"""
Plot Daily / Weekly / Annual Flexibility Needs

Reads flexibility_needs.csv (written by estimate_flexibility_needs.py) and
renders the Daily/Weekly/Annual bar charts into flex_needs_plots/, per
commodity (electricity, heat, hydrogen - see docs/adr/0009): residual
load's own system/category breakdown, and each flexibility option's own
timescale decomposition, system-wide and per Combined category (see
docs/adr/0007, 0008). Bars are stacked, with flex-option bars carrying a
sign that's period-dependent in origin - positive when that option's own
dispatch aligned with what the system needed, negative when it opposed,
regardless of the option's nominal supply/demand role (Geis et al. 2026's
correlation-based flexibility provision, see docs/adr/0017): negative
values in the CSV are expected, not a bug. This script itself has no
opinion on *why* a value is signed one way or the other - it just stacks
whatever's in `flex_need_twh`.

Every system/category view now comes in two variants (see docs/adr/0020):
"aggregate" (`_aggregate` PNG suffix, `group_type`s ending `_aggregate` in
the CSV) sums residual load/flex-option dispatch across countries *before*
decomposing - a copper-plate bound that implicitly assumes unconstrained
cross-border redistribution. "Disaggregated" (`_disaggregated` suffix)
decomposes each country first (the CSV's `country`/`flex_option_country`
rows, written by estimate_flexibility_needs.py, never plotted directly
there) and sums *after* - the opposite, fully-islanded bound. This script
derives every disaggregated plot itself, by summing those country-level CSV
rows (grouped by the CSV's own `category` column for the category-level
roll-up) - no GDX/pybalmorel dependency is added by this (see
docs/adr/0012). Neither variant is "the" true flexibility need; they
bracket it. A single country's own flex-option breakdown can also be
plotted on request via `--country` (table rows for every country are
always in the CSV either way - see docs/adr/0020 for why there's no
plotted grid of all of them by default).

A weather-year ensemble (multiple `Scenario` names sharing one source
scenario, e.g. `base_WY1986_F2050`..`base_WY2020_F2050`, see CONTEXT.md's
"Weather year run") is auto-detected and summarized into one bar per
source scenario rather than one per raw Scenario - unreadable otherwise at
30+ weather years. `--weather-year-stat` (default `mean`) picks
mean/min/median/max of `flex_need_twh` across the ensemble; this is a
plain single-statistic bar, not a distribution view - see
docs/adr/0023/0024.

Also reads interannual_annual_means.csv (also written by
estimate_flexibility_needs.py) and *pools* it here - not in that script -
into a 4th "Interannual" panel (see docs/adr/0023/0024/0026): each row is
one weather year's own raw `annual_mean` (MW), and pooling (the half-
summed-absolute-deviation need/provision arithmetic) is cheap enough to redo
on every plot invocation. This is deliberate, not just convenient: a
weather year later found to be erroneous can be dropped via
`--exclude-weather-year source:year[:run_type]` and the Interannual panel
re-rendered in seconds, without re-running estimate_flexibility_needs.py's
own expensive per-scenario GDX read (confirmed to matter in practice - a
single bad weather year's annual mean, wildly unlike every other year's,
dominated the pooled number before this existed).

Split out from estimate_flexibility_needs.py (see its own docstring) so
that iterating on a plot doesn't require re-running the expensive GDX read
- this script has no GDX/GAMS/pybalmorel dependency at all, only reads a
CSV. Run them back to back:

    python estimate_flexibility_needs.py --output-dir build_postprocess
    python plot_flexibility_needs.py --output-dir build_postprocess

Created on 20.08.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import colorsys
import re
import sys
from collections import defaultdict
from pathlib import Path

# Add repo root to path for scripts.utils imports (see AGENTS.md's
# pybalmorel/import-path note).
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.utils import setup_plot

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #

# Display order for the per-commodity plot loop below - must match
# estimate_flexibility_needs.COMMODITIES. Kept as its own copy rather than
# importing that module, so this script stays free of its GDX/GAMS/
# pybalmorel import chain (the whole point of the split, see module
# docstring) - it's three fixed strings, not worth the coupling.
COMMODITIES = ("ELECTRICITY", "HEAT", "HYDROGEN")

# Default subplot columns for both plotting functions below - Daily/Weekly/
# Annual only. `main()` passes DEFAULT_TIMESCALES + ["Interannual"] instead
# whenever interannual_annual_means.csv has any rows to pool (see
# docs/adr/0023/0024/0026) - a 4th panel, not a replacement for these three.
DEFAULT_TIMESCALES = ["Daily", "Weekly", "Annual"]

# Fixed Balmorel S52xT168 chronological grid (52 weeks x 168 hours), used to
# weight each weather year's own contribution to the Interannual pool - own
# copy of estimate_flexibility_needs.py's constant, for the same GDX-
# independence reason as everything else on this page (see docs/adr/0023 for
# why this is fixed rather than derived from row counts).
HOURS_PER_WEATHER_YEAR = 8736

# Trailing run-type+year suffix on a scenario name (see
# categorize_countries.RUN_TYPE_RE) - kept as its own copy for the same
# GDX-independence reason as COMMODITIES above, not imported.
SCENARIO_SUFFIX_RE = re.compile(r"_(?:F|R)\d{4}$")

# Weather-year suffix on a scenario's own base, post SCENARIO_SUFFIX_RE
# stripping, e.g. "base_WY1986" -> source="base", weather_year="1986" - see
# estimate_flexibility_needs.py's own copy (categorize_countries.
# split_weather_year) and docs/adr/0023. Kept as its own copy for the same
# GDX-independence reason as SCENARIO_SUFFIX_RE above.
WEATHER_YEAR_RE = re.compile(r"^(?P<source>.+)_WY(?P<weather_year>\d{4})$")

_WEATHER_YEAR_STATS = {"mean": "mean", "min": "min", "median": "median", "max": "max"}


def _is_weather_year(scenario: str) -> bool:
    """Whether `scenario` itself parses as a weather-year run (its own
    `_WY<year>` suffix, post SCENARIO_SUFFIX_RE stripping) - not merely
    whether some *other* scenario happens to share its stripped-down
    source name. "base_R2050" and "base_WY1986_F2050" both reduce to
    source "base", but the first is the ordinary reference scenario, the
    second one weather year of a sweep built from it - conflating them
    would silently blend an unrelated scenario into a weather-year
    ensemble's own mean/min/median/max (confirmed directly: without this
    check, "base_R2050" got averaged into "base"'s own weather-year bar)."""
    return WEATHER_YEAR_RE.match(SCENARIO_SUFFIX_RE.sub("", scenario)) is not None


def _source_scenario(scenario: str) -> str:
    """`scenario` with its run-type/year suffix stripped, then its
    weather-year suffix stripped - e.g. "base_WY1986_F2050" -> "base".
    Only meaningful for a name `_is_weather_year` confirms; call sites
    guard on that first (see `_summarize_weather_years`)."""
    base = SCENARIO_SUFFIX_RE.sub("", scenario)
    match = WEATHER_YEAR_RE.match(base)
    return match.group("source") if match else base


def _summarize_weather_years(rows: pd.DataFrame, stat: str) -> pd.DataFrame:
    """One row per (Scenario, Year, group_type, group, category,
    flex_option, Commodity, timescale) - unchanged for an ordinary
    scenario (still its own raw Scenario name, e.g. "SSN_R2050", so
    `--clean`'s own suffix-stripping keeps working exactly as before,
    *even* when it happens to share a stripped-down source name with an
    unrelated weather-year ensemble - see `_is_weather_year`) but
    collapsed to one summary row per *source* scenario (see docs/adr/0023's
    "Scenario name") for every scenario name that itself parses as a
    weather-year run. Auto-detected, never opt-in behind a flag: with 30+
    weather years, one bar per raw Scenario is unreadable regardless of
    whether a flag was remembered - `stat` (mean/min/median/max of
    `flex_need_twh` across weather years) is the only configurable part.
    Applies uniformly to both need (`group_type` in system/category/
    country) and provision (`flex_option_*`) rows - the 30-bar
    unreadability problem is identical for both, see docs/adr/0024's
    Consequences."""
    is_weather_year = rows["Scenario"].map(_is_weather_year)
    display_scenario = rows["Scenario"].where(~is_weather_year, rows["Scenario"].map(_source_scenario))
    working = rows.assign(Scenario=display_scenario)
    group_cols = [c for c in rows.columns if c != "flex_need_twh"]
    # dropna=False: residual-load rows carry an empty (not NaN) flex_option
    # in-memory, but empty string fields round-trip through CSV as NaN
    # (pandas' read_csv default) - pandas' own groupby drops NaN-keyed
    # groups by default, which would silently drop every "need" row here
    # (group_type system_aggregate/category_aggregate/country) rather than
    # summarizing them.
    return working.groupby(group_cols, as_index=False, dropna=False)["flex_need_twh"].agg(_WEATHER_YEAR_STATS[stat])


def _parse_weather_year_exclusions(raw: tuple) -> set:
    """{(source_scenario, weather_year, run_type|None), ...} from
    `--exclude-weather-year` values shaped `source:year` (excludes that
    weather year from every run_type's own pool) or `source:year:run_type`
    (just one) - see docs/adr/0026."""
    exclusions = set()
    for item in raw:
        parts = item.split(":")
        if len(parts) == 2:
            source, year = parts
            exclusions.add((source, year, None))
        elif len(parts) == 3:
            source, year, run_type = parts
            exclusions.add((source, year, run_type))
        else:
            raise click.ClickException(
                f"--exclude-weather-year must look like 'source:year' or 'source:year:run_type', got {item!r}"
            )
    return exclusions


def _apply_weather_year_exclusions(annual_means: pd.DataFrame, exclusions: set) -> pd.DataFrame:
    """`annual_means` with any row matching an `--exclude-weather-year`
    entry dropped - matched against `(source_scenario, weather_year)`
    (excludes that year from every run_type) or, when the exclusion names
    one, `(source_scenario, weather_year, run_type)` specifically. Prints
    exactly what got dropped rather than excluding silently."""
    if not exclusions or annual_means.empty:
        return annual_means
    any_run_type = list(zip(
        annual_means["source_scenario"], annual_means["weather_year"].astype(str), [None] * len(annual_means),
        strict=True,
    ))
    specific = list(zip(
        annual_means["source_scenario"], annual_means["weather_year"].astype(str), annual_means["run_type"],
        strict=True,
    ))
    mask = np.array([a in exclusions or b in exclusions for a, b in zip(any_run_type, specific, strict=True)])
    if mask.any():
        dropped = sorted(set(zip(
            annual_means.loc[mask, "source_scenario"],
            annual_means.loc[mask, "weather_year"],
            annual_means.loc[mask, "run_type"],
            strict=True,
        )))
        print(f"--exclude-weather-year: dropping {int(mask.sum())} row(s) for {dropped}")
    return annual_means[~mask]


def _pool_interannual(annual_means: pd.DataFrame) -> pd.DataFrame:
    """Interannual need/provision rows (`Scenario, Year, group_type, group,
    category, flex_option, Commodity, timescale, flex_need_twh` - the same
    shape `tidy` already has, so callers can concat this straight in), pooled
    here from `annual_means`'s raw per-weather-year `annual_mean_mwh` values
    rather than in estimate_flexibility_needs.py (see docs/adr/0026) - the
    same math that script's own former `_interannual_rows` used, just
    DataFrame-driven since the input is now a flat CSV, not an in-memory
    accumulator:

    `flex_option == ""` rows are residual load (sign-invariant need, same
    construction as the Annual level one level down); `flex_option != ""`
    rows are one option's own provision, signed by *that same group's* own
    Interannual sign (never the option's own - the same rule as `flex_sign`/
    `flexibility_provision`, docs/adr/0017), plus an "Other" catch-all per
    group computed the same additive-residual way as every other timescale's
    own Other. A (source_scenario, run_type, group...) pool with fewer than
    2 weather years is skipped entirely (also what naturally excludes a
    run_type with only one weather year so far, e.g. an R2050 sweep still in
    progress, or a source scenario reduced to a single year by
    `--exclude-weather-year`).

    `Scenario` stays the plain source scenario name (e.g. "base") unless
    that source genuinely has more than one run_type with its own pool, in
    which case each gets a disambiguating `f"{source_scenario}_WY_{run_type}"`
    suffix - distinguishable from any real scenario name (never has "_WY_"
    followed by a bare letter) so it can't collide with an ordinary
    scenario's own raw name once concatenated into `tidy` (confirmed this
    collision is a real risk even without the suffix: "base_R2050", the
    reference scenario, and "base"'s own weather-year ensemble both reduce
    to plain "base" - see `_is_weather_year`).

    Divides by the pool's own weather-year count (`n_years`) - unlike
    Daily/Weekly/Annual, whose population is exactly one year's worth of
    hours (so summing over it already yields a per-year TWh/a figure with
    no extra division needed), Interannual's population spans the *whole*
    N-year ensemble (each year's deviation held constant for all 8736 of
    its own hours, same pattern as the Annual level's own weekly deviation
    - see `HOURS_PER_WEATHER_YEAR`'s use below). Summing over that without
    dividing by N gives a *total over N years*, not an annualized rate -
    confirmed to matter in practice: this was returning numbers on the
    order of total annual demand before the `/ n_years` was added. Every
    row in one group (`need`, every tracked option's own `provision`, and
    `Other`) divides by the *same* `n_years` - the residual load's own
    pool size for that group, looked up via `sign_key` rather than each
    option's own (possibly smaller, if some years had zero dispatch)
    count - so the group's additivity (tracked options + Other == need)
    still holds exactly after normalizing, not just before it."""
    mwh_to_twh = 1e-6
    key_cols = ["source_scenario", "run_type", "group_type", "group", "category", "Commodity"]
    residual = annual_means[annual_means["flex_option"] == ""]
    options = annual_means[annual_means["flex_option"] != ""]

    rows = []  # each dict carries _source_scenario/_run_type too, resolved into "Scenario" at the end
    signs = {}  # tuple(key_cols) -> {weather_year: sign}
    need_value = {}  # same key -> (need TWh, Year)
    n_years_by_key = {}  # same key -> residual load's own weather-year count for this group
    tracked = defaultdict(float)  # same key -> summed tracked-option provision (TWh)

    for key, grp in residual.groupby(key_cols, dropna=False):
        n_years = grp["weather_year"].nunique()
        if n_years < 2:
            continue
        source_scenario, run_type, group_type, group, category, commodity = key
        values = grp["annual_mean_mwh"].to_numpy(dtype=float)
        n_year_mean = values.mean()
        need = 0.5 * HOURS_PER_WEATHER_YEAR * np.abs(values - n_year_mean).sum() * mwh_to_twh / n_years
        need_value[key] = (need, grp["Year"].iloc[0])
        n_years_by_key[key] = n_years
        signs[key] = dict(zip(grp["weather_year"], np.sign(values - n_year_mean), strict=True))
        rows.append({
            "_source_scenario": source_scenario, "_run_type": run_type, "Year": grp["Year"].iloc[0],
            "group_type": group_type, "group": group, "category": category,
            "flex_option": "", "Commodity": commodity, "timescale": "Interannual",
            "flex_need_twh": need,
        })

    for key, grp in options.groupby(key_cols + ["flex_option"], dropna=False):
        if grp["weather_year"].nunique() < 2:
            continue
        source_scenario, run_type, group_type, group, category, commodity, flex_option = key
        sign_key = (source_scenario, run_type, group_type.removeprefix("flex_option_"), group, category, commodity)
        year_signs = signs.get(sign_key)
        if not year_signs:
            continue  # no matching residual-load signal for this group - skip rather than guess
        n_years = n_years_by_key[sign_key]
        values = grp["annual_mean_mwh"].to_numpy(dtype=float)
        n_year_mean = values.mean()
        provision = 0.5 * HOURS_PER_WEATHER_YEAR * mwh_to_twh * sum(
            (value - n_year_mean) * year_signs[year]
            for year, value in zip(grp["weather_year"], values, strict=True)
            if year in year_signs
        ) / n_years
        tracked[sign_key] += provision
        rows.append({
            "_source_scenario": source_scenario, "_run_type": run_type, "Year": grp["Year"].iloc[0],
            "group_type": group_type, "group": group, "category": category,
            "flex_option": flex_option, "Commodity": commodity, "timescale": "Interannual",
            "flex_need_twh": provision,
        })

    for sign_key, (need, need_year) in need_value.items():
        source_scenario, run_type, group_type, group, category, commodity = sign_key
        rows.append({
            "_source_scenario": source_scenario, "_run_type": run_type, "Year": need_year,
            "group_type": f"flex_option_{group_type}", "group": group, "category": category,
            "flex_option": "Other", "Commodity": commodity, "timescale": "Interannual",
            "flex_need_twh": need - tracked.get(sign_key, 0.0),
        })

    result_cols = ["Scenario", "Year", "group_type", "group", "category", "flex_option", "Commodity", "timescale", "flex_need_twh"]
    if not rows:
        return pd.DataFrame(columns=result_cols)

    # Resolve "Scenario" only now that every row's own (source_scenario,
    # run_type) is known - see this function's own docstring.
    run_types_by_source = defaultdict(set)
    for source_scenario, run_type, *_rest in need_value:
        run_types_by_source[source_scenario].add(run_type)
    for row in rows:
        source_scenario = row.pop("_source_scenario")
        run_type = row.pop("_run_type")
        row["Scenario"] = (
            source_scenario
            if len(run_types_by_source[source_scenario]) <= 1
            else f"{source_scenario}_WY_{run_type}"
        )

    return pd.DataFrame(rows, columns=result_cols)


def _display_scenarios(scenarios: list, clean: bool) -> list:
    """Scenario names for x-tick labels, e.g. "base_R2050" -> "base" when
    `clean` (see SCENARIO_SUFFIX_RE). Only affects axis labels - callers
    still filter/index rows by the raw, unstripped `scenarios` list, so two
    scenarios that only differ by run-type/year (e.g. base_R2030 vs.
    base_R2050) would show identical labels rather than collide in the
    data itself."""
    if not clean:
        return scenarios
    return [SCENARIO_SUFFIX_RE.sub("", s) for s in scenarios]


def _shades(anchor_hex: str, lightnesses: dict) -> dict:
    """{name: hex} - every value sharing `anchor_hex`'s hue and saturation,
    each at its own lightness from `lightnesses` (0=black, 1=white) - so
    functionally-related flex options (e.g. EV charging/V2G/Electricity
    storage/transmission, all temporal/spatial electricity movers) read as
    shades of one color rather than unrelated hues that happen to be
    individually distinct. `anchor_hex` itself is never in the output -
    callers that want the anchor's own literal color (e.g. because it's
    already an established/approved value) write it directly instead of
    round-tripping it through here, avoiding any float-rounding drift."""
    h, _, s = colorsys.rgb_to_hls(
        *(int(anchor_hex[i : i + 2], 16) / 255 for i in (1, 3, 5))
    )
    return {
        name: "#{:02x}{:02x}{:02x}".format(
            *(round(c * 255) for c in colorsys.hls_to_rgb(h, max(0.0, min(1.0, l)), s))
        )
        for name, l in lightnesses.items()
    }


# Colors grouped into families by function, each family a set of shades of
# one hue (via `_shades`) rather than unrelated per-option colors, "inspired
# by" pybalmorel.formatting's tech_colours/fuel_colours (imported as
# balmorel_colours in scripts/Balmorel/analysis/analyse.py, which further
# extends it with DISTRICT_HEATING/INDUSTRY/INDIVIDUAL) - not imported
# directly, to keep this script's deliberate independence from the
# pybalmorel/GDX import chain (see module docstring). Two anchors keep their
# literal balmorel_colours-derived hex (Electrolysers from tech_colours'
# ELECTROLYZER, Hydro reservoirs from tech_colours' HYDRO-RESERVOIRS) rather
# than being regenerated via `_shades`, so they stay pixel-identical to
# their original values.
FLEX_OPTION_COLOURS = {
    "Hydro reservoirs": "#33b1ff",  # standalone - a generation technology, not storage/conversion/backup
    "Electrolysers": "#add8e6",  # anchor for the hydrogen-conversion family below
    "Nuclear": "#8e44ad",  # standalone
    # Electricity storage/movers - EV charging, V2G, Electricity storage and
    # Electricity transmission are all temporal or spatial ways of shifting
    # electricity rather than generating it, so they share one hue (anchored
    # on Electricity storage's original tech_colours-derived amber).
    **_shades(
        "#fff6d5ff",
        {
            "V2G": 0.22,
            "Electricity storage": 0.34,
            "Heat storage": 0.46,
            "EV charging": 0.58,
            "Electricity transmission": 0.74,
        },
    ),
    # Hydrogen conversion/storage - Fuel cells (H2->electricity) and
    # Electrolysers (electricity->H2) are each other's inverse, and
    # Hydrogen storage/transmission are the same commodity's own movers;
    # anchored on Electrolysers' own colour above so it's unaffected.
    **_shades(
        "#add8e6",
        {
            "Hydrogen storage": 0.32,
            "Fuel cells": 0.55,
            "Hydrogen transmission": 0.90,
        },
    ),
    # PtH (power-to-heat, see docs/adr/0017's Industrial/Individual/District
    # split) - anchored on ELECT-TO-HEAT's own tech_colours hex.
    **_shades(
        "#d40000ff",
        {
            "Industrial PtH": 0.32,
            "District PtH": 0.50,
            "Individual PtH": 0.72,
        },
    ),
    # Generic dispatchable/backup/catch-all - Peaker, Thermal and Other are
    # all "conventional, not sector-coupled" technologies (or, for Other,
    # literally unclassified), so they share a neutral grey family.
    **_shades(
        "#4d4d4d",
        {
            "Peaker": 0.25,
            "Thermal": 0.50,
            "Other": 0.80,
        },
    ),
}


def _ordered_hues(hue_col: str, values) -> list:
    """`values`, ordered to match FLEX_OPTION_COLOURS' own grouping when
    `hue_col == "flex_option"` - so stacking order (and, since matplotlib
    legends list entries in the order `ax.bar(..., label=...)` was called,
    the legend too) reflects the functional families (storage/movers,
    hydrogen conversion, PtH, generic backup) instead of an alphabetical
    shuffle that scatters them. Any value absent from FLEX_OPTION_COLOURS
    (a flex option added without a family assignment yet) is appended
    alphabetically at the end rather than silently dropped. Spatial groups
    (hue_col == "group": system/category/country) have no such family
    grouping to draw from, so they stay alphabetical."""
    values = set(values)
    if hue_col != "flex_option":
        return sorted(values)
    ordered = [name for name in FLEX_OPTION_COLOURS if name in values]
    ordered += sorted(values - set(ordered))
    return ordered


def _colour_for(hue_col: str, hue, index: int, fallback_cmap):
    """FLEX_OPTION_COLOURS lookup for `hue_col == "flex_option"` (with a
    colormap fallback for any name not in that dict, e.g. a newly-added
    flex option); the colormap directly for spatial groups (system/
    category/country), which have no fixed technology palette to draw
    from. `index` (the hue's position in its already-deterministically-
    sorted `hues` list) drives the colormap fallback, not `hash(hue)` -
    Python's string hashing is randomised per-process by default, which
    would reshuffle spatial-group colors between runs/regenerated plots."""
    if hue_col == "flex_option" and hue in FLEX_OPTION_COLOURS:
        return FLEX_OPTION_COLOURS[hue]
    return fallback_cmap(index % fallback_cmap.N)


def _stack_bars(
    ax,
    x: np.ndarray,
    sub: pd.DataFrame,
    hue_col: str,
    hues: list,
    scenarios: list,
    width: float,
    show_total_line: bool = False,
    dark: bool = False,
) -> None:
    """Draws one stacked bar per `x` position (scenario): each `hues` value's
    flex_need_twh is stacked in turn - positive values upward from the
    running positive top, negative values downward from the running
    negative bottom. Residual load's own rows (group_type system/category)
    are always >=0, so they simply stack upward; flex-option rows
    (group_type flex_option_system/flex_option_category) carry whatever
    sign estimate_flexibility_needs.py's correlation-based flexibility
    provision computed (see docs/adr/0017) - period-dependent, not a fixed
    per-option rule, so which options land above/below zero can differ by
    scenario/year, and the visual stack top is no longer the total need
    once any option goes negative - see `show_total_line`.

    Colors come from `_colour_for` rather than matplotlib's default
    per-axes cycle (only 10 colors) - flex_option is now routinely >10
    values (Electricity-to-heat alone is 3, see docs/adr/0017), and letting
    the cycle wrap silently reuses the same color for two different
    options, which reads as a real bug in a stacked chart, not a cosmetic
    one.

    `show_total_line`: draws a black dashed marker at each bar's true net
    total (sum of every hue's flex_need_twh, including negative
    contributions - by construction equal to the corresponding system/
    category row's own flexibility need, see docs/adr/0017's additivity
    property) - since that's no longer visually obvious from the stack top
    alone once a hue goes negative."""
    bottom_pos = np.zeros(len(x))
    bottom_neg = np.zeros(len(x))
    cmap = plt.get_cmap("tab20")
    totals = np.zeros(len(x))
    line_colour = "white" if dark else "black"
    for i, hue in enumerate(hues):
        color = _colour_for(hue_col, hue, i, cmap)
        heights = np.array([
            sub.loc[
                (sub["Scenario"] == sc) & (sub[hue_col] == hue), "flex_need_twh"
            ].sum()
            for sc in scenarios
        ])
        pos = np.where(heights >= 0, heights, 0.0)
        neg = np.where(heights < 0, heights, 0.0)
        ax.bar(x, pos, width, bottom=bottom_pos, label=hue, color=color)
        ax.bar(x, neg, width, bottom=bottom_neg, color=color)
        bottom_pos += pos
        bottom_neg += neg
        totals += heights
    ax.axhline(0, color=line_colour, linewidth=0.8)
    if show_total_line:
        ax.hlines(
            totals,
            x - width / 2,
            x + width / 2,
            colors=line_colour,
            linestyles="dashed",
            linewidth=1.5,
            label="Total flexibility need",
        )


def _shared_ylim(
    rows: pd.DataFrame, hue_col: str, extra_group_cols: list | None = None
) -> tuple:
    """(ymin, ymax), with a 5% pad, spanning every stacked bar's actual
    positive top / negative bottom across every (Scenario, timescale
    [, extra_group_cols]) combination in `rows` - used so a figure's
    Daily/Weekly/Annual subplots (or, for the category grid, every
    category x timescale subplot) share one y-axis and magnitudes are
    directly comparable across timescales, rather than each subplot
    auto-scaling to fill its own panel."""
    group_cols = ["Scenario", "timescale"] + (extra_group_cols or [])
    tops, bottoms = [], []
    for _, grp in rows.groupby(group_cols):
        per_hue = grp.groupby(hue_col)["flex_need_twh"].sum()
        tops.append(per_hue.clip(lower=0).sum())
        bottoms.append(per_hue.clip(upper=0).sum())
    if not tops:
        return (0.0, 1.0)
    top, bottom = max(tops), min(bottoms)
    pad = 0.05 * ((top - bottom) or 1.0)
    return (bottom - pad, top + pad)


def plot_flexibility_needs(
    rows: pd.DataFrame,
    title: str,
    output_path: Path,
    hue_col: str = "group",
    dark: bool = False,
    clean: bool = False,
    timescales: list = DEFAULT_TIMESCALES,
) -> None:
    """One figure, one panel per timescale: x-axis = scenario, one *stacked*
    bar per timescale (each `hue_col` value stacked in turn, see
    `_stack_bars`), height = flex_need_twh. `hue_col` defaults to "group"
    (spatial grouping: system/category/country); pass "flex_option" to
    stack by flex option instead (also draws the dashed total-need line,
    see `_stack_bars`). `timescales` defaults to Daily/Weekly/Annual;
    `main()` passes a 4th "Interannual" panel on top when pooling
    interannual_annual_means.csv (via `_pool_interannual`) produced rows for
    this commodity/group_type (see docs/adr/0023/0024/0026) - a scenario
    with no weather-year ensemble simply shows an all-zero Interannual panel (`_stack_bars` sums an empty
    slice to 0), not an error."""
    scenarios = sorted(rows["Scenario"].unique())
    groups = _ordered_hues(hue_col, rows[hue_col].unique())
    x = np.arange(len(scenarios))
    width = 0.6
    ylim = _shared_ylim(rows, hue_col)

    fig, axes = plt.subplots(1, len(timescales), figsize=(5 * len(timescales), 5), squeeze=False)
    axes = axes[0]
    for ax, timescale in zip(axes, timescales):
        sub = rows[rows["timescale"] == timescale]
        _stack_bars(
            ax,
            x,
            sub,
            hue_col,
            groups,
            scenarios,
            width,
            show_total_line=(hue_col == "flex_option"),
            dark=dark,
        )
        ax.set_xticks(x)
        ax.set_xticklabels(_display_scenarios(scenarios, clean), rotation=45, ha="right")
        ax.set_title(f"{timescale} flexibility need")
        ax.set_ylabel("Flexibility need [TWh/a]")
        ax.set_ylim(ylim)

    handles, labels = axes[-1].get_legend_handles_labels()
    axes[-1].legend(
        handles,
        labels,
        bbox_to_anchor=(1.02, 0.5),
        loc="center left",
        fontsize=8,
        borderaxespad=0.0,
    )
    fig.suptitle(f"Flexibility needs ({title})")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_flex_option_category_grid(
    rows: pd.DataFrame,
    title: str,
    output_path: Path,
    dark: bool = False,
    clean: bool = False,
    timescales: list = DEFAULT_TIMESCALES,
) -> None:
    """Grid: one row per Combined category, one column per timescale; each
    subplot stacks scenario x flex option (see `_stack_bars`, including the
    dashed total-need line) - the category-level counterpart to
    `plot_flexibility_needs(..., hue_col="flex_option")`'s system-wide plot,
    which can't itself carry a second (category) dimension. `timescales`
    defaults to Daily/Weekly/Annual; see `plot_flexibility_needs`'s own
    docstring for the 4th "Interannual" column `main()` adds.

    The y-axis is shared *within* a category's own row (its timescale
    columns), not across categories - different categories can have wildly
    different absolute magnitudes (e.g. "High Demand" vs "Low Demand"), so
    a grid-wide shared axis would flatten smaller categories to invisible
    slivers; each row scaling to its own data keeps every category
    readable while still letting its timescales be compared against each
    other."""
    categories = sorted(rows["group"].unique())
    flex_options = _ordered_hues("flex_option", rows["flex_option"].unique())
    scenarios = sorted(rows["Scenario"].unique())
    x = np.arange(len(scenarios))
    width = 0.6

    fig, axes = plt.subplots(
        len(categories), len(timescales), figsize=(5 * len(timescales), 4 * len(categories)), squeeze=False
    )
    for row_i, category in enumerate(categories):
        cat_rows = rows[rows["group"] == category]
        row_ylim = _shared_ylim(cat_rows, "flex_option")
        for col_i, timescale in enumerate(timescales):
            ax = axes[row_i][col_i]
            sub = cat_rows[cat_rows["timescale"] == timescale]
            _stack_bars(
                ax,
                x,
                sub,
                "flex_option",
                flex_options,
                scenarios,
                width,
                show_total_line=True,
                dark=dark,
            )
            ax.set_ylim(row_ylim)
            ax.set_xticks(x)
            ax.set_xticklabels(_display_scenarios(scenarios, clean), rotation=45, ha="right")
            if row_i == 0:
                ax.set_title(f"{timescale} flexibility need")
            if col_i == 0:
                ax.set_ylabel(f"{category}\nFlex need [TWh/a]")

    handles, labels = axes[0][-1].get_legend_handles_labels()
    axes[0][-1].legend(
        handles,
        labels,
        bbox_to_anchor=(1.02, 1.0),
        loc="upper left",
        fontsize=8,
        borderaxespad=0.0,
    )
    # rect reserves the top ~5% of the figure for suptitle - tight_layout()
    # alone doesn't know suptitle exists, so without this the top category
    # row's own subplot titles crowd right up against (or under) it, worse
    # the taller the grid (more categories) gets.
    fig.suptitle(f"Flexibility-option use, by Combined category ({title})", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


@click.command()
@click.option(
    "--output-dir",
    type=str,
    default="build_postprocess",
    help="Where to read flexibility_needs.csv from and write flex_needs_plots/ into.",
)
@click.option(
    "--table-csv",
    type=str,
    default=None,
    help="Path to estimate_flexibility_needs.py's output. Defaults to <output-dir>/flexibility_needs.csv",
)
@click.option(
    "--annual-means-csv",
    type=str,
    default=None,
    help="Path to estimate_flexibility_needs.py's raw per-weather-year output. Defaults to "
    "<output-dir>/interannual_annual_means.csv. When present and non-empty, pooled here (see "
    "docs/adr/0023/0024/0026) into a 4th 'Interannual' panel alongside Daily/Weekly/Annual - a source "
    "scenario with no weather-year ensemble just shows an all-zero Interannual panel there, not an error.",
)
@click.option(
    "--exclude-weather-year",
    "exclude_weather_years",
    multiple=True,
    default=(),
    help="Drop a weather year from the Interannual pool before pooling, e.g. --exclude-weather-year "
    "base:1985 (every run_type) or base:1985:F (just Fullyear), repeatable - see docs/adr/0026. Use this "
    "once a weather year is found to be erroneous, without re-running estimate_flexibility_needs.py.",
)
@click.option(
    "--country",
    "countries",
    multiple=True,
    default=(),
    help="Also plot one country's own flexibility-option breakdown (group_type=flex_option_country), "
    "e.g. --country DENMARK, repeatable. Table rows for every country are always in the CSV either "
    "way (see docs/adr/0020) - this only opts into a plot for the ones named here, not one image per "
    "country by default.",
)
@click.option("--dark", is_flag=True, help="Make dark plot?")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["png", "svg", "pdf"]),
    default="png",
    show_default=True,
    help="Output image format for every plot written.",
)
@click.option(
    "--clean",
    is_flag=True,
    help="Strip the _F<year>/_R<year> run-type suffix from scenario names in axis labels, e.g. 'base_R2050' -> 'base'.",
)
@click.option(
    "--weather-year-stat",
    type=click.Choice([*_WEATHER_YEAR_STATS, "none"]),
    default="mean",
    show_default=True,
    help="How to summarize a weather-year ensemble's per-year bars into one (see docs/adr/0023/0024) - "
    "auto-detected whenever a source scenario has more than one weather year present, for both need and "
    "provision plots. A plain single-statistic bar, not a distribution view (see docs/adr/0024's "
    "Consequences) - a flex option's provision can flip sign year-to-year, so 'mean' can understate how "
    "much it actually varies. 'none' fully disables this (and the 4th Interannual panel, which only makes "
    "sense once weather years are pooled) - every Scenario name plotted independently, exactly as before "
    "this feature existed.",
)
def main(
    output_dir: str,
    table_csv: str,
    annual_means_csv: str,
    exclude_weather_years: tuple,
    countries: tuple,
    dark: bool,
    fmt: str,
    clean: bool,
    weather_year_stat: str,
):
    setup_plot(dark=dark)
    output_path = Path(output_dir)
    plots_dir = output_path / "flex_needs_plots"

    table_path = Path(table_csv) if table_csv else output_path / "flexibility_needs.csv"
    if not table_path.exists():
        print(
            f"{table_path} not found - run estimate_flexibility_needs.py first. Nothing to plot."
        )
        return

    tidy = pd.read_csv(table_path, dtype={"category": str}).fillna({"category": ""})
    if tidy.empty:
        print(f"{table_path} is empty - nothing to plot.")
        return

    timescales = list(DEFAULT_TIMESCALES)
    if weather_year_stat == "none":
        # Every Scenario name plotted independently, exactly as before
        # weather-year ensembles existed - no summarizing, no Interannual
        # panel (which is meaningless without pooling - it's a property of
        # the ensemble, not of any one raw Scenario, see docs/adr/0023/0024).
        print("--weather-year-stat none: plotting every Scenario independently, no Interannual panel.")
    else:
        tidy = _summarize_weather_years(tidy, weather_year_stat)

        # interannual_annual_means.csv is raw, unpooled per-weather-year
        # data (see docs/adr/0026) - pool it here (not read pre-pooled)
        # specifically so --exclude-weather-year can drop a bad weather year
        # and get a corrected Interannual panel without re-running
        # estimate_flexibility_needs.py's own expensive GDX read.
        annual_means_path = (
            Path(annual_means_csv) if annual_means_csv else output_path / "interannual_annual_means.csv"
        )
        if annual_means_path.exists():
            # fillna both category and flex_option: residual-load rows carry
            # an empty (not NaN) flex_option in memory, but empty string
            # fields round-trip through CSV as NaN (pandas' read_csv
            # default) - _pool_interannual's own flex_option == "" split
            # would otherwise treat every residual-load row as unmatched.
            annual_means = pd.read_csv(
                annual_means_path,
                dtype={"category": str, "flex_option": str, "weather_year": str, "run_type": str},
            ).fillna({"category": "", "flex_option": ""})
            if not annual_means.empty:
                exclusions = _parse_weather_year_exclusions(exclude_weather_years)
                annual_means = _apply_weather_year_exclusions(annual_means, exclusions)
                interannual = _pool_interannual(annual_means)
                if not interannual.empty:
                    tidy = pd.concat([tidy, interannual], ignore_index=True)
                    timescales.append("Interannual")

    plots_dir.mkdir(parents=True, exist_ok=True)

    for commodity in COMMODITIES:
        by_commodity = tidy[tidy["Commodity"] == commodity]
        if by_commodity.empty:
            continue

        # --- Aggregate residual-load views: system/category summed across
        # countries *before* decomposition (the copper-plate bound written
        # directly by estimate_flexibility_needs.py - see docs/adr/0020).
        for group_type, label in (("system_aggregate", "system"), ("category_aggregate", "category")):
            subset = by_commodity[by_commodity["group_type"] == group_type]
            if subset.empty:
                continue
            plot_flexibility_needs(
                subset,
                f"{label}, {commodity}, aggregate",
                plots_dir / f"{label}_aggregate_{commodity}.{fmt}",
                dark=dark,
                clean=clean,
                timescales=timescales,
            )

        # --- Disaggregated residual-load views: derived here by summing the
        # CSV's own `country` rows (each already decomposed before any
        # spatial summing) - the opposite, fully-islanded bound. Category
        # roll-up uses the CSV's `category` column rather than recomputing
        # Combined-category membership, so this script stays free of the
        # GDX/pybalmorel dependency estimate_flexibility_needs.py needs (see
        # docs/adr/0012, 0020).
        country_rows = by_commodity[by_commodity["group_type"] == "country"]
        if not country_rows.empty:
            system_disaggregated = (
                country_rows.groupby(["Scenario", "timescale"], as_index=False)["flex_need_twh"]
                .sum()
                .assign(group="All")
            )
            plot_flexibility_needs(
                system_disaggregated,
                f"system, {commodity}, disaggregated",
                plots_dir / f"system_disaggregated_{commodity}.{fmt}",
                dark=dark,
                clean=clean,
                timescales=timescales,
            )

            category_disaggregated = (
                country_rows[country_rows["category"] != ""]
                .groupby(["Scenario", "category", "timescale"], as_index=False)["flex_need_twh"]
                .sum()
                .rename(columns={"category": "group"})
            )
            if not category_disaggregated.empty:
                plot_flexibility_needs(
                    category_disaggregated,
                    f"category, {commodity}, disaggregated",
                    plots_dir / f"category_disaggregated_{commodity}.{fmt}",
                    dark=dark,
                    clean=clean,
                    timescales=timescales,
                )

        # --- Aggregate flex-option views (same copper-plate bound, applied
        # to each option's own dispatch instead of residual load). ---
        option_system_rows = by_commodity[
            by_commodity["group_type"] == "flex_option_system_aggregate"
        ]
        if not option_system_rows.empty:
            plot_flexibility_needs(
                option_system_rows,
                f"flexibility options, system-wide, aggregate ({commodity})",
                plots_dir / f"system_by_option_aggregate_{commodity}.{fmt}",
                hue_col="flex_option",
                dark=dark,
                clean=clean,
                timescales=timescales,
            )

        option_category_rows = by_commodity[
            by_commodity["group_type"] == "flex_option_category_aggregate"
        ]
        if not option_category_rows.empty:
            plot_flex_option_category_grid(
                option_category_rows,
                f"{commodity}, aggregate",
                plots_dir / f"category_by_option_aggregate_{commodity}.{fmt}",
                dark=dark,
                clean=clean,
                timescales=timescales,
            )

        # --- Disaggregated flex-option views: summed from the CSV's
        # `flex_option_country` rows (see docs/adr/0020) - additive with the
        # disaggregated residual-load totals above by construction, since
        # each country's own tracked options + its own "Other" already sum
        # to that country's own need (docs/adr/0017's additivity, applied
        # per country) and summation is linear.
        option_country_rows = by_commodity[by_commodity["group_type"] == "flex_option_country"]
        if not option_country_rows.empty:
            system_by_option_disaggregated = option_country_rows.groupby(
                ["Scenario", "flex_option", "timescale"], as_index=False
            )["flex_need_twh"].sum()
            plot_flexibility_needs(
                system_by_option_disaggregated,
                f"flexibility options, system-wide, disaggregated ({commodity})",
                plots_dir / f"system_by_option_disaggregated_{commodity}.{fmt}",
                hue_col="flex_option",
                dark=dark,
                clean=clean,
                timescales=timescales,
            )

            category_by_option_disaggregated = (
                option_country_rows[option_country_rows["category"] != ""]
                .groupby(["Scenario", "category", "flex_option", "timescale"], as_index=False)["flex_need_twh"]
                .sum()
                .rename(columns={"category": "group"})
            )
            if not category_by_option_disaggregated.empty:
                plot_flex_option_category_grid(
                    category_by_option_disaggregated,
                    f"{commodity}, disaggregated",
                    plots_dir / f"category_by_option_disaggregated_{commodity}.{fmt}",
                    dark=dark,
                    clean=clean,
                    timescales=timescales,
                )

            # --- Optional: one named country's own flex-option breakdown. ---
            for country in countries:
                country_subset = option_country_rows[option_country_rows["group"] == country]
                if country_subset.empty:
                    print(f"No flex_option_country rows for {country!r} ({commodity}) - skipping.")
                    continue
                plot_flexibility_needs(
                    country_subset,
                    f"flexibility options, {country} ({commodity})",
                    plots_dir / f"country_by_option_{country}_{commodity}.{fmt}",
                    hue_col="flex_option",
                    dark=dark,
                    clean=clean,
                    timescales=timescales,
                )

    print(f"Wrote plots to {plots_dir}.")


if __name__ == "__main__":
    main()
