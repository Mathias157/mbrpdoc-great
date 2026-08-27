"""
Estimate Daily / Weekly / Annual Flexibility Needs from Residual Load

For each fullyear/rolling scenario result and each commodity (electricity,
heat, hydrogen - see docs/adr/0009), computes hourly residual load
(non-dispatchable demand minus non-dispatchable supply, see CONTEXT.md and
docs/adr/0006/0009) per country, then decomposes it hierarchically
(hourly->daily->weekly->annual, following Geis et al. (2026)) into
flexibility-need numbers (TWh/a) at three levels: system-wide and per
Demand/VRE Combined category (membership fixed from a reference scenario,
see docs/adr/0004) - each computed by *summing residual load across
countries first, then decomposing* (group_type suffix `_aggregate`) - and
per country (`group_type="country"`, decomposed first, never spatially
summed). The two group levels are NOT interchangeable: since the need
metric is built from absolute deviations, summing before decomposing always
understates summing each country's own already-decomposed need (triangle
inequality) - the aggregate figure implicitly assumes unconstrained
("copper-plate") cross-border redistribution, crediting that smoothing to
the aggregation step itself rather than to any tracked flex option (most
consequentially transmission). Both are kept, deliberately, as two
different modelling bounds rather than one replacing the other - see
docs/adr/0020. Country rows carry a `category` column (Combined-category
membership) so `plot_flexibility_needs.py` can roll them up into
category-level "disaggregated" plots itself, without needing its own GDX
dependency (see docs/adr/0012). Heat and hydrogen residual load is
non-dispatchable demand only, never netted against a non-dispatchable
supply (see docs/adr/0009).

Each flexibility option's own commodity-signed net hourly dispatch (see
flex_option_metrics.FLEX_OPTIONS, CONTEXT.md's "Commodity-signed flex
value", and docs/adr/0008) is decomposed the same hierarchical way, but
signed via Geis et al. (2026)'s correlation-based "flexibility provision"
method (docs/adr/0017) rather than a fixed per-option sign: each option's
own deviation curve is weighted by the *group's own* deviation sign (from
that group's own residual load, not the option's own), making its
contribution exactly additive with that group's own Daily/Weekly/Annual
need - including an explicit "Other" catch-all for whatever's left
unattributed, per group and commodity. Computed at the same three levels as
residual load: `flex_option_system_aggregate`, `flex_option_category_aggregate`,
and `flex_option_country` (new, see docs/adr/0020) - the last one is what
lets `plot_flexibility_needs.py` derive a disaggregated by-option view the
same way it derives disaggregated residual load, instead of the aggregate
tables' own spatial-summing-before-decomposition blind spot.

Compute-only - writes flexibility_needs.csv and nothing else. Reading the
GDX results this needs (particularly PRO_YCRAGFST) is the expensive part of
this pipeline stage, both in time and RAM, even with the .gdx_cache/*.pkl
symbol cache (see `_get_result_cached`) - so plotting was split out into
its own companion script, `plot_flexibility_needs.py`, which only reads
this CSV and has no GDX/GAMS dependency at all. Run them back to back:

    python estimate_flexibility_needs.py --output-dir build_postprocess
    python plot_flexibility_needs.py --output-dir build_postprocess

Created on 14.08.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import sys
import time
from pathlib import Path

# Add repo root (for scripts.postprocessing.*) and the Balmorel submodule's
# analysis/ dir (for functions.backup_production - see AGENTS.md's note on
# how `pixi run analyse` invokes analyse.py) to path for imports.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "Balmorel" / "analysis"))

import click
import numpy as np
import pandas as pd
from decouple import config
from pybalmorel import Balmorel

from functions import backup_production

# Wall-clock timing markers (HPC runs of this script take a long time - see
# module docstring - and it's not obvious up front whether that's GDX
# reading, GAMS database collection, or the per-scenario/option Python loops
# below; these markers let a slow run be diagnosed after the fact from its
# stdout log alone, without re-running under a profiler).
_T0 = time.perf_counter()


def _log(msg: str) -> None:
    print(f"[t={time.perf_counter() - _T0:8.1f}s] {msg}", flush=True)

from scripts.postprocessing.aggregate_category_costs import build_reference_category_map
from scripts.postprocessing.categorize_countries import (
    SOLAR_TECHNOLOGIES,
    WIND_TECHNOLOGIES,
    region_to_country_map,
    scenario_target_year,
    select_scenario_names,
)
from scripts.postprocessing.flex_option_metrics import (
    FLEX_OPTIONS,
    STORAGE_CHARGE_CATEGORIES,
)

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #

COMMODITIES = ("ELECTRICITY", "HEAT", "HYDROGEN")

# Non-dispatchable supply is fixed (not configurable) - wind, solar and
# run-of-river hydro, the same "full-certainty" grouping this Balmorel
# dataset already uses internally (VRE_CERT_AS.inc). Electricity-only - see
# docs/adr/0006/0009 for why heat and hydrogen have no non-dispatchable
# supply counterpart.
NON_DISPATCHABLE_SUPPLY_TECHNOLOGIES = [
    *WIND_TECHNOLOGIES,
    *SOLAR_TECHNOLOGIES,
    "HYDRO-RUN-OF-RIVER",
]

# EL_DEMAND_YCRST's own VARIABLE_CATEGORY values with no flexibility-option
# home - EXOGENOUS (pure inelastic household/industry/agriculture/datacentre
# load) plus technical/parasitic categories confirmed present and nonzero in
# this dataset (checked directly against a cached EL_DEMAND_YCRST.pkl, not
# guessed): DIST_LOSSES/TRANS_LOSSES (grid losses - not dispatched),
# ENDO_CCS (CCS parasitic load - not a tracked flex option), ENDO_BIOMETHANE
# (negligible but real). Fixed, not user-configurable: every EL_DEMAND_YCRST
# category must land in exactly one place - here, or exactly one flex
# option's own signed dispatch - so flexibility *provision*'s additivity
# holds (see docs/adr/0017, which supersedes 0006's `--demand-categories`
# flag). `ENDOGENOUS_ELECT2HEAT`/`ENDO_H2`/`ENDO_EV`'s flexible share are
# therefore always excluded here - a flex option always claims them.
ELECTRICITY_NON_FLEX_DEMAND_CATEGORIES = (
    "EXOGENOUS",
    "DIST_LOSSES",
    "TRANS_LOSSES",
    "ENDO_CCS",
    "ENDO_BIOMETHANE",
)
# Heat/hydrogen's own technical-loss-equivalent categories are unverified
# against live data (no local .gdx_cache for H_DEMAND_YCRAST/H2_DEMAND_YCRST
# yet) - EXOGENOUS only for now, to be extended the same way once checked
# (see docs/adr/0017).
NON_ELECTRICITY_DEMAND_CATEGORIES = ("EXOGENOUS",)

NEEDS_COLUMNS = [
    "Scenario",
    "Year",
    "group_type",
    "group",
    "category",
    "flex_option",
    "Commodity",
    "timescale",
    "flex_need_twh",
]

_EMPTY_HOURLY = pd.DataFrame(columns=["Country", "Season", "Time", "Value"])

# Flattened (flex_option, commodity, spec) triples for every commodity view
# in flex_option_metrics.FLEX_OPTIONS whose own MainResults symbol carries
# an hourly Season/Time dimension - every kind except "system_only"
# (Demand response's DR_FLEX_Y has no "ST" counterpart in this dataset's own
# naming convention for "already summed over Season/Time", see pybalmorel's
# formatting.py). Demand response therefore never becomes a named row here -
# it passively falls into the "Other" catch-all instead (see
# `flexibility_provision`/docs/adr/0017). EV charging/V2G
# ("net_category_signed", EL_DEMAND_YCRST) are decomposable here even though
# V2G wasn't originally (docs/adr/0007) - EL_DEMAND_YCRST does have an
# hourly counterpart, unlike the V2G_FLEX_YCR symbol it replaced (see
# docs/adr/0008) - and that hourly resolution is now also what the
# demand/supply split itself is computed from (docs/adr/0016).
HOURLY_FLEX_OPTIONS = [
    (flex_option, commodity, spec)
    for flex_option, commodities in FLEX_OPTIONS.items()
    for commodity, spec in commodities.items()
    if spec["kind"] != "system_only"
]


def _filter_area(df: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """Area-substring filter for options split by deployment context (e.g.
    PtH's Industrial/Individual/District split, see
    docs/adr/0017) - "area_contains" keeps only matching rows,
    "area_excludes" drops rows matching any of a list of substrings. No-op
    if spec has neither key. Same logic as flex_option_metrics.py's own
    `_filter_area` - kept as a separate copy since this module only imports
    that one's shared FLEX_OPTIONS/STORAGE_CHARGE_CATEGORIES, not its
    private helpers."""
    if "area_contains" in spec:
        return df[df["Area"].str.contains(spec["area_contains"])]
    if "area_excludes" in spec:
        return df[~df["Area"].str.contains("|".join(spec["area_excludes"]))]
    return df


def _load_ev_dumb_fraction() -> pd.DataFrame:
    """(Year, Region, dumb_fraction) parsed from EV_BEV_dumb.inc - the
    year x region fraction of EV charging that's dumb/inflexible (a lower
    bound on VEV_G2V_BEV, see docs/adr/0016/0017). EV_PHEV_dumb.inc carries
    identical values to EV_BEV_dumb.inc in this dataset (checked directly)
    so only one is read - the aggregated ENDO_EV series has no BEV/PHEV
    split to apply them separately against anyway. Does not apply the
    RollingSeasons=yes x0.1 adjustment EV_BEV_dumb.inc's last line encodes -
    a further reduction on an already-negligible (0.001 in 2050) fraction,
    skipped rather than plumbing rolling/fullyear run-type detection through
    for a sub-0.1% effect."""
    path = Path(__file__).parent.parent / "Balmorel" / "base" / "data" / "EV_BEV_dumb.inc"
    lines = path.read_text().splitlines()
    header_idx = next(i for i, line in enumerate(lines) if line.strip().startswith("TABLE"))
    regions = lines[header_idx + 1].split()
    rows = []
    for line in lines[header_idx + 2:]:
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or stripped.startswith("$"):
            break
        year, *values = stripped.split()
        rows.extend((year, region, float(value)) for region, value in zip(regions, values))
    return pd.DataFrame(rows, columns=["Year", "Region", "dumb_fraction"])


def _split_ev_dumb(
    el: pd.DataFrame, dumb_fraction: pd.DataFrame, scenario_name: str, year: str
) -> tuple:
    """(dumb_hourly, smart_hourly) - raw ENDO_EV (Country, Region, Season,
    Time, Value; demand-table convention, positive = more demand) split by
    `dumb_fraction` (see `_load_ev_dumb_fraction`). `dumb_hourly` is the
    locked-in/inflexible share, taken only from the net-charging part of
    each Region-hour (`Value` clipped to >=0 first - a net-discharging
    Region-hour, i.e. net V2G, has no "dumb charging" to lock in) - this
    moves into residual load's non-dispatchable demand. `smart_hourly` is
    the remainder, still in demand-table convention, that stays genuinely
    flexible for the EV charging/V2G flex options (see docs/adr/0017)."""
    raw = el[
        (el["Scenario"] == scenario_name)
        & (el["Year"].astype(str) == str(year))
        & (el["Category"] == "ENDO_EV")
    ]
    fraction_this_year = dumb_fraction[dumb_fraction["Year"] == str(year)][["Region", "dumb_fraction"]]
    merged = raw.merge(fraction_this_year, on="Region", how="left")
    merged["dumb_fraction"] = merged["dumb_fraction"].fillna(0.0)
    dumb_share = merged["Value"].clip(lower=0) * merged["dumb_fraction"]
    cols = ["Country", "Region", "Season", "Time"]
    dumb_hourly = merged[cols].assign(Value=dumb_share)
    smart_hourly = merged[cols].assign(Value=merged["Value"] - dumb_share)
    return dumb_hourly, smart_hourly


def _get_result_cached(
    res, symbol: str, cache_dir: Path, overwrite: bool
) -> pd.DataFrame:
    """`res.get_result(symbol)`, pickle-cached to `cache_dir/<symbol>.pkl`.
    PRO_YCRAGFST in particular is a large hourly GDX read reused by every
    technology/peaker flex option below, so re-running this script (e.g. to
    tweak a plot) doesn't re-read it from disk every time. Mirrors
    scripts/Balmorel/analysis/analyse.py's module-level `collect_results`
    pickle cache, but self-contained (no click context) and living under
    the (already gitignored) --output-dir."""
    cache_path = cache_dir / f"{symbol}.pkl"
    t_start = time.perf_counter()
    if cache_path.exists() and not overwrite:
        _log(f"Loading {symbol} from cached .pkl file")
        df = pd.read_pickle(cache_path)
        _log(f"  {symbol}: {len(df):,} rows loaded from cache in {time.perf_counter() - t_start:.1f}s")
        return df
    _log(f"Loading {symbol} from Balmorel results (GDX read - not cached yet)")
    df = res.get_result(symbol)
    _log(f"  {symbol}: {len(df):,} rows read from GDX in {time.perf_counter() - t_start:.1f}s")
    t_pickle = time.perf_counter()
    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_pickle(cache_path)
    _log(f"  {symbol}: cached to {cache_path.name} in {time.perf_counter() - t_pickle:.1f}s")
    return df


def country_hourly_demand(
    demand_df: pd.DataFrame, demand_categories: tuple, scenario_name: str, year: str
) -> pd.DataFrame:
    """(Country, Season, Time, Value): non-dispatchable demand (MWh) per
    country-hour, summed over the chosen `demand_categories`. `demand_df` is
    whichever commodity's own hourly demand symbol (EL_DEMAND_YCRST /
    H_DEMAND_YCRAST / H2_DEMAND_YCRST)."""
    query = "Scenario == @scenario_name and Year == @year and Category in @demand_categories"
    return (
        demand_df
        .query(query)
        .groupby(["Country", "Season", "Time"])["Value"]
        .sum()
        .reset_index()
    )


def country_hourly_supply(
    pro: pd.DataFrame, scenario_name: str, year: str
) -> pd.DataFrame:
    """(Country, Season, Time, Value): non-dispatchable supply (MWh) per
    country-hour - wind, solar and run-of-river production. Electricity
    only - see docs/adr/0009."""
    query = "Scenario == @scenario_name and Year == @year and Technology in @NON_DISPATCHABLE_SUPPLY_TECHNOLOGIES"
    return (
        pro
        .query(query)
        .groupby(["Country", "Season", "Time"])["Value"]
        .sum()
        .reset_index()
    )


def country_residual_load(demand: pd.DataFrame, supply: pd.DataFrame) -> pd.DataFrame:
    """(Country, Season, Time, Value): residual load (MWh) = non-dispatchable
    demand minus non-dispatchable supply, per country-hour. A country-hour
    present on only one side is treated as 0 on the other (e.g. a country
    with demand but no modelled wind/solar/run-of-river) - this is also how
    heat/hydrogen residual load (demand only, no supply netting, see
    docs/adr/0009) is computed: `supply` is simply passed in empty."""
    merged = demand.merge(
        supply,
        on=["Country", "Season", "Time"],
        how="outer",
        suffixes=("_demand", "_supply"),
    ).fillna(0).infer_objects(copy=False)
    merged["Value"] = merged["Value_demand"] - merged["Value_supply"]
    return merged[["Country", "Season", "Time", "Value"]]


def _net_hourly(supply: pd.DataFrame, demand: pd.DataFrame) -> pd.DataFrame:
    """(Country, Season, Time, Value): supply minus demand, per country-hour
    - the commodity-signed net hourly series for one flex option's own
    dispatch (see CONTEXT.md's "Commodity-signed flex value",
    docs/adr/0008). Either side may be `_EMPTY_HOURLY` for a
    single-directional option (e.g. heat pumps have no "supply" component
    on the electricity view)."""
    merged = supply.merge(
        demand,
        on=["Country", "Season", "Time"],
        how="outer",
        suffixes=("_supply", "_demand"),
    ).fillna(0).infer_objects(copy=False)
    merged["Value"] = merged["Value_supply"] - merged["Value_demand"]
    return merged[["Country", "Season", "Time", "Value"]]


def _period_means(hourly: pd.DataFrame) -> pd.DataFrame:
    """`hourly` (Season, Time, Value) with Day/daily_mean/weekly_mean/
    annual_mean columns added, one row per hour - the shared building block
    for `flexibility_needs()` (sign-invariant need) and `flex_sign()`/
    `flexibility_provision()` (Geis et al. 2026's correlation-based signed
    decomposition, see docs/adr/0017)."""
    hour_in_week = hourly["Time"].str[1:].astype(int)
    day = hourly["Season"] + "-D" + (((hour_in_week - 1) // 24) + 1).astype(str)

    working = hourly.assign(Day=day)
    working["daily_mean"] = working.groupby("Day")["Value"].transform("mean")
    working["weekly_mean"] = working.groupby("Season")["Value"].transform("mean")
    working["annual_mean"] = working["Value"].mean()
    return working


def flexibility_needs(hourly: pd.DataFrame) -> dict:
    """Daily/Weekly/Annual flexibility need (TWh) for one group's hourly
    series (Season, Time, Value - Season = calendar week S01-S52, Time =
    hour-in-week T001-T168, per this Balmorel setup's chronological
    fullyear/rolling grid). Works the same whether `Value` is residual load
    or a flex option's own commodity-signed net dispatch - only the
    variability (half the summed absolute deviation) is reported, so sign
    doesn't change the result, only what physical series it was computed
    from.

    Follows Geis et al. (2026)'s hierarchical decomposition: each timescale's
    need is half the summed absolute deviation between one resolution's mean
    and the next coarser one, always summed over the full hourly grid so
    variability already captured at a finer timescale isn't double-counted -
    see docs/adr/0006."""
    working = _period_means(hourly)
    mwh_to_twh = 1e-6
    return {
        "Daily": 0.5
        * (working["Value"] - working["daily_mean"]).abs().sum()
        * mwh_to_twh,
        "Weekly": 0.5
        * (working["daily_mean"] - working["weekly_mean"]).abs().sum()
        * mwh_to_twh,
        "Annual": 0.5 * (working["weekly_mean"] - working["annual_mean"]).abs().sum() * mwh_to_twh,
    }


def flex_sign(hourly: pd.DataFrame) -> pd.DataFrame:
    """(Season, Time, Daily, Weekly, Annual) - one group's (system/category)
    own FlexSign at each timescale, from its own residual load (Geis et al.
    2026's FlexSign^{l|h}(t) = sign(FlexCurve^{l|h}(t)), see docs/adr/0017).
    Used to weight every flex option's own deviation curve in
    `flexibility_provision()` - the *system's* sign, not the option's own."""
    working = _period_means(hourly)
    return pd.DataFrame({
        "Season": working["Season"],
        "Time": working["Time"],
        "Daily": np.sign(working["Value"] - working["daily_mean"]),
        "Weekly": np.sign(working["daily_mean"] - working["weekly_mean"]),
        "Annual": np.sign(working["weekly_mean"] - working["annual_mean"]),
    })


def flexibility_provision(hourly: pd.DataFrame, sign: pd.DataFrame) -> dict:
    """Daily/Weekly/Annual flexibility *provision* (TWh) of one flex
    option's own hourly series, weighted by `sign` (that group's own
    FlexSign, from `flex_sign()` on its residual load) rather than a fixed
    per-option sign - Geis et al. (2026) eq. 3-4. Positive when the
    option's own deviation aligns with what the system needs at that hour,
    negative when it opposes, regardless of the option's nominal
    supply/demand role. Exactly additive with `flexibility_needs()` across
    every tracked option plus an explicit "Other" residual, by construction
    (Geis's Appendix A.1) - see docs/adr/0017.

    `hourly` is reindexed onto `sign`'s own (Season, Time) domain - always
    the complete 8736-hour grid, since `sign` comes from residual load,
    which never has an all-countries-zero hour - and zero-filled before
    `_period_means` runs. GDX never stores true zeros, so an option that's
    genuinely zero everywhere at some hour (e.g. Peaker/backup only firing
    304 of 8736 hours, or Nuclear off for maintenance) has that hour
    *missing* from its own table rather than present as 0; averaging over
    only the hours where a sparse option happens to have a row - instead of
    over the full year, with the silent hours correctly counted as
    contributing 0 - inflates its daily/weekly/annual means (dividing by
    however many hours happen to be present instead of by 24/168/8736),
    which biases its deviations, sign-alignment, and hence its provision at
    every timescale. Confirmed empirically: for base_R2050/ELECTRICITY this
    was the entire "Other" catch-all - zero-filling before decomposing
    reduces Other to exact-zero (to float precision) at all three
    timescales, with no missing flex option or sign-correlation effect
    involved."""
    hourly = (
        sign[["Season", "Time"]]
        .merge(hourly, on=["Season", "Time"], how="left")
        .fillna(0)
        .infer_objects(copy=False)
    )
    working = (
        _period_means(hourly)
        .merge(sign, on=["Season", "Time"], how="left")
        .fillna(0)
        .infer_objects(copy=False)
    )
    mwh_to_twh = 1e-6
    return {
        "Daily": 0.5
        * ((working["Value"] - working["daily_mean"]) * working["Daily"]).sum()
        * mwh_to_twh,
        "Weekly": 0.5
        * ((working["daily_mean"] - working["weekly_mean"]) * working["Weekly"]).sum()
        * mwh_to_twh,
        "Annual": 0.5
        * ((working["weekly_mean"] - working["annual_mean"]) * working["Annual"]).sum()
        * mwh_to_twh,
    }


def _needs_rows(
    hourly: pd.DataFrame,
    scenario_name: str,
    year: str,
    group_type: str,
    group: str,
    commodity: str,
    flex_option: str = "",
) -> pd.DataFrame:
    if hourly.empty:
        return pd.DataFrame(columns=NEEDS_COLUMNS)
    needs = flexibility_needs(hourly)
    return _needs_rows_from_dict(needs, scenario_name, year, group_type, group, commodity, flex_option)


def _needs_rows_from_dict(
    needs: dict,
    scenario_name: str,
    year: str,
    group_type: str,
    group: str,
    commodity: str,
    flex_option: str = "",
) -> pd.DataFrame:
    return pd.DataFrame({
        "Scenario": scenario_name,
        "Year": year,
        "group_type": group_type,
        "group": group,
        "category": "",
        "flex_option": flex_option,
        "Commodity": commodity,
        "timescale": list(needs.keys()),
        "flex_need_twh": list(needs.values()),
    })


def build_system_table(
    rl: pd.DataFrame, commodity: str, scenario_name: str, year: str
) -> pd.DataFrame:
    """Aggregate flexibility need summed across every country in `rl` *before*
    decomposition - one system-wide hourly residual load series. This is the
    "copper-plate" bound, not a system-wide truth - see module docstring and
    docs/adr/0020 for why `plot_flexibility_needs.py` also derives a
    disaggregated system view by summing `build_country_table`'s own rows
    instead."""
    hourly = rl.groupby(["Season", "Time"])["Value"].sum().reset_index()
    return _needs_rows(
        hourly,
        scenario_name,
        year,
        group_type="system_aggregate",
        group="All",
        commodity=commodity,
    )


def build_category_table(
    rl: pd.DataFrame, category_map: dict, commodity: str, scenario_name: str, year: str
) -> pd.DataFrame:
    """Aggregate flexibility need per Combined category - each category's
    hourly residual load is its member countries' (fixed via `category_map`,
    see docs/adr/0004) hourly residual load summed together *before*
    decomposition - the same copper-plate bound as `build_system_table`, one
    level down. See docs/adr/0020."""
    categorized = rl.assign(combined_category=rl["Country"].map(category_map)).dropna(
        subset=["combined_category"]
    )
    tables = []
    for group, group_rl in categorized.groupby("combined_category"):
        hourly = group_rl.groupby(["Season", "Time"])["Value"].sum().reset_index()
        tables.append(
            _needs_rows(
                hourly,
                scenario_name,
                year,
                group_type="category_aggregate",
                group=group,
                commodity=commodity,
            )
        )
    return (
        pd.concat(tables, ignore_index=True)
        if tables
        else pd.DataFrame(columns=NEEDS_COLUMNS)
    )


def build_country_table(
    rl: pd.DataFrame, category_map: dict, commodity: str, scenario_name: str, year: str
) -> pd.DataFrame:
    """Flexibility need per individual country, decomposed before any
    spatial summing - table rows only (no plot, see docs/adr/0006/
    CONTEXT.md), to avoid one PNG per country. Carries a `category` column
    (that country's Combined-category membership, from `category_map`) so
    `plot_flexibility_needs.py` can roll these rows up into system-wide or
    category-level "disaggregated" totals itself, without its own GDX
    dependency - see docs/adr/0012, docs/adr/0020. A country absent from
    `category_map` gets `category=""`, not dropped - unlike
    `build_category_table`, system/country-level rows don't depend on
    category membership to be meaningful."""
    tables = [
        _needs_rows(
            group_rl[["Season", "Time", "Value"]],
            scenario_name,
            year,
            group_type="country",
            group=country,
            commodity=commodity,
        ).assign(category=category_map.get(country, ""))
        for country, group_rl in rl.groupby("Country")
    ]
    return (
        pd.concat(tables, ignore_index=True)
        if tables
        else pd.DataFrame(columns=NEEDS_COLUMNS)
    )


def flex_option_hourly_net(
    spec: dict,
    commodity: str,
    pro: pd.DataFrame,
    f_cons: pd.DataFrame,
    demand_symbols: dict,
    x_flow: pd.DataFrame,
    xh2_flow: pd.DataFrame,
    region_to_country: dict,
    scenario_name: str,
    year: str,
    ev_smart_hourly: pd.DataFrame = None,
) -> pd.DataFrame:
    """(Country, Season, Time, Value): one flex option's own commodity-signed
    net hourly dispatch (supply minus demand - positive when it injects into
    `commodity`'s balance, negative when it withdraws, see CONTEXT.md's
    "Commodity-signed flex value" and docs/adr/0008) - the same shape as
    `country_hourly_supply`'s output, so `flexibility_needs()`/
    `flexibility_provision()` decompose it the same hierarchical way as
    residual load. Transmission is the one exception to the "Commodity-signed
    flex value" convention's own sourcing: it's signed by net import minus
    export here, not unsigned utilisation as in flex_option_metrics.py (see
    docs/adr/0019). Only called for `HOURLY_FLEX_OPTIONS`. `demand_symbols`
    is {"ELECTRICITY": el, "HEAT": h, "HYDROGEN": h2} - each commodity's own
    hourly non-dispatchable-demand symbol, reused here to source storage's
    charging side, electrolysers' consumption (via "hourly_category"), and
    EV's net side. `ev_smart_hourly` - only used for
    `spec["category"] == "ENDO_EV"` - is the flexible/smart residual of
    ENDO_EV after `_split_ev_dumb` removes the dumb/inflexible share (see
    docs/adr/0017); when None, falls back to the raw category (used for
    commodities/specs where the split doesn't apply)."""
    kind = spec["kind"]

    # Boolean indexing throughout, not `.query("... == @scenario_name ...")`
    # - pandas' query engine resolves `@name` by inspecting the calling
    # frame, which does not reliably see a nested closure's free variables
    # (confirmed: raises UndefinedVariableError from within `_tech_rows`).

    def _scenario_year(df: pd.DataFrame) -> pd.DataFrame:
        return df[(df["Scenario"] == scenario_name) & (df["Year"] == year)]

    def _tech_rows(df: pd.DataFrame) -> pd.DataFrame:
        sub = _scenario_year(df)
        sub = sub[
            (sub["Commodity"] == commodity)
            & (sub["Technology"].isin(spec["technologies"]))
        ]
        if "fuels" in spec:
            sub = sub[sub["Fuel"].isin(spec["fuels"])]
        if "exclude_fuels" in spec:
            sub = sub[~sub["Fuel"].isin(spec["exclude_fuels"])]
        if spec.get("exclude_backup"):
            sub = sub[~sub["Generation"].str.contains("BACKUP")]
        sub = _filter_area(sub, spec)
        return sub.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()

    if kind == "production":
        return _net_hourly(_tech_rows(pro), _EMPTY_HOURLY)

    if kind == "consumption":
        if "hourly_category" in spec:
            # Electrolysers: sourced from EL_DEMAND_YCRST's own ENDO_H2
            # category rather than F_CONS_YCRAST, guaranteeing by
            # construction that this exactly offsets what residual load
            # excludes (see docs/adr/0017) - unlike PtH
            # below, which needs F_CONS_YCRAST's Area column for its
            # Industrial/Individual/District split (EL_DEMAND_YCRST has no
            # Area column to split on).
            sub = _scenario_year(demand_symbols[commodity])
            sub = sub[sub["Category"] == spec["hourly_category"]]
            demand = sub.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()
        else:
            sub = _scenario_year(f_cons)
            sub = sub[
                (sub["Technology"].isin(spec["technologies"]))
                & (sub["Fuel"] == spec.get("fuel", "ELECTRIC"))
            ]
            sub = _filter_area(sub, spec)
            demand = sub.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()
        return _net_hourly(_EMPTY_HOURLY, demand)

    if kind == "storage":
        supply = _tech_rows(pro)
        dem = _scenario_year(demand_symbols[commodity])
        dem = dem[dem["Category"].isin(STORAGE_CHARGE_CATEGORIES)]
        demand = dem.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()
        return _net_hourly(supply, demand)

    if kind == "transmission":
        flow = x_flow if spec["use_symbol"] == "X_FLOW_YCR" else xh2_flow
        df = _scenario_year(flow)
        # Net cross-border position per country-hour: import (flow arriving
        # into one of this country's regions, via `To`) minus export (flow
        # leaving from one of this country's own regions - `Country` is
        # always the *exporting* region's country on this symbol, confirmed
        # against real GDX output, see docs/adr/0019 - unlike
        # flex_option_metrics.py's own unsigned utilisation view of the same
        # symbol, see docs/adr/0008). Intra-country flow (e.g. NO1->NO2)
        # cancels to zero at the country level automatically, which is
        # correct - only cross-border flow should move a country's own
        # residual-load balance.
        export = df.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()
        import_ = (
            df
            .assign(Country=df["To"].map(region_to_country))
            .dropna(subset=["Country"])
            .groupby(["Country", "Season", "Time"])["Value"]
            .sum()
            .reset_index()
        )
        return _net_hourly(import_, export)

    if kind == "net_category_signed":
        # Split at raw Region-hour resolution, before any Country/Season/
        # Time aggregation - see flex_option_metrics.py's FLEX_OPTIONS
        # docstring and docs/adr/0016. Only one already-net GAMS variable
        # exists (ENDO_EV); clipping approximates gross demand/supply, and
        # understates whichever side loses a tie within one Region-hour of
        # simultaneous charging and discharging. `ev_smart_hourly`, when
        # given, is already the dumb-share-removed residual (see
        # docs/adr/0017) - still in raw demand-table convention, so the
        # sign flip/clip below applies unchanged.
        if spec.get("category") == "ENDO_EV" and ev_smart_hourly is not None:
            dem = ev_smart_hourly
        else:
            dem = _scenario_year(demand_symbols[commodity])
            dem = dem[dem["Category"] == spec["category"]]
        dem = dem.assign(
            Value=dem["Value"] * -1
        )  # demand-table convention ("more demand" = positive) -> "positive = supply"
        dem = dem.assign(
            Value=dem["Value"].clip(lower=0)
            if spec["direction"] == "supply"
            else dem["Value"].clip(upper=0)
        )
        return dem.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()

    if kind == "peaker":
        backup = backup_production(_scenario_year(pro), commodity=commodity)
        df = backup.assign(Country=backup["Region"].map(region_to_country)).dropna(
            subset=["Country"]
        )
        supply = df.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()
        return _net_hourly(supply, _EMPTY_HOURLY)

    raise ValueError(
        f"{kind!r} has no hourly resolution for flexibility-need decomposition"
    )


def build_flex_option_system_table(
    hourly_net: pd.DataFrame,
    sign: pd.DataFrame,
    flex_option: str,
    commodity: str,
    scenario_name: str,
    year: str,
) -> pd.DataFrame:
    """Aggregate Daily/Weekly/Annual flexibility *provision* (see
    docs/adr/0017) of one flex option's own commodity-signed net hourly
    dispatch, summed across every country *before* decomposition, weighted
    by the system's own FlexSign (`sign`, from residual load - see
    `flex_sign`) rather than a fixed per-option sign - system-wide
    equivalent of `build_system_table`, but the signal is the option's own
    operation, not residual load. Shares `build_system_table`'s
    copper-plate bound (see docs/adr/0020) - `build_flex_option_country_table`
    is the per-country counterpart `plot_flexibility_needs.py` sums for a
    disaggregated view instead."""
    hourly = hourly_net.groupby(["Season", "Time"])["Value"].sum().reset_index()
    provision = flexibility_provision(hourly, sign)
    return _needs_rows_from_dict(
        provision,
        scenario_name,
        year,
        group_type="flex_option_system_aggregate",
        group="All",
        commodity=commodity,
        flex_option=flex_option,
    )


def build_flex_option_category_table(
    hourly_net: pd.DataFrame,
    category_map: dict,
    signs: dict,
    flex_option: str,
    commodity: str,
    scenario_name: str,
    year: str,
) -> pd.DataFrame:
    """Category-level equivalent of `build_flex_option_system_table` - each
    category weighted by that category's own FlexSign (`signs[group]`), not
    a system-wide one, so category bars stay additive to that category's own
    Total Flexibility Needs line (see docs/adr/0017). Categories with no
    computed sign (i.e. absent from residual load's own categorization,
    should not normally happen since both are keyed off the same
    `category_map`) are skipped rather than raising. Shares
    `build_category_table`'s copper-plate bound (see docs/adr/0020)."""
    categorized = hourly_net.assign(
        combined_category=hourly_net["Country"].map(category_map)
    ).dropna(subset=["combined_category"])
    tables = []
    for group, group_use in categorized.groupby("combined_category"):
        if group not in signs:
            continue
        hourly = group_use.groupby(["Season", "Time"])["Value"].sum().reset_index()
        provision = flexibility_provision(hourly, signs[group])
        tables.append(
            _needs_rows_from_dict(
                provision,
                scenario_name,
                year,
                group_type="flex_option_category_aggregate",
                group=group,
                commodity=commodity,
                flex_option=flex_option,
            )
        )
    return (
        pd.concat(tables, ignore_index=True)
        if tables
        else pd.DataFrame(columns=NEEDS_COLUMNS)
    )


def build_flex_option_country_table(
    hourly_net: pd.DataFrame,
    category_map: dict,
    signs: dict,
    flex_option: str,
    commodity: str,
    scenario_name: str,
    year: str,
) -> pd.DataFrame:
    """Country-level equivalent of `build_flex_option_category_table` - each
    country weighted by that country's own FlexSign (`signs[country]`), so
    country rows stay additive to that country's own Total Flexibility Needs
    line (`build_country_table`'s own residual-load need) - the disaggregated
    counterpart to `build_flex_option_system_table`/
    `build_flex_option_category_table`'s copper-plate bound, see
    docs/adr/0020. Countries with no computed sign are skipped rather than
    raising, same as the category version. Table rows only, no dedicated
    plot by default (mirrors `build_country_table`'s own "no PNG per
    country" precedent) - `plot_flexibility_needs.py` derives its
    disaggregated system/category-by-option plots by summing these rows,
    using `category` for the category rollup, and can optionally plot a
    single country's own rows on request."""
    tables = []
    for country, group_use in hourly_net.groupby("Country"):
        if country not in signs:
            continue
        hourly = group_use.groupby(["Season", "Time"])["Value"].sum().reset_index()
        provision = flexibility_provision(hourly, signs[country])
        tables.append(
            _needs_rows_from_dict(
                provision,
                scenario_name,
                year,
                group_type="flex_option_country",
                group=country,
                commodity=commodity,
                flex_option=flex_option,
            ).assign(category=category_map.get(country, ""))
        )
    return (
        pd.concat(tables, ignore_index=True)
        if tables
        else pd.DataFrame(columns=NEEDS_COLUMNS)
    )



# ------------------------------- #
#            2. Main              #
# ------------------------------- #


@click.command()
@click.option(
    "--balmorel-path",
    type=str,
    default="scripts/Balmorel",
    help="Path to the top level of Balmorel scenario folders",
)
@click.option(
    "--gams-sysdir",
    type=str,
    default=config("GAMS_SYSTEM_DIR", default=None),
    help="Path to GAMS system directory",
)
@click.option(
    "--output-dir",
    type=str,
    default="build_postprocess",
    help="Where to write flexibility_needs.csv (and cache read GDX symbols under .gdx_cache/). "
    "Plotting it is a separate step - see plot_flexibility_needs.py.",
)
@click.option(
    "--categorization-csv",
    type=str,
    default=None,
    help="Path to categorize_countries.py's output. Defaults to <output-dir>/categorization.csv",
)
@click.option(
    "--reference-scenario",
    type=str,
    default="base_R2050",
    help="Scenario whose Combined category assignment is fixed and reused for every scenario (see docs/adr/0004)",
)
@click.option(
    "--years",
    multiple=True,
    default=(),
    help="Restrict to these target year(s) (e.g. 2050). Default: all found.",
)
@click.option(
    "--scenarios",
    multiple=True,
    default=(),
    help="Restrict to these scenario name(s) (e.g. --scenarios ELN_R2050) for local testing. "
    "Default ('all', i.e. every fullyear/rolling scenario result found under --balmorel-path) is expensive: "
    "Balmorel.collect_results() opens a GAMS database per scenario *folder* it locates, not per scenario "
    "name, regardless of any filtering done afterwards - so this option prunes which folders get located "
    "in the first place, before collect_results() runs, rather than filtering the resulting DataFrames.",
)
@click.option(
    "--overwrite-cache",
    is_flag=True,
    default=False,
    help="Re-read PRO_YCRAGFST/X_FLOW_YCRST/XH2_FLOW_YCRST/etc. from GDX instead of <output-dir>/.gdx_cache/*.pkl "
    "(stale after new HPC results are synced down for the same scenario names).",
)
def main(
    balmorel_path: str,
    gams_sysdir: str,
    output_dir: str,
    categorization_csv: str,
    reference_scenario: str,
    years: tuple,
    scenarios: tuple,
    overwrite_cache: bool,
):
    _log("estimate_flexibility_needs.py starting")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    table_path = output_path / "flexibility_needs.csv"
    cache_dir = output_path / ".gdx_cache"

    categorization_path = (
        Path(categorization_csv)
        if categorization_csv
        else output_path / "categorization.csv"
    )
    if not categorization_path.exists():
        print(
            f"{categorization_path} not found - run categorize_countries.py first. Nothing to compute."
        )
        pd.DataFrame(columns=NEEDS_COLUMNS).to_csv(table_path, index=False)
        return

    categorization = pd.read_csv(categorization_path)
    category_map = build_reference_category_map(categorization, reference_scenario)
    if not category_map:
        print(
            f"Reference scenario {reference_scenario!r} not found in {categorization_path}. Category-level needs will be empty."
        )

    if not any(Path(balmorel_path).glob("*/model/MainResults_*.gdx")):
        print(
            f"No MainResults*.gdx files found under {balmorel_path} - nothing to compute yet."
        )
        pd.DataFrame(columns=NEEDS_COLUMNS).to_csv(table_path, index=False)
        return

    _log(f"Scanning {balmorel_path!r} for scenario folders")
    t_scan = time.perf_counter()
    model = Balmorel(balmorel_path, gams_system_directory=gams_sysdir)
    _log(f"Found {len(model.scenarios)} scenario folder(s) in {time.perf_counter() - t_scan:.1f}s")
    if scenarios:
        # locate_results() alone is cheap (filenames only, no GDX read -
        # see AGENTS.md's pybalmorel note) - used here only to resolve
        # which scenario *folder* each requested scenario name lives in,
        # so `model.scenarios` can be pruned before collect_results()
        # re-locates and opens a GAMS database per remaining folder.
        t_locate = time.perf_counter()
        model.locate_results(suffix_naming_only=True)
        _log(f"locate_results() (filenames only) done in {time.perf_counter() - t_locate:.1f}s")
        missing = set(scenarios) - set(model.scname_to_scfolder)
        if missing:
            print(f"Requested --scenarios not found, ignoring: {sorted(missing)}")
        wanted_folders = {
            model.scname_to_scfolder[s] for s in scenarios if s in model.scname_to_scfolder
        }
        model.scenarios = [SC for SC in model.scenarios if SC in wanted_folders]
        _log(f"Pruned to {len(model.scenarios)} scenario folder(s) matching --scenarios")

    _log("collect_results() starting - opens a GAMS database per remaining scenario folder")
    t_collect = time.perf_counter()
    model.collect_results(suffix_naming_only=True)
    _log(f"collect_results() done in {time.perf_counter() - t_collect:.1f}s")
    res = model.results

    el = _get_result_cached(res, "EL_DEMAND_YCRST", cache_dir, overwrite_cache)
    h = _get_result_cached(res, "H_DEMAND_YCRAST", cache_dir, overwrite_cache)
    h2 = _get_result_cached(res, "H2_DEMAND_YCRST", cache_dir, overwrite_cache)
    pro = _get_result_cached(res, "PRO_YCRAGFST", cache_dir, overwrite_cache)
    f_cons = _get_result_cached(res, "F_CONS_YCRAST", cache_dir, overwrite_cache)
    x_flow = _get_result_cached(res, "X_FLOW_YCRST", cache_dir, overwrite_cache)
    xh2_flow = _get_result_cached(res, "XH2_FLOW_YCRST", cache_dir, overwrite_cache)
    region_to_country = region_to_country_map(pro)
    demand_symbols = {"ELECTRICITY": el, "HEAT": h, "HYDROGEN": h2}
    ev_dumb_fraction = _load_ev_dumb_fraction()

    scenario_names = select_scenario_names(model.scenario_names)
    _log(
        f"Estimating flexibility needs for {len(scenario_names)} fullyear/rolling scenario result(s): {scenario_names}"
    )

    tables = []
    for scenario_i, scenario_name in enumerate(scenario_names, start=1):
        t_scenario = time.perf_counter()
        _log(f"[{scenario_i}/{len(scenario_names)}] {scenario_name}: starting")
        year = scenario_target_year(el, scenario_name=scenario_name)
        if year is None:
            _log(f"[{scenario_i}/{len(scenario_names)}] {scenario_name}: no target year found, skipping")
            continue

        dumb_hourly, smart_hourly = _split_ev_dumb(el, ev_dumb_fraction, scenario_name, year)
        dumb_country_hourly = (
            dumb_hourly.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()
        )

        for commodity in COMMODITIES:
            t_commodity = time.perf_counter()
            if commodity == "ELECTRICITY":
                demand = country_hourly_demand(
                    el, ELECTRICITY_NON_FLEX_DEMAND_CATEGORIES, scenario_name, year
                )
                demand = (
                    pd.concat([demand, dumb_country_hourly])
                    .groupby(["Country", "Season", "Time"])["Value"]
                    .sum()
                    .reset_index()
                )
                supply = country_hourly_supply(pro, scenario_name, year)
            else:
                # No non-dispatchable supply on the heat/hydrogen side - see
                # docs/adr/0009 - so `supply` is left empty and residual
                # load is just non-dispatchable demand.
                demand = country_hourly_demand(
                    demand_symbols[commodity],
                    NON_ELECTRICITY_DEMAND_CATEGORIES,
                    scenario_name,
                    year,
                )
                supply = _EMPTY_HOURLY
            if demand.empty and supply.empty:
                continue
            rl = country_residual_load(demand, supply)

            tables.append(build_system_table(rl, commodity, scenario_name, year))
            tables.append(
                build_category_table(
                    rl, category_map, commodity, scenario_name, year
                )
            )
            tables.append(
                build_country_table(rl, category_map, commodity, scenario_name, year)
            )

            # Per-group FlexSign/need (system/category/country), each from
            # that group's own residual load - not one system-wide value
            # broadcast to every group - so every group's tracked flex
            # options plus its "Other" bucket sum back to that group's own
            # Total Flexibility Needs (see docs/adr/0017). system/category
            # are the aggregate (copper-plate) bound; country is the
            # disaggregated one - see docs/adr/0020.
            system_hourly_rl = rl.groupby(["Season", "Time"])["Value"].sum().reset_index()
            system_sign = flex_sign(system_hourly_rl)
            system_need = flexibility_needs(system_hourly_rl)

            categorized_rl = rl.assign(
                combined_category=rl["Country"].map(category_map)
            ).dropna(subset=["combined_category"])
            category_signs = {}
            category_needs = {}
            for group, group_rl in categorized_rl.groupby("combined_category"):
                group_hourly_rl = group_rl.groupby(["Season", "Time"])["Value"].sum().reset_index()
                category_signs[group] = flex_sign(group_hourly_rl)
                category_needs[group] = flexibility_needs(group_hourly_rl)

            country_signs = {}
            country_needs = {}
            for country, group_rl in rl.groupby("Country"):
                group_hourly_rl = group_rl.groupby(["Season", "Time"])["Value"].sum().reset_index()
                country_signs[country] = flex_sign(group_hourly_rl)
                country_needs[country] = flexibility_needs(group_hourly_rl)

            system_tracked = {"Daily": 0.0, "Weekly": 0.0, "Annual": 0.0}
            category_tracked = {
                group: {"Daily": 0.0, "Weekly": 0.0, "Annual": 0.0} for group in category_needs
            }
            country_tracked = {
                country: {"Daily": 0.0, "Weekly": 0.0, "Annual": 0.0} for country in country_needs
            }

            for flex_option, spec in (
                (fo, s) for fo, com, s in HOURLY_FLEX_OPTIONS if com == commodity
            ):
                t_option = time.perf_counter()
                hourly_net = flex_option_hourly_net(
                    spec,
                    commodity,
                    pro,
                    f_cons,
                    demand_symbols,
                    x_flow,
                    xh2_flow,
                    region_to_country,
                    scenario_name,
                    year,
                    ev_smart_hourly=smart_hourly if spec.get("category") == "ENDO_EV" else None,
                )
                if hourly_net.empty:
                    continue

                system_table = build_flex_option_system_table(
                    hourly_net, system_sign, flex_option, commodity, scenario_name, year
                )
                tables.append(system_table)
                for ts, value in zip(system_table["timescale"], system_table["flex_need_twh"]):
                    system_tracked[ts] += value

                category_table = build_flex_option_category_table(
                    hourly_net,
                    category_map,
                    category_signs,
                    flex_option,
                    commodity,
                    scenario_name,
                    year,
                )
                tables.append(category_table)
                for group, ts, value in zip(
                    category_table["group"], category_table["timescale"], category_table["flex_need_twh"]
                ):
                    category_tracked[group][ts] += value

                country_table = build_flex_option_country_table(
                    hourly_net,
                    category_map,
                    country_signs,
                    flex_option,
                    commodity,
                    scenario_name,
                    year,
                )
                tables.append(country_table)
                for country, ts, value in zip(
                    country_table["group"], country_table["timescale"], country_table["flex_need_twh"]
                ):
                    country_tracked[country][ts] += value

                _log(
                    f"    [{scenario_name}/{commodity}] flex_option={flex_option!r}: "
                    f"done in {time.perf_counter() - t_option:.2f}s "
                    f"({hourly_net['Country'].nunique()} country-hour row(s): {len(hourly_net):,})"
                )

            # "Other": whatever's left unattributed after every tracked flex
            # option, computed the same way as any other technology (as a
            # residual of the already-additive FlexNeed/FlexProv numbers,
            # exploiting linearity) rather than silently omitted - a safety
            # net for exact additivity regardless of whether FLEX_OPTIONS is
            # a perfectly exhaustive partition (see docs/adr/0017). Computed
            # at all three levels - country-level "Other" is what a future
            # investigation into its actual composition would start from
            # (deferred, see docs/adr/0020's Consequences).
            other_system = {ts: system_need[ts] - system_tracked[ts] for ts in system_need}
            tables.append(
                _needs_rows_from_dict(
                    other_system, scenario_name, year, "flex_option_system_aggregate", "All", commodity, "Other"
                )
            )
            for group, needs in category_needs.items():
                other_category = {
                    ts: needs[ts] - category_tracked[group][ts] for ts in needs
                }
                tables.append(
                    _needs_rows_from_dict(
                        other_category, scenario_name, year, "flex_option_category_aggregate", group, commodity, "Other"
                    )
                )
            for country, needs in country_needs.items():
                other_country = {
                    ts: needs[ts] - country_tracked[country][ts] for ts in needs
                }
                tables.append(
                    _needs_rows_from_dict(
                        other_country, scenario_name, year, "flex_option_country", country, commodity, "Other"
                    ).assign(category=category_map.get(country, ""))
                )

            _log(
                f"  [{scenario_name}] commodity={commodity}: "
                f"done in {time.perf_counter() - t_commodity:.1f}s"
            )

        _log(f"[{scenario_i}/{len(scenario_names)}] {scenario_name}: done in {time.perf_counter() - t_scenario:.1f}s")

    _log(f"All scenarios processed - writing {table_path}")
    tidy = (
        pd.concat(tables, ignore_index=True)
        if tables
        else pd.DataFrame(columns=NEEDS_COLUMNS)
    )
    if years:
        tidy = tidy[tidy["Year"].astype(str).isin([str(y) for y in years])]
    tidy.to_csv(table_path, index=False)
    _log(f"Wrote {len(tidy)} row(s) to {table_path}. Plot with plot_flexibility_needs.py.")


if __name__ == "__main__":
    main()
