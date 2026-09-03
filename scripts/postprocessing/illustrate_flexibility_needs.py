"""
Illustrate Flexibility Need/Provision Curves

A single-scenario diagnostic tool: renders the actual residual-load curve
against its own Daily/Weekly/Annual means (Geis et al. 2026's Fig. 1 style -
shaded area above/below the mean *is* the flexibility need at that
timescale), and, when a flex option is named, that option's own profile next
to its FlexSign-weighted contribution (Geis's Fig. 2 style) - so a number in
flexibility_needs.csv can be checked against the actual shape it came from.
See docs/adr/0018 for why this is a separate, on-demand script rather than a
mode of plot_flexibility_needs.py or an addition to estimate_flexibility_needs.py.

Calls estimate_flexibility_needs.py's own functions directly (residual-load
construction, FlexSign, flexibility_needs/flexibility_provision) rather than
reimplementing them, so this illustration can't silently drift from what
that script's CSV reports.

Deliberately has no pickle cache and never touches build_postprocess/.gdx_cache
- always a fresh, single-scenario-folder GDX read (see docs/adr/0018 for the
measured RAM/time cost and why the shared cache isn't a safe shortcut here).

Run via the illustrate-flex pixi task, e.g.:

    pixi run illustrate-flex --scenario base_R2050 --commodity ELECTRICITY \
        --group-type category --group "High Demand / High Wind" \
        --flex-option "Electricity storage"

Created on 25.08.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import re
import sys
from pathlib import Path

# Add repo root to path for scripts.postprocessing.* imports (see AGENTS.md's
# pybalmorel/import-path note) - importing estimate_flexibility_needs below
# additionally puts the Balmorel submodule's analysis/ dir on sys.path itself
# (needed for its own `from functions import backup_production`), as a side
# effect of that module's own top-of-file sys.path.insert.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from decouple import config
from pybalmorel import Balmorel

from scripts.postprocessing.aggregate_category_costs import build_reference_category_map
from scripts.utils import setup_plot
from scripts.postprocessing.categorize_countries import (
    region_to_country_map,
    scenario_target_year,
)
from scripts.postprocessing.estimate_flexibility_needs import (
    _EMPTY_HOURLY,
    COMMODITIES,
    ELECTRICITY_NON_FLEX_DEMAND_CATEGORIES,
    NON_ELECTRICITY_DEMAND_CATEGORIES,
    _load_ev_dumb_fraction,
    _period_means,
    _split_ev_dumb,
    country_hourly_demand,
    country_hourly_supply,
    country_residual_load,
    flex_option_hourly_net,
    flex_sign,
    flexibility_needs,
    flexibility_provision,
)
from scripts.postprocessing.flex_option_metrics import FLEX_OPTIONS
from scripts.postprocessing.plot_flexibility_needs import FLEX_OPTION_COLOURS

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #

TIMESCALE_ORDER = ["Daily", "Weekly", "Annual"]

ABOVE_COLOUR = "#f4a259"  # residual load / profile above its own mean
BELOW_COLOUR = "#4daa8a"  # residual load / profile below its own mean
LINE_COLOUR = "#2f6690"


def _group_hourly(df: pd.DataFrame, group_type: str, group: str, category_map: dict) -> pd.DataFrame:
    """(Season, Time, Value): `df` (Country, Season, Time, Value - either
    residual load or a flex option's own commodity-signed net dispatch)
    summed to one system/category/country group's hourly series - the same
    grouping estimate_flexibility_needs.py's build_*_table functions use for
    the aggregated CSV, kept as its own copy so this script stays independent
    of that module's Snakemake-facing CSV/cache plumbing (see docs/adr/0018)."""
    if group_type == "system":
        subset = df
    elif group_type == "country":
        subset = df[df["Country"] == group]
    else:
        subset = df.assign(combined_category=df["Country"].map(category_map))
        subset = subset[subset["combined_category"] == group]
    return subset.groupby(["Season", "Time"])["Value"].sum().reset_index()


def _augment(hourly: pd.DataFrame) -> pd.DataFrame:
    """`_period_means(hourly)`'s output, plus a continuous chronological hour
    index (season_num, hour_in_week, hour_index = 0..8735) - every panel's
    x-axis, so the full-year view reads left-to-right in calendar order
    regardless of Balmorel's own Season/Time string sort order."""
    working = _period_means(hourly)
    season_num = working["Season"].str[1:].astype(int)
    hour_in_week = working["Time"].str[1:].astype(int)
    working = working.assign(
        season_num=season_num,
        hour_in_week=hour_in_week,
        hour_index=(season_num - 1) * 168 + (hour_in_week - 1),
    ).sort_values("hour_index").reset_index(drop=True)
    return working


def _parse_window(window: str | None, working: pd.DataFrame) -> tuple:
    """(start_season, end_season, label) - the zoomed excerpt's Season range.
    Explicit `window` looks like "S10" or "S10-S12". When not given, picks
    the week with the largest Daily deviation from its own daily mean (the
    "most interesting" week to look at) so a first run doesn't require
    already knowing which Season number matters."""
    if window is None:
        by_season = (
            (working["Value"] - working["daily_mean"]).abs().groupby(working["season_num"]).sum()
        )
        start = end = int(by_season.idxmax())
        return start, end, f"S{start:02d} (auto-picked)"
    match = re.match(r"^S(\d+)(?:-S(\d+))?$", window.strip())
    if not match:
        raise click.ClickException(f"--window must look like 'S10' or 'S10-S12', got {window!r}")
    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else start
    return start, end, window


def _filter_window(working: pd.DataFrame, window: tuple) -> pd.DataFrame:
    start, end, _ = window
    return working[(working["season_num"] >= start) & (working["season_num"] <= end)].reset_index(drop=True)


def _series_for_timescale(working: pd.DataFrame, timescale: str) -> pd.DataFrame:
    """(x, finer, coarser): the two curves `flexibility_needs()` takes half
    the absolute deviation between, for one timescale - hourly value vs.
    daily mean (Daily), one point per day's mean vs. weekly mean (Weekly), or
    one point per week's mean vs. the annual mean (Annual)."""
    if timescale == "Daily":
        return working[["hour_index", "Value", "daily_mean"]].rename(
            columns={"hour_index": "x", "Value": "finer", "daily_mean": "coarser"}
        )
    if timescale == "Weekly":
        per_day = (
            working.groupby(["season_num", "Day"], as_index=False)
            .agg(finer=("daily_mean", "first"), coarser=("weekly_mean", "first"))
            .sort_values(["season_num", "Day"])
            .reset_index(drop=True)
        )
        per_day["x"] = per_day.index
        return per_day[["x", "finer", "coarser"]]
    per_week = (
        working.groupby("season_num", as_index=False)
        .agg(finer=("weekly_mean", "first"), coarser=("annual_mean", "first"))
        .sort_values("season_num")
        .reset_index(drop=True)
    )
    per_week["x"] = per_week.index
    return per_week[["x", "finer", "coarser"]]


def _contribution_for_timescale(working: pd.DataFrame, sign: pd.DataFrame, timescale: str) -> pd.DataFrame:
    """(x, contribution): one flex option's own per-period contribution,
    `0.5 * deviation * FlexSign` - the exact per-period integrand
    `flexibility_provision()` sums over the full hourly grid (see
    docs/adr/0017), just left unsummed here so it can be plotted."""
    merged = working.merge(sign[["Season", "Time", timescale]], on=["Season", "Time"], how="left")
    merged = merged.rename(columns={timescale: "sign"})
    if timescale == "Daily":
        merged["deviation"] = merged["Value"] - merged["daily_mean"]
        out = merged[["hour_index", "deviation", "sign"]].rename(columns={"hour_index": "x"})
    elif timescale == "Weekly":
        merged["deviation"] = merged["daily_mean"] - merged["weekly_mean"]
        out = (
            merged.groupby(["season_num", "Day"], as_index=False)
            .agg(deviation=("deviation", "first"), sign=("sign", "first"))
            .sort_values(["season_num", "Day"])
            .reset_index(drop=True)
        )
        out["x"] = out.index
    else:
        merged["deviation"] = merged["weekly_mean"] - merged["annual_mean"]
        out = (
            merged.groupby("season_num", as_index=False)
            .agg(deviation=("deviation", "first"), sign=("sign", "first"))
            .sort_values("season_num")
            .reset_index(drop=True)
        )
        out["x"] = out.index
    out["contribution"] = 0.5 * out["deviation"] * out["sign"]
    return out[["x", "contribution"]]


def _plot_deviation(ax, series: pd.DataFrame, title: str) -> None:
    x = series["x"].to_numpy(dtype=float)
    finer = series["finer"].to_numpy(dtype=float)
    coarser = series["coarser"].to_numpy(dtype=float)
    ax.plot(x, finer, color=LINE_COLOUR, linewidth=1.0, label="Series")
    ax.plot(x, coarser, color=LINE_COLOUR, linestyle="--", linewidth=1.3, label="Period mean")
    ax.fill_between(x, finer, coarser, where=finer >= coarser, color=ABOVE_COLOUR, alpha=0.55, interpolate=True, label="Above mean")
    ax.fill_between(x, finer, coarser, where=finer < coarser, color=BELOW_COLOUR, alpha=0.55, interpolate=True, label="Below mean")
    ax.set_title(title, fontsize=9)
    ax.set_ylabel("Value [MW]", fontsize=8)


def _plot_contribution(ax, series: pd.DataFrame, title: str) -> None:
    x = series["x"].to_numpy(dtype=float)
    y = series["contribution"].to_numpy(dtype=float)
    colours = np.where(y >= 0, BELOW_COLOUR, "#e07a5f")
    ax.bar(x, y, color=colours, width=1.0)
    ax.axhline(0, color="black", linewidth=0.7)
    ax.set_title(title, fontsize=9)
    ax.set_ylabel("Contribution [MWh]", fontsize=8)


def plot_residual_illustration(
    working: pd.DataFrame, needs: dict, timescales: list, window: tuple, title: str, output_path: Path
) -> None:
    """Fig.-1-style illustration: one row per selected timescale, full-year
    view (left) and a zoomed `window` excerpt (right - same already-computed
    means, only which hours are drawn changes). Each row's title carries the
    actual TWh figure from `flexibility_needs()`, so the shaded area can be
    checked against the number it produces."""
    rows = [t for t in TIMESCALE_ORDER if t in timescales]
    zoomed = _filter_window(working, window)
    fig, axes = plt.subplots(len(rows), 2, figsize=(13, 3.2 * len(rows)), squeeze=False)
    for i, timescale in enumerate(rows):
        need = needs[timescale]
        full_series = _series_for_timescale(working, timescale)
        _plot_deviation(axes[i][0], full_series, f"{timescale} - full year (need: {need:.2f} TWh/a)")
        if timescale == "Annual":
            axes[i][1].axis("off")
            axes[i][1].text(0.5, 0.5, "Annual timescale already spans the full year", ha="center", va="center", fontsize=8, wrap=True)
        else:
            zoom_series = _series_for_timescale(zoomed, timescale)
            _plot_deviation(axes[i][1], zoom_series, f"{timescale} - zoomed ({window[2]})")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8)
    fig.suptitle(title)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_flex_option_illustration(
    working: pd.DataFrame,
    sign: pd.DataFrame,
    provision: dict,
    timescales: list,
    window: tuple,
    flex_option: str,
    title: str,
    output_path: Path,
    colour: str | None,
) -> None:
    """Fig.-2-style illustration: one row per selected timescale, each with
    the option's own profile-vs-mean (left pair) next to its FlexSign-
    weighted contribution (right pair) - the two factors
    `flexibility_provision()` multiplies together before summing, per
    docs/adr/0017 - full-year and zoomed-window side by side, same as
    `plot_residual_illustration`. Row titles carry the actual TWh
    contribution from `flexibility_provision()`."""
    rows = [t for t in TIMESCALE_ORDER if t in timescales]
    zoomed = _filter_window(working, window)
    fig, axes = plt.subplots(len(rows), 4, figsize=(17, 3.2 * len(rows)), squeeze=False)
    for i, timescale in enumerate(rows):
        contribution = provision[timescale]
        full_profile = _series_for_timescale(working, timescale)
        full_contribution = _contribution_for_timescale(working, sign, timescale)
        _plot_deviation(axes[i][0], full_profile, f"{timescale} profile - full year")
        _plot_contribution(axes[i][1], full_contribution, f"{timescale} contribution (provision: {contribution:.2f} TWh/a)")
        if timescale == "Annual":
            axes[i][2].axis("off")
            axes[i][3].axis("off")
        else:
            zoom_profile = _series_for_timescale(zoomed, timescale)
            zoom_contribution = _contribution_for_timescale(zoomed, sign, timescale)
            _plot_deviation(axes[i][2], zoom_profile, f"{timescale} profile - zoomed ({window[2]})")
            _plot_contribution(axes[i][3], zoom_contribution, f"{timescale} contribution - zoomed ({window[2]})")
        if colour:
            for ax in (axes[i][0], axes[i][2]):
                lines = ax.get_lines()
                if lines:
                    lines[0].set_color(colour)
    fig.suptitle(f"{flex_option}: {title}")
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


@click.command()
@click.option("--scenario", required=True, help="Scenario name to illustrate, e.g. base_R2050 (see CONTEXT.md's 'Scenario name').")
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
    "--timescales",
    multiple=True,
    type=click.Choice(TIMESCALE_ORDER),
    default=tuple(TIMESCALE_ORDER),
    show_default=True,
    help="Which timescale panel(s) to render.",
)
@click.option(
    "--window",
    default=None,
    help="Season (e.g. S10) or range (S10-S12) to zoom into. Default: auto-picked as the week with the largest Daily deviation.",
)
@click.option("--balmorel-path", type=str, default="scripts/Balmorel", help="Path to the top level of Balmorel scenario folders")
@click.option("--gams-sysdir", type=str, default=config("GAMS_SYSTEM_DIR", default=None), help="Path to GAMS system directory")
@click.option("--output-dir", type=str, default="build_postprocess", help="Where to write flex_illustration/*")
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
    scenario: str,
    commodity: str,
    group_type: str,
    group: str,
    flex_option: str,
    timescales: tuple,
    window: str,
    balmorel_path: str,
    gams_sysdir: str,
    output_dir: str,
    categorization_csv: str,
    reference_scenario: str,
    dark: bool,
    fmt: str,
):
    setup_plot(dark=dark)
    output_path = Path(output_dir) / "flex_illustration"
    output_path.mkdir(parents=True, exist_ok=True)

    if group_type == "system":
        group = "All"
    elif not group:
        raise click.ClickException(f"--group is required for --group-type={group_type!r}")

    # No pickle cache, no --scenarios-style multi-folder pruning across a
    # shared model instance - always exactly one scenario folder, read fresh
    # every invocation (see docs/adr/0018).
    model = Balmorel(balmorel_path, gams_system_directory=gams_sysdir)
    model.locate_results(suffix_naming_only=True)
    if scenario not in model.scname_to_scfolder:
        raise click.ClickException(f"Scenario {scenario!r} not found under {balmorel_path!r}.")
    folder = model.scname_to_scfolder[scenario]
    model.scenarios = [SC for SC in model.scenarios if folder == SC]
    print(f"Reading MainResults for {scenario!r} (folder {folder!r}) fresh - no shared .gdx_cache, see docs/adr/0018.")
    model.collect_results(suffix_naming_only=True)
    res = model.results

    el = res.get_result("EL_DEMAND_YCRST")
    h = res.get_result("H_DEMAND_YCRAST")
    h2 = res.get_result("H2_DEMAND_YCRST")
    pro = res.get_result("PRO_YCRAGFST")
    f_cons = res.get_result("F_CONS_YCRAST")
    x_flow = res.get_result("X_FLOW_YCRST")
    xh2_flow = res.get_result("XH2_FLOW_YCRST")
    demand_symbols = {"ELECTRICITY": el, "HEAT": h, "HYDROGEN": h2}
    region_to_country = region_to_country_map(pro)

    year = scenario_target_year(el, scenario_name=scenario)
    if year is None:
        raise click.ClickException(f"No Year found for scenario {scenario!r} in EL_DEMAND_YCRST.")

    ev_dumb_fraction = _load_ev_dumb_fraction(Path(balmorel_path), folder)
    dumb_hourly, smart_hourly = _split_ev_dumb(el, ev_dumb_fraction, scenario, year)
    dumb_country_hourly = dumb_hourly.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()

    if commodity == "ELECTRICITY":
        demand = country_hourly_demand(el, ELECTRICITY_NON_FLEX_DEMAND_CATEGORIES, scenario, year)
        demand = (
            pd.concat([demand, dumb_country_hourly])
            .groupby(["Country", "Season", "Time"])["Value"]
            .sum()
            .reset_index()
        )
        supply = country_hourly_supply(pro, scenario, year)
    else:
        demand = country_hourly_demand(demand_symbols[commodity], NON_ELECTRICITY_DEMAND_CATEGORIES, scenario, year)
        supply = _EMPTY_HOURLY
    rl = country_residual_load(demand, supply)
    if rl.empty:
        raise click.ClickException(f"No residual load computed for {scenario!r}/{commodity!r}.")

    category_map = {}
    if group_type == "category":
        categorization_path = Path(categorization_csv) if categorization_csv else Path(output_dir) / "categorization.csv"
        if not categorization_path.exists():
            raise click.ClickException(f"{categorization_path} not found - run categorize_countries.py first.")
        categorization = pd.read_csv(categorization_path)
        category_map = build_reference_category_map(categorization, reference_scenario)

    hourly = _group_hourly(rl, group_type, group, category_map)
    if hourly.empty:
        raise click.ClickException(f"No residual load found for group_type={group_type!r} group={group!r}.")

    sign = flex_sign(hourly)
    needs = flexibility_needs(hourly)
    working = _augment(hourly)
    window_range = _parse_window(window, working)
    print(f"Zoom window: {window_range[2]}")

    title = f"{scenario} | {commodity} | {group_type}={group}"
    safe_group = group.replace(" ", "_").replace("/", "-")
    residual_path = output_path / f"{scenario}__{commodity}__{group_type}-{safe_group}__residual.{fmt}"
    plot_residual_illustration(working, needs, list(timescales), window_range, title, residual_path)
    print(f"Wrote {residual_path}")

    if flex_option:
        if flex_option not in FLEX_OPTIONS or commodity not in FLEX_OPTIONS[flex_option]:
            valid = sorted(o for o, coms in FLEX_OPTIONS.items() if commodity in coms)
            raise click.ClickException(f"{flex_option!r} has no {commodity!r} view. Valid options for this commodity: {valid}")
        spec = FLEX_OPTIONS[flex_option][commodity]
        ev_smart = smart_hourly if spec.get("category") == "ENDO_EV" else None
        option_hourly_net = flex_option_hourly_net(
            spec, commodity, pro, f_cons, demand_symbols, x_flow, xh2_flow,
            region_to_country, scenario, year, ev_smart_hourly=ev_smart,
        )
        if option_hourly_net.empty:
            raise click.ClickException(f"{flex_option!r} has no hourly dispatch for {scenario!r}/{commodity!r}.")
        option_hourly = _group_hourly(option_hourly_net, group_type, group, category_map)
        if option_hourly.empty:
            raise click.ClickException(f"{flex_option!r} has no dispatch in group_type={group_type!r} group={group!r}.")
        provision = flexibility_provision(option_hourly, sign)
        option_working = _augment(option_hourly)
        colour = FLEX_OPTION_COLOURS.get(flex_option)
        safe_option = flex_option.replace(" ", "_")
        option_path = output_path / f"{scenario}__{commodity}__{group_type}-{safe_group}__{safe_option}.{fmt}"
        plot_flex_option_illustration(
            option_working, sign, provision, list(timescales), window_range, flex_option, title, option_path, colour
        )
        print(f"Wrote {option_path}")


if __name__ == "__main__":
    main()
