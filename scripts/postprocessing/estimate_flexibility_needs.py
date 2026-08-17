"""
Estimate Daily / Weekly / Annual Flexibility Needs from Residual Load

For each fullyear/rolling scenario result, computes hourly residual load
(non-dispatchable demand minus non-dispatchable supply, see CONTEXT.md and
docs/adr/0006) per country, then decomposes it hierarchically
(hourly->daily->weekly->annual, following Geis et al. (2026)) into three
flexibility-need numbers (TWh/a) - system-wide, per Demand/VRE Combined
category (membership fixed from a reference scenario, see docs/adr/0004),
and per country.

The same hierarchical decomposition is also applied to each hourly-capable
flexibility option's (see flex_option_metrics.FLEX_OPTIONS) own dispatch, to
show what timescale it actually operates at, alongside residual load's own
Daily/Weekly/Annual bars (see docs/adr/0007).

Created on 14.08.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import sys
from pathlib import Path

# Add repo root (for scripts.postprocessing.*) and the Balmorel submodule's
# analysis/ dir (for functions.backup_production - see AGENTS.md's note on
# how `pixi run analyse` invokes analyse.py) to path for imports.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "Balmorel" / "analysis"))

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from decouple import config
from pybalmorel import Balmorel

from functions import backup_production

from scripts.postprocessing.aggregate_category_costs import build_reference_category_map
from scripts.postprocessing.categorize_countries import (
    SOLAR_TECHNOLOGIES,
    WIND_TECHNOLOGIES,
    region_to_country_map,
    scenario_target_year,
    select_scenario_names,
)
from scripts.postprocessing.flex_option_metrics import FLEX_OPTIONS

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #

# Non-dispatchable supply is fixed (not configurable) - wind, solar and
# run-of-river hydro, the same "full-certainty" grouping this Balmorel
# dataset already uses internally (VRE_CERT_AS.inc). See docs/adr/0006.
NON_DISPATCHABLE_SUPPLY_TECHNOLOGIES = [*WIND_TECHNOLOGIES, *SOLAR_TECHNOLOGIES, "HYDRO-RUN-OF-RIVER"]

# EL_DEMAND_YCRST's own VARIABLE_CATEGORY values that may count as
# non-dispatchable demand - see docs/adr/0006 for why EXOGENOUS is the only
# default and ENDOGENOUS_ELECT2HEAT/ENDO_EV are opt-in via --demand-categories.
DEMAND_CATEGORY_CHOICES = ["EXOGENOUS", "ENDOGENOUS_ELECT2HEAT", "ENDO_EV"]

NEEDS_COLUMNS = ["Scenario", "Year", "group_type", "group", "flex_option", "timescale", "flex_need_twh"]

# Flex options (see flex_option_metrics.FLEX_OPTIONS) whose own MainResults
# symbol carries an hourly Season/Time dimension - technology options read
# PRO_YCRAGFST (already loaded below), transmission options read their own
# *_FLOW_YCRST symbol, and peaker is derived from PRO_YCRAGFST the same way
# flex_option_metrics.py does. V2G ("region_symbol", V2G_FLEX_YCR) and
# Demand response ("system_only", DR_FLEX_Y) have no "ST" suffix - this
# dataset's own naming convention for "already summed over Season/Time" (see
# pybalmorel's formatting.py) - so they can't be decomposed this way and are
# excluded here (see docs/adr/0007).
HOURLY_FLEX_OPTIONS = {
    name: spec for name, spec in FLEX_OPTIONS.items() if spec["kind"] in ("technology", "transmission", "peaker")
}


def _get_result_cached(res, symbol: str, cache_dir: Path, overwrite: bool) -> pd.DataFrame:
    """`res.get_result(symbol)`, pickle-cached to `cache_dir/<symbol>.pkl`.
    PRO_YCRAGFST in particular is a large hourly GDX read reused by every
    technology/peaker flex option below, so re-running this script (e.g. to
    tweak a plot) doesn't re-read it from disk every time. Mirrors
    scripts/Balmorel/analysis/analyse.py's module-level `collect_results`
    pickle cache, but self-contained (no click context) and living under
    the (already gitignored) --output-dir."""
    cache_path = cache_dir / f"{symbol}.pkl"
    if cache_path.exists() and not overwrite:
        return pd.read_pickle(cache_path)
    df = res.get_result(symbol)
    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_pickle(cache_path)
    return df


def country_hourly_demand(el: pd.DataFrame, demand_categories: tuple, scenario_name: str, year: str) -> pd.DataFrame:
    """(Country, Season, Time, Value): non-dispatchable demand (MWh) per
    country-hour, summed over the chosen `demand_categories`."""
    query = "Scenario == @scenario_name and Year == @year and Category in @demand_categories"
    return el.query(query).groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()


def country_hourly_supply(pro: pd.DataFrame, scenario_name: str, year: str) -> pd.DataFrame:
    """(Country, Season, Time, Value): non-dispatchable supply (MWh) per
    country-hour - wind, solar and run-of-river production."""
    query = "Scenario == @scenario_name and Year == @year and Technology in @NON_DISPATCHABLE_SUPPLY_TECHNOLOGIES"
    return pro.query(query).groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()


def country_residual_load(demand: pd.DataFrame, supply: pd.DataFrame) -> pd.DataFrame:
    """(Country, Season, Time, Value): residual load (MWh) = non-dispatchable
    demand minus non-dispatchable supply, per country-hour. A country-hour
    present on only one side is treated as 0 on the other (e.g. a country
    with demand but no modelled wind/solar/run-of-river)."""
    merged = demand.merge(
        supply, on=["Country", "Season", "Time"], how="outer", suffixes=("_demand", "_supply")
    ).fillna(0)
    merged["Value"] = merged["Value_demand"] - merged["Value_supply"]
    return merged[["Country", "Season", "Time", "Value"]]


def flexibility_needs(hourly: pd.DataFrame) -> dict:
    """Daily/Weekly/Annual flexibility need (TWh) for one group's hourly
    residual load series (Season, Time, Value - Season = calendar week
    S01-S52, Time = hour-in-week T001-T168, per this Balmorel setup's
    chronological fullyear/rolling grid).

    Follows Geis et al. (2026)'s hierarchical decomposition: each timescale's
    need is half the summed absolute deviation between one resolution's mean
    and the next coarser one, always summed over the full hourly grid so
    variability already captured at a finer timescale isn't double-counted -
    see docs/adr/0006."""
    hour_in_week = hourly["Time"].str[1:].astype(int)
    day = hourly["Season"] + "-D" + (((hour_in_week - 1) // 24) + 1).astype(str)

    working = hourly.assign(Day=day)
    working["daily_mean"] = working.groupby("Day")["Value"].transform("mean")
    working["weekly_mean"] = working.groupby("Season")["Value"].transform("mean")
    annual_mean = working["Value"].mean()

    mwh_to_twh = 1e-6
    return {
        "Daily": 0.5 * (working["Value"] - working["daily_mean"]).abs().sum() * mwh_to_twh,
        "Weekly": 0.5 * (working["daily_mean"] - working["weekly_mean"]).abs().sum() * mwh_to_twh,
        "Annual": 0.5 * (working["weekly_mean"] - annual_mean).abs().sum() * mwh_to_twh,
    }


def _needs_rows(
    hourly: pd.DataFrame, scenario_name: str, year: str, group_type: str, group: str, flex_option: str = ""
) -> pd.DataFrame:
    if hourly.empty:
        return pd.DataFrame(columns=NEEDS_COLUMNS)
    needs = flexibility_needs(hourly)
    return pd.DataFrame(
        {
            "Scenario": scenario_name,
            "Year": year,
            "group_type": group_type,
            "group": group,
            "flex_option": flex_option,
            "timescale": list(needs.keys()),
            "flex_need_twh": list(needs.values()),
        }
    )


def build_system_table(rl: pd.DataFrame, scenario_name: str, year: str) -> pd.DataFrame:
    """Flexibility needs summed across every country in `rl` - one system-
    wide hourly residual load series."""
    hourly = rl.groupby(["Season", "Time"])["Value"].sum().reset_index()
    return _needs_rows(hourly, scenario_name, year, group_type="system", group="All")


def build_category_table(rl: pd.DataFrame, category_map: dict, scenario_name: str, year: str) -> pd.DataFrame:
    """Flexibility needs per Combined category - each category's hourly
    residual load is its member countries' (fixed via `category_map`, see
    docs/adr/0004) hourly residual load summed together."""
    categorized = rl.assign(combined_category=rl["Country"].map(category_map)).dropna(subset=["combined_category"])
    tables = []
    for group, group_rl in categorized.groupby("combined_category"):
        hourly = group_rl.groupby(["Season", "Time"])["Value"].sum().reset_index()
        tables.append(_needs_rows(hourly, scenario_name, year, group_type="category", group=group))
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame(columns=NEEDS_COLUMNS)


def build_country_table(rl: pd.DataFrame, scenario_name: str, year: str) -> pd.DataFrame:
    """Flexibility needs per individual country - table rows only (no plot,
    see docs/adr/0006/CONTEXT.md), to avoid one PNG per country."""
    tables = [
        _needs_rows(group_rl[["Season", "Time", "Value"]], scenario_name, year, group_type="country", group=country)
        for country, group_rl in rl.groupby("Country")
    ]
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame(columns=NEEDS_COLUMNS)


def flex_option_hourly_use(
    spec: dict,
    pro: pd.DataFrame,
    x_flow: pd.DataFrame,
    xh2_flow: pd.DataFrame,
    region_to_country: dict,
    scenario_name: str,
    year: str,
) -> pd.DataFrame:
    """(Country, Season, Time, Value): one flex option's own hourly
    use/dispatch, summed to country level - the same shape as
    `country_hourly_supply`'s output, so `flexibility_needs()` decomposes it
    the same hierarchical way as residual load, to show what timescale that
    option actually operates at. Only called for `HOURLY_FLEX_OPTIONS`."""
    query = "Scenario == @scenario_name and Year == @year"

    if spec["kind"] == "technology":
        df = pro.query(query + " and Technology in @spec['technologies']")
        return df.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()

    if spec["kind"] == "transmission":
        flow = x_flow if spec["use_symbol"] == "X_FLOW_YCR" else xh2_flow
        df = flow.query(query)
        # abs(): a directional flow can be negative depending on this
        # symbol's From/To sign convention - "use" here means how much the
        # interconnector is utilised, not net export/import direction.
        return df.assign(Value=df["Value"].abs()).groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()

    if spec["kind"] == "peaker":
        backup = backup_production(pro.query(query), commodity="ELECTRICITY")
        df = backup.assign(Country=backup["Region"].map(region_to_country)).dropna(subset=["Country"])
        return df.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()

    raise ValueError(f"{spec['kind']!r} has no hourly resolution for flexibility-need decomposition")


def build_flex_option_system_table(
    hourly_use: pd.DataFrame, flex_option: str, scenario_name: str, year: str
) -> pd.DataFrame:
    """Daily/Weekly/Annual decomposition of one flex option's own hourly use,
    summed across every country - system-wide equivalent of `build_system_table`,
    but the signal is the option's own operation, not residual load."""
    hourly = hourly_use.groupby(["Season", "Time"])["Value"].sum().reset_index()
    return _needs_rows(hourly, scenario_name, year, group_type="flex_option_system", group="All", flex_option=flex_option)


def build_flex_option_category_table(
    hourly_use: pd.DataFrame, category_map: dict, flex_option: str, scenario_name: str, year: str
) -> pd.DataFrame:
    """Daily/Weekly/Annual decomposition of one flex option's own hourly use,
    per Combined category - category-level equivalent of `build_category_table`."""
    categorized = hourly_use.assign(combined_category=hourly_use["Country"].map(category_map)).dropna(
        subset=["combined_category"]
    )
    tables = []
    for group, group_use in categorized.groupby("combined_category"):
        hourly = group_use.groupby(["Season", "Time"])["Value"].sum().reset_index()
        tables.append(
            _needs_rows(hourly, scenario_name, year, group_type="flex_option_category", group=group, flex_option=flex_option)
        )
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame(columns=NEEDS_COLUMNS)


def plot_flexibility_needs(rows: pd.DataFrame, group_type: str, output_path: Path, hue_col: str = "group") -> None:
    """One figure, one panel per timescale: x-axis = scenario, one bar per
    `hue_col` value (a single 'All' bar for system-level), height =
    flex_need_twh. `hue_col` defaults to "group" (spatial grouping: system/
    category/country); pass "flex_option" to legend by flex option instead."""
    timescales = ["Daily", "Weekly", "Annual"]
    scenarios = sorted(rows["Scenario"].unique())
    groups = sorted(rows[hue_col].unique())
    x = np.arange(len(scenarios))
    width = 0.8 / max(len(groups), 1)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, timescale in zip(axes, timescales):
        sub = rows[rows["timescale"] == timescale]
        for i, group in enumerate(groups):
            heights = [
                sub.loc[(sub["Scenario"] == sc) & (sub[hue_col] == group), "flex_need_twh"].sum()
                for sc in scenarios
            ]
            ax.bar(x + i * width, heights, width, label=group)
        ax.set_xticks(x + width * (len(groups) - 1) / 2)
        ax.set_xticklabels(scenarios, rotation=45, ha="right")
        ax.set_title(f"{timescale} flexibility need")
        ax.set_ylabel("Flexibility need [TWh/a]")

    handles, labels = axes[0].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    fig.legend(by_label.values(), by_label.keys(), bbox_to_anchor=(1.1, 0.5), loc="center left", fontsize=8)
    fig.suptitle(f"Flexibility needs ({group_type})")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_flex_option_category_grid(rows: pd.DataFrame, output_path: Path) -> None:
    """Grid: one row per Combined category, one column per timescale; each
    subplot bars scenario x flex option - the category-level counterpart to
    `plot_flexibility_needs(..., hue_col="flex_option")`'s system-wide plot,
    which can't itself carry a second (category) dimension."""
    timescales = ["Daily", "Weekly", "Annual"]
    categories = sorted(rows["group"].unique())
    flex_options = sorted(rows["flex_option"].unique())
    scenarios = sorted(rows["Scenario"].unique())
    x = np.arange(len(scenarios))
    width = 0.8 / max(len(flex_options), 1)

    fig, axes = plt.subplots(len(categories), 3, figsize=(15, 4 * len(categories)), squeeze=False)
    for row_i, category in enumerate(categories):
        cat_rows = rows[rows["group"] == category]
        for col_i, timescale in enumerate(timescales):
            ax = axes[row_i][col_i]
            sub = cat_rows[cat_rows["timescale"] == timescale]
            for i, option in enumerate(flex_options):
                heights = [
                    sub.loc[(sub["Scenario"] == sc) & (sub["flex_option"] == option), "flex_need_twh"].sum()
                    for sc in scenarios
                ]
                ax.bar(x + i * width, heights, width, label=option)
            ax.set_xticks(x + width * (len(flex_options) - 1) / 2)
            ax.set_xticklabels(scenarios, rotation=45, ha="right")
            if row_i == 0:
                ax.set_title(f"{timescale} flexibility need")
            if col_i == 0:
                ax.set_ylabel(f"{category}\nFlex need [TWh/a]")

    handles, labels = axes[0][0].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    fig.legend(by_label.values(), by_label.keys(), bbox_to_anchor=(1.06, 0.5), loc="center left", fontsize=8)
    fig.suptitle("Flexibility-option use, by Combined category")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


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
    help="Where to write flexibility_needs.csv and flex_needs_plots/",
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
    "--demand-categories",
    multiple=True,
    type=click.Choice(DEMAND_CATEGORY_CHOICES),
    default=("EXOGENOUS",),
    help="EL_DEMAND_YCRST categories counted as non-dispatchable demand (see docs/adr/0006)",
)
@click.option(
    "--years",
    multiple=True,
    default=(),
    help="Restrict to these target year(s) (e.g. 2050). Default: all found.",
)
@click.option(
    "--overwrite-cache",
    is_flag=True,
    default=False,
    help="Re-read PRO_YCRAGFST/X_FLOW_YCRST/XH2_FLOW_YCRST from GDX instead of <output-dir>/.gdx_cache/*.pkl "
    "(stale after new HPC results are synced down for the same scenario names).",
)
def main(
    balmorel_path: str,
    gams_sysdir: str,
    output_dir: str,
    categorization_csv: str,
    reference_scenario: str,
    demand_categories: tuple,
    years: tuple,
    overwrite_cache: bool,
):
    output_path = Path(output_dir)
    plots_dir = output_path / "flex_needs_plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    table_path = output_path / "flexibility_needs.csv"
    cache_dir = output_path / ".gdx_cache"

    categorization_path = (
        Path(categorization_csv) if categorization_csv else output_path / "categorization.csv"
    )
    if not categorization_path.exists():
        print(f"{categorization_path} not found - run categorize_countries.py first. Nothing to compute.")
        pd.DataFrame(columns=NEEDS_COLUMNS).to_csv(table_path, index=False)
        return

    categorization = pd.read_csv(categorization_path)
    category_map = build_reference_category_map(categorization, reference_scenario)
    if not category_map:
        print(f"Reference scenario {reference_scenario!r} not found in {categorization_path}. Category-level needs will be empty.")

    if not any(Path(balmorel_path).glob("*/model/MainResults_*.gdx")):
        print(f"No MainResults*.gdx files found under {balmorel_path} - nothing to compute yet.")
        pd.DataFrame(columns=NEEDS_COLUMNS).to_csv(table_path, index=False)
        return

    model = Balmorel(balmorel_path, gams_system_directory=gams_sysdir)
    model.collect_results(suffix_naming_only=True)
    res = model.results

    el = _get_result_cached(res, "EL_DEMAND_YCRST", cache_dir, overwrite_cache)
    pro = _get_result_cached(res, "PRO_YCRAGFST", cache_dir, overwrite_cache)
    x_flow = _get_result_cached(res, "X_FLOW_YCRST", cache_dir, overwrite_cache)
    xh2_flow = _get_result_cached(res, "XH2_FLOW_YCRST", cache_dir, overwrite_cache)
    region_to_country = region_to_country_map(pro)

    scenario_names = select_scenario_names(model.scenario_names)
    print(f"Estimating flexibility needs for {len(scenario_names)} fullyear/rolling scenario result(s): {scenario_names}")

    tables = []
    for scenario_name in scenario_names:
        year = scenario_target_year(el, scenario_name=scenario_name)
        if year is None:
            continue

        demand = country_hourly_demand(el, tuple(demand_categories), scenario_name, year)
        supply = country_hourly_supply(pro, scenario_name, year)
        if demand.empty and supply.empty:
            continue
        rl = country_residual_load(demand, supply)

        tables.append(build_system_table(rl, scenario_name, year))
        tables.append(build_category_table(rl, category_map, scenario_name, year))
        tables.append(build_country_table(rl, scenario_name, year))

        for flex_option, spec in HOURLY_FLEX_OPTIONS.items():
            hourly_use = flex_option_hourly_use(
                spec, pro, x_flow, xh2_flow, region_to_country, scenario_name, year
            )
            if hourly_use.empty:
                continue
            tables.append(build_flex_option_system_table(hourly_use, flex_option, scenario_name, year))
            tables.append(build_flex_option_category_table(hourly_use, category_map, flex_option, scenario_name, year))

    tidy = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame(columns=NEEDS_COLUMNS)
    if years:
        tidy = tidy[tidy["Year"].astype(str).isin([str(y) for y in years])]
    tidy.to_csv(table_path, index=False)

    if tidy.empty:
        return

    for group_type in ("system", "category"):
        subset = tidy[tidy["group_type"] == group_type]
        if subset.empty:
            continue
        plot_flexibility_needs(subset, group_type, plots_dir / f"{group_type}.png")

    option_system_rows = tidy[tidy["group_type"] == "flex_option_system"]
    if not option_system_rows.empty:
        plot_flexibility_needs(
            option_system_rows,
            "flexibility options, system-wide",
            plots_dir / "system_by_option.png",
            hue_col="flex_option",
        )

    option_category_rows = tidy[tidy["group_type"] == "flex_option_category"]
    if not option_category_rows.empty:
        plot_flex_option_category_grid(option_category_rows, plots_dir / "category_by_option.png")


if __name__ == "__main__":
    main()
