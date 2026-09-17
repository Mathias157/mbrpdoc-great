"""
Illustrate Interannual Flexibility Need/Provision (across weather years)

The Interannual counterpart to illustrate_flexibility_needs.py: same visual
language (Geis et al. 2026's Fig. 1/Fig. 2 style - a series against its own
mean, shaded above/below, and a flex option's own FlexSign-weighted
contribution as bars), but one point per *weather year* rather than one
point per hour/day/week - so an interannual_annual_means.csv-derived pooled
number (see docs/adr/0023/0024/0026) can be checked against the actual
per-year shape it came from, the same way illustrate_flexibility_needs.py
lets a Daily/Weekly/Annual number be checked. Recomputes its own pooling
here from `.gdx_cache` directly (never reads either interannual CSV) - see
this module's own `_interannual_need`/`_interannual_provision`, the same
math plot_flexibility_needs.py's own `_pool_interannual` uses.

Deliberately a *separate script* from illustrate_flexibility_needs.py, not a
mode of it (same reasoning as docs/adr/0018 for why that script itself is
separate) - the two have genuinely different data-access shapes: one
scenario folder, read fresh, vs. up to dozens of weather-year folders. See
docs/adr/0025 for why this script also deliberately breaks from
illustrate_flexibility_needs.py's own no-cache philosophy and reads from
estimate_flexibility_needs.py's per-folder .gdx_cache instead - a fresh read
of every weather year in an ensemble is a many-minutes operation, not the
single-scenario tool's few-seconds one, and estimate_flexibility_needs.py has
almost always already built that cache by the time anyone wants this
illustration.

Reuses illustrate_flexibility_needs.py's own `_plot_deviation`/
`_plot_contribution` (generic over what `x`/`finer`/`coarser`/`contribution`
mean - never hard-coded to hourly/daily/weekly) and estimate_flexibility_
needs.py's own residual-load/flex-option construction, so this can't
silently drift from what a pooled interannual number reports, the same
guarantee illustrate_flexibility_needs.py already gives for the other three
timescales.

Requires estimate_flexibility_needs.py to have already run for this scenario
set (--output-dir's .gdx_cache must have every requested weather year's
folder cached, per symbol) - this script never reads GDX itself, see
docs/adr/0025.

Run via the illustrate-flex-interannual pixi task, e.g.:

    pixi run illustrate-flex-interannual --source-scenario base --run-type F \
        --commodity ELECTRICITY --group-type system \
        --flex-option "Electricity storage"

Created on 17.09.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import sys
from pathlib import Path

# Add repo root to path for scripts.postprocessing.* imports (see AGENTS.md's
# pybalmorel/import-path note) - importing estimate_flexibility_needs below
# additionally puts the Balmorel submodule's analysis/ dir on sys.path itself,
# as a side effect of that module's own top-of-file sys.path.insert.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from decouple import config
from pybalmorel import Balmorel

from scripts.postprocessing.aggregate_category_costs import build_reference_category_map
from scripts.postprocessing.categorize_countries import (
    RUN_TYPE_RE,
    region_to_country_map,
    scenario_target_year,
    split_weather_year,
)
from scripts.postprocessing.estimate_flexibility_needs import (
    _EMPTY_HOURLY,
    COMMODITIES,
    ELECTRICITY_NON_FLEX_DEMAND_CATEGORIES,
    NON_ELECTRICITY_DEMAND_CATEGORIES,
    _annual_mean_aligned,
    _folder_cache_path,
    _load_ev_dumb_fraction,
    _split_ev_dumb,
    country_hourly_demand,
    country_hourly_supply,
    country_residual_load,
    flex_option_hourly_net,
    flex_sign,
)
from scripts.postprocessing.flex_option_metrics import FLEX_OPTIONS
from scripts.postprocessing.illustrate_flexibility_needs import (
    _group_hourly,
    _plot_contribution,
    _plot_deviation,
)

# HOURS_PER_WEATHER_YEAR/pooling math moved out of estimate_flexibility_
# needs.py into plot_flexibility_needs.py (see docs/adr/0026) - imported
# from there rather than duplicated a third time, since this script already
# depends on that module for FLEX_OPTION_COLOURS.
from scripts.postprocessing.plot_flexibility_needs import (
    FLEX_OPTION_COLOURS,
    HOURS_PER_WEATHER_YEAR,
)
from scripts.utils import setup_plot

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #

SYMBOLS = (
    "EL_DEMAND_YCRST", "H_DEMAND_YCRAST", "H2_DEMAND_YCRST",
    "PRO_YCRAGFST", "F_CONS_YCRAST", "X_FLOW_YCRST", "XH2_FLOW_YCRST",
)


def _parse_excluded_years(raw: tuple, source_scenario: str, run_type: str) -> set:
    """Weather-year strings to drop from this illustration's own ensemble,
    from `--exclude-weather-year` values shaped `year` (bare - this
    invocation's own source_scenario/run_type are already fixed by the
    other required flags, so no need to repeat them), or the same
    `source:year`/`source:year:run_type` shape `plot_flexibility_needs.py`
    accepts (see docs/adr/0026) - accepted here too so the identical
    exclusion list can be copy-pasted between both tools without
    reformatting; an entry naming a different source_scenario or run_type
    than this invocation's own is simply a no-op, not an error."""
    excluded = set()
    for item in raw:
        parts = item.split(":")
        if len(parts) == 1:
            excluded.add(parts[0])
        elif len(parts) == 2:
            source, year = parts
            if source == source_scenario:
                excluded.add(year)
        elif len(parts) == 3:
            source, year, item_run_type = parts
            if source == source_scenario and item_run_type == run_type:
                excluded.add(year)
        else:
            raise click.ClickException(
                f"--exclude-weather-year must look like 'year', 'source:year' or 'source:year:run_type', got {item!r}"
            )
    return excluded


def _weather_year_scenarios(model, source_scenario: str, run_type: str) -> list:
    """[(weather_year, scenario_name, scfolder), ...], sorted by weather
    year - every located scenario name that parses (via RUN_TYPE_RE/
    split_weather_year, the same way estimate_flexibility_needs.py's main()
    does) as `source_scenario`'s own `run_type` (F or R) weather-year sweep.
    Deliberately requires `run_type` explicit rather than auto-picking one -
    see docs/adr/0023's "one run per type per folder" rule and the bug that
    motivated it (mixing F and R produced a ~150x-too-large Interannual
    number, confirmed directly against real data)."""
    found = []
    for name, folder in model.scname_to_scfolder.items():
        match = RUN_TYPE_RE.match(name)
        if not match or match.group("run_type") != run_type:
            continue
        source, weather_year = split_weather_year(match.group("base"))
        if source != source_scenario or weather_year is None:
            continue
        found.append((weather_year, name, folder))
    return sorted(found, key=lambda row: row[0])


def _read_cached_symbol(cache_dir: Path, symbol: str, folders: list) -> pd.DataFrame:
    """Every `folder`'s own cached `symbol` pickle (written by
    estimate_flexibility_needs.py, see docs/adr/0023), concatenated - never
    reads GDX itself (see docs/adr/0025). Raises a clear, actionable error
    naming exactly which folders are missing rather than a bare
    FileNotFoundError, since the fix is always the same (run
    estimate_flexibility_needs.py first, or --overwrite-cache after new HPC
    results landed) and this script has no way to produce that cache itself."""
    missing = [folder for folder in folders if not _folder_cache_path(cache_dir, symbol, folder).exists()]
    if missing:
        raise click.ClickException(
            f"{symbol} not cached for {len(missing)} folder(s) under {cache_dir}: {missing}. "
            "Run estimate_flexibility_needs.py for this --output-dir first (add --overwrite-cache "
            "if these folders' GDX results changed since it last ran)."
        )
    return pd.concat(
        [pd.read_pickle(_folder_cache_path(cache_dir, symbol, folder)) for folder in folders],
        ignore_index=True,
    )


def _annual_series(annual_means: dict) -> pd.DataFrame:
    """(x, finer, coarser) - `_plot_deviation`'s expected shape, one row per
    weather year: `finer` is that year's own annual-mean value, `coarser`
    the N-year mean (constant) - the Interannual-level equivalent of
    `illustrate_flexibility_needs._series_for_timescale`'s Annual row
    (weekly_mean vs. annual_mean), one level up (annual_mean vs. N_year_
    mean). `x` is the weather year itself (an actual calendar year, e.g.
    1986..2020), not a synthetic index - so the x-axis reads directly,
    unlike the hourly script's chronological-but-arbitrary hour_index."""
    years = sorted(annual_means, key=int)
    values = np.array([annual_means[year] for year in years], dtype=float)
    n_year_mean = values.mean()
    return pd.DataFrame({
        "x": [int(year) for year in years],
        "finer": values,
        "coarser": n_year_mean,
    })


def _contribution_series(annual_means: dict, residual_annual_means: dict) -> pd.DataFrame:
    """(x, contribution) - `_plot_contribution`'s expected shape (MWh, per
    its own shared y-axis label - not TWh, matching the original hourly
    script's own per-period contribution units): one flex option's own
    per-weather-year contribution, `0.5 * HOURS_PER_WEATHER_YEAR *
    deviation * sign / n_years`, the exact per-year integrand
    `_interannual_provision` sums (see docs/adr/0024) - `sign` from the
    *group's own* residual load (`residual_annual_means`), never the
    option's own, matching `flex_sign`/`flexibility_provision`'s "group's
    own sign" rule one level up. `n_years` is *residual load's own* weather-
    year count (not this option's own, possibly smaller if some years had
    zero dispatch) - same reason as `_pool_interannual`'s own
    `n_years_by_key`: every bar here must divide by the same N so
    `sum(bars) * 1e-6` reproduces `_interannual_provision`'s own TWh/a
    figure exactly, not just the un-normalized total. Only weather years
    present in both dicts contribute (mirrors `_pool_interannual`'s own
    `if year in year_signs` guard)."""
    residual_values = np.array(list(residual_annual_means.values()), dtype=float)
    residual_mean = residual_values.mean()
    n_years = len(residual_annual_means)
    signs = {year: np.sign(value - residual_mean) for year, value in residual_annual_means.items()}

    option_values = np.array(list(annual_means.values()), dtype=float)
    option_mean = option_values.mean()

    years = sorted((y for y in annual_means if y in signs), key=int)
    contributions = [
        0.5 * HOURS_PER_WEATHER_YEAR * (annual_means[year] - option_mean) * signs[year] / n_years
        for year in years
    ]
    return pd.DataFrame({"x": [int(year) for year in years], "contribution": contributions})


def _interannual_need(annual_means: dict) -> float:
    """TWh/a - half the summed absolute deviation between each weather
    year's own annual mean and the N-year mean, weighted by
    HOURS_PER_WEATHER_YEAR and divided by the weather-year count (see
    docs/adr/0023/0026 - Interannual's population spans the whole N-year
    ensemble, unlike Daily/Weekly/Annual's own exactly-one-year population,
    so an un-normalized sum here is a *total over N years*, not a per-year
    rate; confirmed to matter in practice - this returned numbers on the
    order of total annual demand before the `/ len(annual_means)` was
    added) - the exact formula `_pool_interannual` computes from the pooled
    per-year data, recomputed here directly from the per-year series being
    plotted so the two can never silently drift apart."""
    values = np.array(list(annual_means.values()), dtype=float)
    n_year_mean = values.mean()
    return 0.5 * HOURS_PER_WEATHER_YEAR * np.abs(values - n_year_mean).sum() * 1e-6 / len(annual_means)


def _interannual_provision(annual_means: dict, residual_annual_means: dict) -> float:
    """TWh/a - the Interannual-level equivalent of `flexibility_provision`,
    see `_contribution_series`'s own docstring for the per-year integrand
    this sums (see docs/adr/0024) and for why the division is by
    *residual load's own* weather-year count, not this option's own."""
    residual_values = np.array(list(residual_annual_means.values()), dtype=float)
    residual_mean = residual_values.mean()
    n_years = len(residual_annual_means)
    signs = {year: np.sign(value - residual_mean) for year, value in residual_annual_means.items()}
    option_values = np.array(list(annual_means.values()), dtype=float)
    option_mean = option_values.mean()
    return 0.5 * HOURS_PER_WEATHER_YEAR * 1e-6 * sum(
        (value - option_mean) * signs[year] for year, value in annual_means.items() if year in signs
    ) / n_years


def plot_interannual_illustration(series: pd.DataFrame, need: float, n_years: int, title: str, output_path: Path) -> None:
    """Fig.-1-style illustration, Interannual resolution: a single panel (no
    zoom pane - there's no finer structure within "across weather years" to
    zoom into, the same reason illustrate_flexibility_needs.py's own Annual
    row already disables its zoom pane)."""
    fig, ax = plt.subplots(1, 1, figsize=(9, 4.5))
    # unit="MWh": Interannual is one point per weather year, never hourly -
    # see illustrate_flexibility_needs._resolution_unit's own docstring.
    _plot_deviation(ax, series, f"Interannual - {n_years} weather years (need: {need:.2f} TWh/a)", unit="MWh")
    ax.set_xlabel("Weather year")
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8)
    fig.suptitle(title)
    fig.tight_layout(rect=(0, 0.1, 1, 0.92))
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_interannual_flex_option_illustration(
    profile_series: pd.DataFrame,
    contribution_series: pd.DataFrame,
    provision: float,
    flex_option: str,
    title: str,
    output_path: Path,
    colour: str | None,
) -> None:
    """Fig.-2-style illustration, Interannual resolution: profile-vs-mean
    (left) next to FlexSign-weighted contribution (right), no zoom pane -
    same reasoning as `plot_interannual_illustration`."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    _plot_deviation(axes[0], profile_series, "Interannual profile", unit="MWh")
    _plot_contribution(axes[1], contribution_series, f"Interannual contribution (provision: {provision:.2f} TWh/a)", unit="MWh")
    if colour:
        lines = axes[0].get_lines()
        if lines:
            lines[0].set_color(colour)
    for ax in axes:
        ax.set_xlabel("Weather year")
    fig.suptitle(f"{flex_option}: {title}")
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


@click.command()
@click.option("--source-scenario", required=True, help="Source scenario whose weather-year sweep to illustrate, e.g. base (see CONTEXT.md's 'Source scenario').")
@click.option("--run-type", required=True, type=click.Choice(["F", "R"]), help="Fullyear or Rolling - never mixed, see docs/adr/0023.")
@click.option("--commodity", type=click.Choice(COMMODITIES), default="ELECTRICITY", show_default=True)
@click.option(
    "--group-type",
    type=click.Choice(["system", "category", "country"]),
    default="system",
    show_default=True,
)
@click.option(
    "--group",
    default=None,
    help="Combined category name (e.g. 'High Demand / High Wind') or Country code. "
    "Ignored/forced to 'All' for --group-type=system; required otherwise.",
)
@click.option(
    "--flex-option",
    default=None,
    help="Also illustrate this flex option's own profile + FlexSign-weighted contribution (see flex_option_metrics.FLEX_OPTIONS).",
)
@click.option(
    "--exclude-weather-year",
    "exclude_weather_years",
    multiple=True,
    default=(),
    help="Drop a weather year from this illustration's own ensemble before plotting, e.g. --exclude-weather-year "
    "1985 (bare year - this invocation's own --source-scenario/--run-type already fix which pool), or the same "
    "'source:year'/'source:year:run_type' shape plot_flexibility_needs.py accepts, repeatable - see docs/adr/0026.",
)
@click.option("--balmorel-path", type=str, default="scripts/Balmorel", help="Path to the top level of Balmorel scenario folders (used only to resolve folder/scenario-name mappings, see docs/adr/0025 - never read for GDX here).")
@click.option("--gams-sysdir", type=str, default=config("GAMS_SYSTEM_DIR", default=None), help="Path to GAMS system directory")
@click.option("--output-dir", type=str, default="build_postprocess", help="Where estimate_flexibility_needs.py's .gdx_cache lives, and where to write flex_illustration_interannual/*.")
@click.option("--categorization-csv", type=str, default=None, help="Path to categorize_countries.py's output. Defaults to <output-dir>/categorization.csv")
@click.option("--reference-scenario", type=str, default="base_R2050", help="Scenario whose Combined category assignment is used (see docs/adr/0004)")
@click.option("--dark", is_flag=True, help="Make dark plot?")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["png", "svg", "pdf"]),
    default="png",
    show_default=True,
    help="Output image format for every plot written.",
)
def main(
    source_scenario: str,
    run_type: str,
    commodity: str,
    group_type: str,
    group: str,
    flex_option: str,
    exclude_weather_years: tuple,
    balmorel_path: str,
    gams_sysdir: str,
    output_dir: str,
    categorization_csv: str,
    reference_scenario: str,
    dark: bool,
    fmt: str,
):
    setup_plot(dark=dark)
    output_path = Path(output_dir) / "flex_illustration_interannual"
    output_path.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(output_dir) / ".gdx_cache"

    if group_type == "system":
        group = "All"
    elif not group:
        raise click.ClickException(f"--group is required for --group-type={group_type!r}")

    # locate_results() only - filenames, no GDX read (see AGENTS.md's
    # pybalmorel note) - just to resolve which folder each weather year's
    # scenario name lives in. The actual data always comes from
    # estimate_flexibility_needs.py's own per-folder cache (see docs/adr/0025).
    model = Balmorel(balmorel_path, gams_system_directory=gams_sysdir)
    model.locate_results(suffix_naming_only=True)
    weather_years = _weather_year_scenarios(model, source_scenario, run_type)

    excluded_years = _parse_excluded_years(exclude_weather_years, source_scenario, run_type)
    if excluded_years:
        before = len(weather_years)
        weather_years = [row for row in weather_years if row[0] not in excluded_years]
        print(f"--exclude-weather-year: dropped {before - len(weather_years)} weather year(s): {sorted(excluded_years)}")

    if len(weather_years) < 2:
        raise click.ClickException(
            f"Only {len(weather_years)} weather year(s) found for source scenario {source_scenario!r}, "
            f"run_type {run_type!r} - need at least 2 to illustrate interannual variability."
        )
    print(f"{len(weather_years)} weather year(s): {[wy for wy, _, _ in weather_years]}")
    folders = sorted({folder for _, _, folder in weather_years})

    el = _read_cached_symbol(cache_dir, "EL_DEMAND_YCRST", folders)
    h = _read_cached_symbol(cache_dir, "H_DEMAND_YCRAST", folders)
    h2 = _read_cached_symbol(cache_dir, "H2_DEMAND_YCRST", folders)
    pro = _read_cached_symbol(cache_dir, "PRO_YCRAGFST", folders)
    f_cons = _read_cached_symbol(cache_dir, "F_CONS_YCRAST", folders)
    x_flow = _read_cached_symbol(cache_dir, "X_FLOW_YCRST", folders)
    xh2_flow = _read_cached_symbol(cache_dir, "XH2_FLOW_YCRST", folders)
    demand_symbols = {"ELECTRICITY": el, "HEAT": h, "HYDROGEN": h2}
    region_to_country = region_to_country_map(pro)
    balmorel_path_obj = Path(balmorel_path)

    category_map = {}
    if group_type == "category":
        categorization_path = Path(categorization_csv) if categorization_csv else Path(output_dir) / "categorization.csv"
        if not categorization_path.exists():
            raise click.ClickException(f"{categorization_path} not found - run categorize_countries.py first.")
        categorization = pd.read_csv(categorization_path)
        category_map = build_reference_category_map(categorization, reference_scenario)

    residual_annual_means = {}
    option_annual_means = {}
    for weather_year, scenario_name, scfolder in weather_years:
        year = scenario_target_year(el, scenario_name=scenario_name)
        if year is None:
            print(f"  {scenario_name}: no target year found, skipping")
            continue

        ev_dumb_fraction = _load_ev_dumb_fraction(balmorel_path_obj, scfolder)
        dumb_hourly, smart_hourly = _split_ev_dumb(el, ev_dumb_fraction, scenario_name, year)
        dumb_country_hourly = dumb_hourly.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()

        if commodity == "ELECTRICITY":
            demand = country_hourly_demand(el, ELECTRICITY_NON_FLEX_DEMAND_CATEGORIES, scenario_name, year)
            demand = (
                pd.concat([demand, dumb_country_hourly])
                .groupby(["Country", "Season", "Time"])["Value"]
                .sum()
                .reset_index()
            )
            supply = country_hourly_supply(pro, scenario_name, year)
        else:
            demand = country_hourly_demand(demand_symbols[commodity], NON_ELECTRICITY_DEMAND_CATEGORIES, scenario_name, year)
            supply = _EMPTY_HOURLY
        rl = country_residual_load(demand, supply)
        hourly = _group_hourly(rl, group_type, group, category_map)
        if hourly.empty:
            print(f"  {scenario_name}: no residual load in group_type={group_type!r} group={group!r}, skipping")
            continue
        residual_annual_means[weather_year] = _annual_mean_aligned(hourly)

        if flex_option:
            if flex_option not in FLEX_OPTIONS or commodity not in FLEX_OPTIONS[flex_option]:
                valid = sorted(o for o, coms in FLEX_OPTIONS.items() if commodity in coms)
                raise click.ClickException(f"{flex_option!r} has no {commodity!r} view. Valid options for this commodity: {valid}")
            spec = FLEX_OPTIONS[flex_option][commodity]
            ev_smart = smart_hourly if spec.get("category") == "ENDO_EV" else None
            option_hourly_net = flex_option_hourly_net(
                spec, commodity, pro, f_cons, demand_symbols, x_flow, xh2_flow,
                region_to_country, scenario_name, year, ev_smart_hourly=ev_smart,
            )
            if option_hourly_net.empty:
                print(f"  {scenario_name}: {flex_option!r} has no hourly dispatch, skipping this year for it")
                continue
            option_hourly = _group_hourly(option_hourly_net, group_type, group, category_map)
            if option_hourly.empty:
                continue
            sign = flex_sign(hourly)  # this year's own hourly FlexSign - only used to align option_hourly's zero-fill domain
            option_annual_means[weather_year] = _annual_mean_aligned(option_hourly, sign)

    if len(residual_annual_means) < 2:
        raise click.ClickException(
            f"Only {len(residual_annual_means)} weather year(s) had usable residual load - need at least 2."
        )

    title = f"{source_scenario} ({run_type}) | {commodity} | {group_type}={group}"
    safe_group = group.replace(" ", "_").replace("/", "-")
    need = _interannual_need(residual_annual_means)
    series = _annual_series(residual_annual_means)
    residual_path = output_path / f"{source_scenario}_WY_{run_type}__{commodity}__{group_type}-{safe_group}__residual.{fmt}"
    plot_interannual_illustration(series, need, len(residual_annual_means), title, residual_path)
    print(f"Wrote {residual_path}")

    if flex_option:
        if len(option_annual_means) < 2:
            print(f"Only {len(option_annual_means)} weather year(s) had usable {flex_option!r} dispatch - skipping its plot.")
        else:
            provision = _interannual_provision(option_annual_means, residual_annual_means)
            profile_series = _annual_series(option_annual_means)
            contribution_series = _contribution_series(option_annual_means, residual_annual_means)
            colour = FLEX_OPTION_COLOURS.get(flex_option)
            safe_option = flex_option.replace(" ", "_")
            option_path = output_path / f"{source_scenario}_WY_{run_type}__{commodity}__{group_type}-{safe_group}__{safe_option}.{fmt}"
            plot_interannual_flex_option_illustration(
                profile_series, contribution_series, provision, flex_option, title, option_path, colour
            )
            print(f"Wrote {option_path}")


if __name__ == "__main__":
    main()
