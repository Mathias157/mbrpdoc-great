"""
Estimate Daily / Weekly / Annual Flexibility Needs from Residual Load

For each fullyear/rolling scenario result and each commodity (electricity,
heat, hydrogen - see docs/adr/0009), computes hourly residual load
(non-dispatchable demand minus non-dispatchable supply, see CONTEXT.md and
docs/adr/0006/0009) per country, then decomposes it hierarchically
(hourly->daily->weekly->annual, following Geis et al. (2026)) into three
flexibility-need numbers (TWh/a) - system-wide, per Demand/VRE Combined
category (membership fixed from a reference scenario, see docs/adr/0004),
and per country. Heat and hydrogen residual load is non-dispatchable demand
only, never netted against a non-dispatchable supply (see docs/adr/0009).

The same hierarchical decomposition is also applied to each flexibility
option's own commodity-signed net hourly dispatch (see
flex_option_metrics.FLEX_OPTIONS, CONTEXT.md's "Commodity-signed flex
value", and docs/adr/0008), per commodity it has a view on, to show what
timescale it actually operates at, alongside residual load's own
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
from scripts.postprocessing.flex_option_metrics import FLEX_OPTIONS, STORAGE_CHARGE_CATEGORIES

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #

COMMODITIES = ("ELECTRICITY", "HEAT", "HYDROGEN")

# Non-dispatchable supply is fixed (not configurable) - wind, solar and
# run-of-river hydro, the same "full-certainty" grouping this Balmorel
# dataset already uses internally (VRE_CERT_AS.inc). Electricity-only - see
# docs/adr/0006/0009 for why heat and hydrogen have no non-dispatchable
# supply counterpart.
NON_DISPATCHABLE_SUPPLY_TECHNOLOGIES = [*WIND_TECHNOLOGIES, *SOLAR_TECHNOLOGIES, "HYDRO-RUN-OF-RIVER"]

# EL_DEMAND_YCRST's own VARIABLE_CATEGORY values that may count as
# non-dispatchable demand - see docs/adr/0006 for why EXOGENOUS is the only
# default and ENDOGENOUS_ELECT2HEAT/ENDO_EV are opt-in via --demand-categories.
# Electricity-only: heat and hydrogen always use EXOGENOUS only (see
# docs/adr/0009) - no equivalent judgement call has been identified for them
# the way ENDOGENOUS_ELECT2HEAT/ENDO_EV are for electricity.
DEMAND_CATEGORY_CHOICES = ["EXOGENOUS", "ENDOGENOUS_ELECT2HEAT", "ENDO_EV"]
NON_ELECTRICITY_DEMAND_CATEGORIES = ("EXOGENOUS",)

NEEDS_COLUMNS = ["Scenario", "Year", "group_type", "group", "flex_option", "Commodity", "timescale", "flex_need_twh"]

_EMPTY_HOURLY = pd.DataFrame(columns=["Country", "Season", "Time", "Value"])

# Flattened (flex_option, commodity, spec) triples for every commodity view
# in flex_option_metrics.FLEX_OPTIONS whose own MainResults symbol carries
# an hourly Season/Time dimension - every kind except "system_only"
# (Demand response's DR_FLEX_Y has no "ST" counterpart in this dataset's own
# naming convention for "already summed over Season/Time", see pybalmorel's
# formatting.py). V2G ("net_category", EL_DEMAND_YCRST) is decomposable here
# even though it wasn't originally (docs/adr/0007) - EL_DEMAND_YCRST does
# have an hourly counterpart, unlike the V2G_FLEX_YCR symbol it replaced
# (see docs/adr/0008).
HOURLY_FLEX_OPTIONS = [
    (flex_option, commodity, spec)
    for flex_option, commodities in FLEX_OPTIONS.items()
    for commodity, spec in commodities.items()
    if spec["kind"] != "system_only"
]


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


def country_hourly_demand(demand_df: pd.DataFrame, demand_categories: tuple, scenario_name: str, year: str) -> pd.DataFrame:
    """(Country, Season, Time, Value): non-dispatchable demand (MWh) per
    country-hour, summed over the chosen `demand_categories`. `demand_df` is
    whichever commodity's own hourly demand symbol (EL_DEMAND_YCRST /
    H_DEMAND_YCRAST / H2_DEMAND_YCRST)."""
    query = "Scenario == @scenario_name and Year == @year and Category in @demand_categories"
    return demand_df.query(query).groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()


def country_hourly_supply(pro: pd.DataFrame, scenario_name: str, year: str) -> pd.DataFrame:
    """(Country, Season, Time, Value): non-dispatchable supply (MWh) per
    country-hour - wind, solar and run-of-river production. Electricity
    only - see docs/adr/0009."""
    query = "Scenario == @scenario_name and Year == @year and Technology in @NON_DISPATCHABLE_SUPPLY_TECHNOLOGIES"
    return pro.query(query).groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()


def country_residual_load(demand: pd.DataFrame, supply: pd.DataFrame) -> pd.DataFrame:
    """(Country, Season, Time, Value): residual load (MWh) = non-dispatchable
    demand minus non-dispatchable supply, per country-hour. A country-hour
    present on only one side is treated as 0 on the other (e.g. a country
    with demand but no modelled wind/solar/run-of-river) - this is also how
    heat/hydrogen residual load (demand only, no supply netting, see
    docs/adr/0009) is computed: `supply` is simply passed in empty."""
    merged = demand.merge(
        supply, on=["Country", "Season", "Time"], how="outer", suffixes=("_demand", "_supply")
    ).fillna(0)
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
        demand, on=["Country", "Season", "Time"], how="outer", suffixes=("_supply", "_demand")
    ).fillna(0)
    merged["Value"] = merged["Value_supply"] - merged["Value_demand"]
    return merged[["Country", "Season", "Time", "Value"]]


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
    return pd.DataFrame(
        {
            "Scenario": scenario_name,
            "Year": year,
            "group_type": group_type,
            "group": group,
            "flex_option": flex_option,
            "Commodity": commodity,
            "timescale": list(needs.keys()),
            "flex_need_twh": list(needs.values()),
        }
    )


def build_system_table(rl: pd.DataFrame, commodity: str, scenario_name: str, year: str) -> pd.DataFrame:
    """Flexibility needs summed across every country in `rl` - one system-
    wide hourly residual load series."""
    hourly = rl.groupby(["Season", "Time"])["Value"].sum().reset_index()
    return _needs_rows(hourly, scenario_name, year, group_type="system", group="All", commodity=commodity)


def build_category_table(rl: pd.DataFrame, category_map: dict, commodity: str, scenario_name: str, year: str) -> pd.DataFrame:
    """Flexibility needs per Combined category - each category's hourly
    residual load is its member countries' (fixed via `category_map`, see
    docs/adr/0004) hourly residual load summed together."""
    categorized = rl.assign(combined_category=rl["Country"].map(category_map)).dropna(subset=["combined_category"])
    tables = []
    for group, group_rl in categorized.groupby("combined_category"):
        hourly = group_rl.groupby(["Season", "Time"])["Value"].sum().reset_index()
        tables.append(_needs_rows(hourly, scenario_name, year, group_type="category", group=group, commodity=commodity))
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame(columns=NEEDS_COLUMNS)


def build_country_table(rl: pd.DataFrame, commodity: str, scenario_name: str, year: str) -> pd.DataFrame:
    """Flexibility needs per individual country - table rows only (no plot,
    see docs/adr/0006/CONTEXT.md), to avoid one PNG per country."""
    tables = [
        _needs_rows(
            group_rl[["Season", "Time", "Value"]], scenario_name, year, group_type="country", group=country, commodity=commodity
        )
        for country, group_rl in rl.groupby("Country")
    ]
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame(columns=NEEDS_COLUMNS)


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
) -> pd.DataFrame:
    """(Country, Season, Time, Value): one flex option's own commodity-signed
    net hourly dispatch (supply minus demand - positive when it injects into
    `commodity`'s balance, negative when it withdraws, see CONTEXT.md's
    "Commodity-signed flex value" and docs/adr/0008) - the same shape as
    `country_hourly_supply`'s output, so `flexibility_needs()` decomposes it
    the same hierarchical way as residual load, to show what timescale that
    option actually operates at. Only called for `HOURLY_FLEX_OPTIONS`.
    `demand_symbols` is {"ELECTRICITY": el, "HEAT": h, "HYDROGEN": h2} -
    each commodity's own hourly non-dispatchable-demand symbol, reused here
    to source storage's charging side and V2G's net side."""
    kind = spec["kind"]

    # Boolean indexing throughout, not `.query("... == @scenario_name ...")`
    # - pandas' query engine resolves `@name` by inspecting the calling
    # frame, which does not reliably see a nested closure's free variables
    # (confirmed: raises UndefinedVariableError from within `_tech_rows`).

    def _scenario_year(df: pd.DataFrame) -> pd.DataFrame:
        return df[(df["Scenario"] == scenario_name) & (df["Year"] == year)]

    def _tech_rows(df: pd.DataFrame) -> pd.DataFrame:
        sub = _scenario_year(df)
        sub = sub[(sub["Commodity"] == commodity) & (sub["Technology"].isin(spec["technologies"]))]
        if "fuels" in spec:
            sub = sub[sub["Fuel"].isin(spec["fuels"])]
        if "exclude_fuels" in spec:
            sub = sub[~sub["Fuel"].isin(spec["exclude_fuels"])]
        if spec.get("exclude_backup"):
            sub = sub[~sub["Generation"].str.contains("BACKUP")]
        return sub.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()

    if kind == "production":
        return _net_hourly(_tech_rows(pro), _EMPTY_HOURLY)

    if kind == "consumption":
        sub = _scenario_year(f_cons)
        sub = sub[(sub["Technology"].isin(spec["technologies"])) & (sub["Fuel"] == "ELECTRIC")]
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
        # abs(): a directional flow can be negative depending on this
        # symbol's From/To sign convention - "use" here means how much the
        # interconnector is utilised, not net export/import direction
        # (deliberately kept unsigned/out of scope, see docs/adr/0008).
        supply = df.assign(Value=df["Value"].abs()).groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()
        return _net_hourly(supply, _EMPTY_HOURLY)

    if kind == "net_category":
        dem = _scenario_year(demand_symbols[commodity])
        dem = dem[dem["Category"] == spec["category"]]
        rows = dem.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()
        rows["Value"] *= -1  # demand-table convention ("more demand" = positive) -> "positive = supply"
        return rows

    if kind == "peaker":
        backup = backup_production(_scenario_year(pro), commodity=commodity)
        df = backup.assign(Country=backup["Region"].map(region_to_country)).dropna(subset=["Country"])
        supply = df.groupby(["Country", "Season", "Time"])["Value"].sum().reset_index()
        return _net_hourly(supply, _EMPTY_HOURLY)

    raise ValueError(f"{kind!r} has no hourly resolution for flexibility-need decomposition")


def build_flex_option_system_table(
    hourly_net: pd.DataFrame, flex_option: str, commodity: str, scenario_name: str, year: str
) -> pd.DataFrame:
    """Daily/Weekly/Annual decomposition of one flex option's own commodity-
    signed net hourly dispatch, summed across every country - system-wide
    equivalent of `build_system_table`, but the signal is the option's own
    operation, not residual load."""
    hourly = hourly_net.groupby(["Season", "Time"])["Value"].sum().reset_index()
    return _needs_rows(
        hourly, scenario_name, year, group_type="flex_option_system", group="All", commodity=commodity, flex_option=flex_option
    )


def build_flex_option_category_table(
    hourly_net: pd.DataFrame, category_map: dict, flex_option: str, commodity: str, scenario_name: str, year: str
) -> pd.DataFrame:
    """Daily/Weekly/Annual decomposition of one flex option's own commodity-
    signed net hourly dispatch, per Combined category - category-level
    equivalent of `build_category_table`."""
    categorized = hourly_net.assign(combined_category=hourly_net["Country"].map(category_map)).dropna(
        subset=["combined_category"]
    )
    tables = []
    for group, group_use in categorized.groupby("combined_category"):
        hourly = group_use.groupby(["Season", "Time"])["Value"].sum().reset_index()
        tables.append(
            _needs_rows(
                hourly,
                scenario_name,
                year,
                group_type="flex_option_category",
                group=group,
                commodity=commodity,
                flex_option=flex_option,
            )
        )
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame(columns=NEEDS_COLUMNS)


def plot_flexibility_needs(rows: pd.DataFrame, title: str, output_path: Path, hue_col: str = "group") -> None:
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
    fig.suptitle(f"Flexibility needs ({title})")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_flex_option_category_grid(rows: pd.DataFrame, title: str, output_path: Path) -> None:
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
    fig.suptitle(f"Flexibility-option use, by Combined category ({title})")
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
    help="EL_DEMAND_YCRST categories counted as electricity's non-dispatchable demand (see docs/adr/0006). "
    "Heat and hydrogen always use EXOGENOUS only (see docs/adr/0009).",
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
    help="Re-read PRO_YCRAGFST/X_FLOW_YCRST/XH2_FLOW_YCRST/etc. from GDX instead of <output-dir>/.gdx_cache/*.pkl "
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
    h = _get_result_cached(res, "H_DEMAND_YCRAST", cache_dir, overwrite_cache)
    h2 = _get_result_cached(res, "H2_DEMAND_YCRST", cache_dir, overwrite_cache)
    pro = _get_result_cached(res, "PRO_YCRAGFST", cache_dir, overwrite_cache)
    f_cons = _get_result_cached(res, "F_CONS_YCRAST", cache_dir, overwrite_cache)
    x_flow = _get_result_cached(res, "X_FLOW_YCRST", cache_dir, overwrite_cache)
    xh2_flow = _get_result_cached(res, "XH2_FLOW_YCRST", cache_dir, overwrite_cache)
    region_to_country = region_to_country_map(pro)
    demand_symbols = {"ELECTRICITY": el, "HEAT": h, "HYDROGEN": h2}

    scenario_names = select_scenario_names(model.scenario_names)
    print(f"Estimating flexibility needs for {len(scenario_names)} fullyear/rolling scenario result(s): {scenario_names}")

    tables = []
    for scenario_name in scenario_names:
        year = scenario_target_year(el, scenario_name=scenario_name)
        if year is None:
            continue

        for commodity in COMMODITIES:
            if commodity == "ELECTRICITY":
                demand = country_hourly_demand(el, tuple(demand_categories), scenario_name, year)
                supply = country_hourly_supply(pro, scenario_name, year)
            else:
                # No non-dispatchable supply on the heat/hydrogen side - see
                # docs/adr/0009 - so `supply` is left empty and residual
                # load is just non-dispatchable demand.
                demand = country_hourly_demand(demand_symbols[commodity], NON_ELECTRICITY_DEMAND_CATEGORIES, scenario_name, year)
                supply = _EMPTY_HOURLY
            if demand.empty and supply.empty:
                continue
            rl = country_residual_load(demand, supply)

            tables.append(build_system_table(rl, commodity, scenario_name, year))
            tables.append(build_category_table(rl, category_map, commodity, scenario_name, year))
            tables.append(build_country_table(rl, commodity, scenario_name, year))

        for flex_option, commodity, spec in HOURLY_FLEX_OPTIONS:
            hourly_net = flex_option_hourly_net(
                spec, commodity, pro, f_cons, demand_symbols, x_flow, xh2_flow, region_to_country, scenario_name, year
            )
            if hourly_net.empty:
                continue
            tables.append(build_flex_option_system_table(hourly_net, flex_option, commodity, scenario_name, year))
            tables.append(build_flex_option_category_table(hourly_net, category_map, flex_option, commodity, scenario_name, year))

    tidy = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame(columns=NEEDS_COLUMNS)
    if years:
        tidy = tidy[tidy["Year"].astype(str).isin([str(y) for y in years])]
    tidy.to_csv(table_path, index=False)

    if tidy.empty:
        return

    for commodity in COMMODITIES:
        by_commodity = tidy[tidy["Commodity"] == commodity]
        if by_commodity.empty:
            continue

        for group_type in ("system", "category"):
            subset = by_commodity[by_commodity["group_type"] == group_type]
            if subset.empty:
                continue
            plot_flexibility_needs(subset, f"{group_type}, {commodity}", plots_dir / f"{group_type}_{commodity}.png")

        option_system_rows = by_commodity[by_commodity["group_type"] == "flex_option_system"]
        if not option_system_rows.empty:
            plot_flexibility_needs(
                option_system_rows,
                f"flexibility options, system-wide ({commodity})",
                plots_dir / f"system_by_option_{commodity}.png",
                hue_col="flex_option",
            )

        option_category_rows = by_commodity[by_commodity["group_type"] == "flex_option_category"]
        if not option_category_rows.empty:
            plot_flex_option_category_grid(option_category_rows, commodity, plots_dir / f"category_by_option_{commodity}.png")


if __name__ == "__main__":
    main()
