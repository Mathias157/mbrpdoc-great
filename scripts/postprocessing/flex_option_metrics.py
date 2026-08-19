"""
Flexibility-Option Priority Scatter Plots

For each flexibility option (heat pumps, storage, thermal, ...) and each
commodity it touches (electricity, heat, hydrogen), plots its capacity or
(commodity-signed) use against system cost, emissions, and security of
supply/LOLE, one dot per (scenario, year), one plot per commodity,
separately per Demand/VRE Combined category (default) or system-wide. See
CONTEXT.md ("Flexibility option", "Commodity-signed flex value") and
docs/adr/0005, 0008, 0010 for the definitions this script implements.

Does not itself rank flexibility options - it produces the plots and a
tidy CSV (build_postprocess/flex_option_metrics.csv) meant to feed a later
priority/slope-KPI pass.

Created on 12.08.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import sys
from pathlib import Path

# Add repo root (for scripts.postprocessing.categorize_countries) and the
# Balmorel submodule's analysis/ dir (for functions.costs/functions.heatmap/
# functions, which assume analysis/ itself is on sys.path - see AGENTS.md's
# note on how `pixi run analyse` invokes analyse.py) to path for imports.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "Balmorel" / "analysis"))

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from decouple import config
from pybalmorel import Balmorel

from functions import backup_production, compute_lole_ens, effective_backup_capacity
from functions.costs import combine_capex_opex
from functions.heatmap import SCENARIOS

from scripts.postprocessing.aggregate_category_costs import build_reference_category_map
from scripts.postprocessing.categorize_countries import (
    region_to_country_map,
    select_scenario_names,
)

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #

# Each commodity's own non-dispatchable-demand symbol (annual) - used both
# to source storage's charging side and V2G's net G2V-minus-V2G side. See
# CONTEXT.md's "Non-dispatchable demand"/"Non-dispatchable heat demand"/
# "Non-dispatchable hydrogen demand" and docs/adr/0008.
COMMODITY_DEMAND_SYMBOLS = {
    "ELECTRICITY": "EL_DEMAND_YCR",
    "HEAT": "H_DEMAND_YCRA",
    "HYDROGEN": "H2_DEMAND_YCR",
}

# Category values, within a commodity's own demand symbol, that represent
# that commodity's own storage charging - always excluded from residual
# load (see docs/adr/0006, 0009) and, here, the source of storage's negative
# "demand" (charging) row (see docs/adr/0008).
STORAGE_CHARGE_CATEGORIES = ["ENDO_INTRASTO", "ENDO_INTERSTO"]

# Which capacity/use metrics a flex-option-commodity view supports, driven
# purely by "kind" (see docs/adr/0008): "production" and "storage" (its
# discharge side) have a real nameplate capacity; "consumption" (heat
# pump/electrolyser electricity draw) and storage's own charging side do
# not - no symbol reports "how much of this commodity can this option
# withdraw" - so capacity is never shown there (see CONTEXT.md's
# "Flexibility option" entry).
_METRIC_TYPES_BY_KIND = {
    "production": ("capacity", "use"),
    "consumption": ("use",),
    "storage": ("capacity", "use"),
    "transmission": ("capacity", "use"),
    "net_category": ("use",),
    "system_only": ("use",),
    "peaker": ("capacity", "use"),
}

# FLEX_OPTIONS: {option name: {commodity: view spec}}. A single option can
# have a view on more than one commodity (e.g. a heat pump withdraws
# electricity and supplies heat) - each view is independent and produces its
# own (possibly multi-directional, see "kind"="storage") rows. "kind"
# determines both the extraction mechanism and the sign convention (see
# CONTEXT.md's "Commodity-signed flex value" and docs/adr/0008, 0010):
#   - "production": positive/supply-side technology output (PRO_YCRAGF /
#     G_CAP_YCRAF, Commodity-filtered). Optional "fuels"/"exclude_fuels"
#     (Fuel include/exclude list) and "exclude_backup" (drop rows whose
#     Generation contains "BACKUP" - this dataset's peaker/backup
#     convention, see docs/adr/0010).
#   - "consumption": negative/demand-side electricity draw (F_CONS_YCRA,
#     Fuel=ELECTRIC, Technology-filtered). No capacity.
#   - "storage": both directions - positive "supply" (discharging, same as
#     "production") and negative "demand" (charging, from that commodity's
#     own COMMODITY_DEMAND_SYMBOLS entry, STORAGE_CHARGE_CATEGORIES).
#     Capacity only on the "supply"/discharge side.
#   - "transmission": unsigned magnitude (X_CAP_YCR/X_FLOW_YCR or
#     XH2_CAP_YCR/XH2_FLOW_YCR) - unchanged from before this redesign; a
#     directional flow's sign is a From/To convention, not a supply/demand
#     one, so it's deliberately left out of scope here.
#   - "net_category": one already-net-signed series from that commodity's
#     own demand symbol (V2G's ENDO_EV = net G2V-minus-V2G) - negated once
#     to flip from "demand-table" convention (positive = more demand) to
#     this script's "positive = injects" convention.
#   - "system_only": unsigned magnitude, no Country dimension
#     (DR_FLEX_Y) - unchanged; no equivalent net-signed source exists.
#   - "peaker": unsigned/positive backup production, per commodity (see
#     docs/adr/0010) - electricity and heat only, no hydrogen backup exists
#     in this model.
FLEX_OPTIONS = {
    "Heat pumps": {
        "ELECTRICITY": {"kind": "consumption", "technologies": ["ELECT-TO-HEAT"]},
        "HEAT": {"kind": "production", "technologies": ["ELECT-TO-HEAT"]},
    },
    "Electrolysers": {
        "ELECTRICITY": {"kind": "consumption", "technologies": ["ELECTROLYZER"]},
        "HYDROGEN": {"kind": "production", "technologies": ["ELECTROLYZER"]},
        "HEAT": {"kind": "production", "technologies": ["ELECTROLYZER"]},
    },
    "Electricity storage": {
        "ELECTRICITY": {"kind": "storage", "technologies": ["INTRASEASONAL-ELECT-STORAGE"]},
    },
    "Heat storage": {
        "HEAT": {"kind": "storage", "technologies": ["INTERSEASONAL-HEAT-STORAGE", "INTRASEASONAL-HEAT-STORAGE"]},
    },
    "Hydrogen storage": {
        "HYDROGEN": {"kind": "storage", "technologies": ["H2-STORAGE"]},
    },
    "Electricity transmission": {
        "ELECTRICITY": {"kind": "transmission", "capacity_symbol": "X_CAP_YCR", "use_symbol": "X_FLOW_YCR"},
    },
    "Hydrogen transmission": {
        "HYDROGEN": {"kind": "transmission", "capacity_symbol": "XH2_CAP_YCR", "use_symbol": "XH2_FLOW_YCR"},
    },
    "V2G": {
        "ELECTRICITY": {"kind": "net_category", "category": "ENDO_EV"},
    },
    "Demand response": {
        "ELECTRICITY": {"kind": "system_only", "symbol": "DR_FLEX_Y"},
    },
    "Nuclear": {
        "ELECTRICITY": {"kind": "production", "technologies": ["CONDENSING"], "fuels": ["NUCLEAR"], "exclude_backup": True},
    },
    "Thermal": {
        "ELECTRICITY": {
            "kind": "production",
            "technologies": ["CONDENSING", "CHP-BACK-PRESSURE", "CHP-EXTRACTION"],
            "exclude_fuels": ["NUCLEAR"],
            "exclude_backup": True,
        },
        "HEAT": {
            "kind": "production",
            "technologies": ["CHP-BACK-PRESSURE", "CHP-EXTRACTION", "BOILERS"],
            "exclude_backup": True,
        },
        "HYDROGEN": {"kind": "production", "technologies": ["STEAMREFORMING"]},
    },
    "Hydro reservoirs": {
        "ELECTRICITY": {"kind": "production", "technologies": ["HYDRO-RESERVOIRS"]},
    },
    "Peaker": {
        "ELECTRICITY": {"kind": "peaker"},
        "HEAT": {"kind": "peaker"},
    },
}

# scenario -> colour, year -> marker. Small fixed maps (not analyse.py's
# CLI-only itertools.cycle) since this script isn't invoked through that
# module and wants a deterministic, reproducible mapping across runs.
_COLOURS = ["b", "r", "g", "c", "m", "y", "orange", "purple", "brown", "k"]
_YEAR_MARKERS = {"2030": "o", "2040": "^", "2050": "s"}


def _year_col(df: pd.DataFrame) -> str:
    return "Year" if "Year" in df.columns else "Y"


def extract_flex_option_values(
    get_symbol, region_to_country: dict, flex_option: str, commodity: str, metric_type: str
) -> list:
    """[(direction, DataFrame)] for one (flex_option, commodity, metric_type)
    - each DataFrame is (Scenario, Year, Country, Value), except demand
    response ("system_only"), which has no country dimension (see
    CONTEXT.md). Usually one pair; storage's "use" returns two - "demand"
    (charging, from that commodity's own non-dispatchable-demand symbol) and
    "supply" (discharging, from production) - since they come from two
    different symbols and must never be summed together upstream (see
    docs/adr/0008)."""
    spec = FLEX_OPTIONS[flex_option][commodity]
    kind = spec["kind"]
    if metric_type not in _METRIC_TYPES_BY_KIND[kind]:
        raise ValueError(
            f"{flex_option!r}/{commodity!r} has no {metric_type!r} metric - valid: {_METRIC_TYPES_BY_KIND[kind]}"
        )

    def _technology_rows(symbol: str) -> pd.DataFrame:
        df = get_symbol(symbol)
        df = df[(df["Commodity"] == commodity) & (df["Technology"].isin(spec["technologies"]))]
        if "fuels" in spec:
            df = df[df["Fuel"].isin(spec["fuels"])]
        if "exclude_fuels" in spec:
            df = df[~df["Fuel"].isin(spec["exclude_fuels"])]
        if spec.get("exclude_backup"):
            df = df[~df["Generation"].str.contains("BACKUP")]
        return df.groupby(["Scenario", "Year", "Country"])["Value"].sum().reset_index()

    if kind == "production":
        symbol = "G_CAP_YCRAF" if metric_type == "capacity" else "PRO_YCRAGF"
        return [("supply", _technology_rows(symbol))]

    if kind == "consumption":
        df = get_symbol("F_CONS_YCRA")
        df = df[(df["Technology"].isin(spec["technologies"])) & (df["Fuel"] == "ELECTRIC")]
        rows = df.groupby(["Scenario", "Year", "Country"])["Value"].sum().reset_index()
        rows["Value"] *= -1
        return [("demand", rows)]

    if kind == "storage":
        if metric_type == "capacity":
            return [("supply", _technology_rows("G_CAP_YCRAF"))]
        discharge = _technology_rows("PRO_YCRAGF")
        demand = get_symbol(COMMODITY_DEMAND_SYMBOLS[commodity])
        demand = demand[demand["Category"].isin(STORAGE_CHARGE_CATEGORIES)]
        charge = demand.groupby(["Scenario", "Year", "Country"])["Value"].sum().reset_index()
        charge["Value"] *= -1
        return [("demand", charge), ("supply", discharge)]

    if kind == "transmission":
        symbol = spec["capacity_symbol"] if metric_type == "capacity" else spec["use_symbol"]
        df = get_symbol(symbol)
        rows = df.groupby(["Scenario", "Year", "Country"])["Value"].sum().reset_index()
        return [("unsigned", rows)]

    if kind == "net_category":
        df = get_symbol(COMMODITY_DEMAND_SYMBOLS[commodity])
        df = df[df["Category"] == spec["category"]]
        rows = df.groupby(["Scenario", "Year", "Country"])["Value"].sum().reset_index()
        rows["Value"] *= -1
        return [("net", rows)]

    if kind == "system_only":
        df = get_symbol(spec["symbol"])
        rows = df.rename(columns={_year_col(df): "Year"})[["Scenario", "Year", "Value"]]
        return [("unsigned", rows)]

    if kind == "peaker":
        backup = backup_production(get_symbol("PRO_YCRAGFST"), commodity=commodity)
        if metric_type == "capacity":
            per_region = effective_backup_capacity(backup, nth_max=1)
        else:
            per_region = backup.groupby(["Scenario", "Year", "Region"])["Value"].sum().reset_index()
            per_region["Value"] = (
                per_region["Value"] / 1e6
            )  # MWh -> TWh, matching PRO_YCRAGF/X_FLOW_YCR's own "use" unit
        per_region = per_region.assign(Country=per_region["Region"].map(region_to_country))
        rows = (
            per_region.dropna(subset=["Country"])
            .groupby(["Scenario", "Year", "Country"])["Value"]
            .sum()
            .reset_index()
        )
        return [("supply", rows)]

    raise ValueError(f"Unknown flex option kind: {kind!r}")


def extract_scenario_metrics(
    model, get_symbol, region_to_country: dict, scenarios: list | tuple
) -> pd.DataFrame:
    """(Scenario, Year, Country): cost_beur, emissions_kton, lole_h, ens_twh.
    System-wide (all commodities) for cost/emissions; electricity-only for
    LOLE/ENS (see docs/adr/0005) - unchanged by the commodity-aware
    redesign in docs/adr/0008."""
    res = model.results

    obj = res.get_result("OBJ_YCR")
    combined, missing = combine_capex_opex(obj, model.scenario_names, scenarios)
    if missing:
        print(
            f"Missing investment or operational MainResults for: {missing} - excluded from cost."
        )
    cost = (
        combined
        .groupby(["Scenario", "Year", "Country"])["Value"]
        .sum()
        .div(1e3)
        .rename("cost_beur")
    )

    emi = res.get_result(
        "EMI_YCRAG",
        cols=[
            "Year",
            "Country",
            "Region",
            "Area",
            "Generation",
            "Fuel",
            "Technology",
            "Unit",
            "Value",
        ],
    )
    emissions = (
        emi
        .groupby(["Scenario", "Year", "Country"])["Value"]
        .sum()
        .rename("emissions_kton")
    )

    backup = backup_production(get_symbol("PRO_YCRAGFST"), commodity="ELECTRICITY")
    lole_ens = compute_lole_ens(backup)
    lole_ens = lole_ens.assign(
        Country=lole_ens["Region"].map(region_to_country)
    ).dropna(subset=["Country"])
    lole_ens = lole_ens.groupby(["Scenario", "Year", "Country"])[
        ["lole_h", "ens_twh"]
    ].sum()

    return pd.concat([cost, emissions, lole_ens], axis=1).fillna(0).reset_index()


def system_totals(scenario_metrics: pd.DataFrame) -> pd.DataFrame:
    """(Scenario, Year): scenario_metrics summed across all countries."""
    return (
        scenario_metrics
        .groupby(["Scenario", "Year"])[
            ["cost_beur", "emissions_kton", "lole_h", "ens_twh"]
        ]
        .sum()
        .reset_index()
    )


def build_category_table(
    flex_values: pd.DataFrame,
    scenario_metrics: pd.DataFrame,
    category_map: dict,
    flex_option: str,
    commodity: str,
    metric_type: str,
    direction: str,
) -> pd.DataFrame:
    """One row per (Scenario, Year, combined_category): flex_value summed
    (with cost/emissions/lole/ens) across that category's countries. Empty
    if `flex_values` has no Country column (demand response)."""
    if "Country" not in flex_values.columns:
        return pd.DataFrame()

    merged = flex_values.merge(
        scenario_metrics, on=["Scenario", "Year", "Country"], how="inner"
    )
    merged = merged.assign(
        combined_category=merged["Country"].map(category_map)
    ).dropna(subset=["combined_category"])
    if merged.empty:
        return pd.DataFrame()

    grouped = (
        merged
        .groupby(["Scenario", "Year", "combined_category"])[
            ["Value", "cost_beur", "emissions_kton", "lole_h", "ens_twh"]
        ]
        .sum()
        .reset_index()
        .rename(columns={"Value": "flex_value", "combined_category": "group"})
    )
    grouped["flex_option"] = flex_option
    grouped["Commodity"] = commodity
    grouped["metric_type"] = metric_type
    grouped["direction"] = direction
    grouped["group_type"] = "category"
    return grouped


def build_system_table(
    flex_values: pd.DataFrame,
    system_metrics: pd.DataFrame,
    flex_option: str,
    commodity: str,
    metric_type: str,
    direction: str,
) -> pd.DataFrame:
    """One row per (Scenario, Year): system-wide flex_value (summed across
    countries first, if any) against system-wide cost/emissions/lole/ens."""
    if "Country" in flex_values.columns:
        flex_totals = (
            flex_values.groupby(["Scenario", "Year"])["Value"].sum().reset_index()
        )
    else:
        flex_totals = flex_values

    grouped = flex_totals.merge(
        system_metrics, on=["Scenario", "Year"], how="inner"
    ).rename(columns={"Value": "flex_value"})
    grouped["group"] = "All"
    grouped["flex_option"] = flex_option
    grouped["Commodity"] = commodity
    grouped["metric_type"] = metric_type
    grouped["direction"] = direction
    grouped["group_type"] = "system"
    return grouped


def plot_flex_vs_metrics(
    rows: pd.DataFrame,
    flex_option: str,
    commodity: str,
    metric_type: str,
    group: str,
    output_path: Path,
) -> None:
    """One figure: cost/emissions/LOLE as three subplots, scenario -> colour,
    year -> marker, a degree-1 fit line per subplot as a visual aid. Rows of
    different "direction" (e.g. storage's charge/discharge) simply coexist
    as differently-signed points - not separate plots."""
    metrics = [
        ("cost_beur", "System cost [B€]"),
        ("emissions_kton", "Emissions [kton]"),
        ("lole_h", "LOLE [h]"),
    ]
    scenario_colours = {
        sc: _COLOURS[i % len(_COLOURS)]
        for i, sc in enumerate(sorted(rows["Scenario"].unique()))
    }

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, (col, label) in zip(axes, metrics):
        for (scenario, year), sub in rows.groupby(["Scenario", "Year"]):
            ax.scatter(
                sub[col],
                sub["flex_value"],
                color=scenario_colours[scenario],
                marker=_YEAR_MARKERS.get(str(year), "x"),
                label=f"{scenario} ({year})",
                alpha=0.8,
            )
        if rows[col].nunique() > 1:
            fit = np.polyfit(rows[col], rows["flex_value"], 1)
            xs = np.linspace(rows[col].min(), rows[col].max(), 2)
            ax.plot(xs, np.polyval(fit, xs), color="grey", linestyle="--", linewidth=1)
        ax.axhline(0, color="black", linewidth=0.5)
        ax.set_xlabel(label)
        ax.set_ylabel(f"{flex_option} ({commodity}, {metric_type})")

    handles, labels = axes[0].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    fig.legend(
        by_label.values(),
        by_label.keys(),
        bbox_to_anchor=(1.15, 0.5),
        loc="center left",
        fontsize=8,
    )
    fig.suptitle(f"{flex_option} ({commodity}, {metric_type}) - {group}")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_all(tidy: pd.DataFrame, plots_dir: Path) -> None:
    """One PNG per (flex_option, Commodity, metric_type, group) in `tidy` -
    rows of different direction (e.g. storage charge/discharge) land in the
    same plot as differently-signed points, not separate PNGs."""
    for (flex_option, commodity, metric_type, group), rows in tidy.groupby([
        "flex_option",
        "Commodity",
        "metric_type",
        "group",
    ]):
        safe_group = str(group).replace(" ", "-").replace("/", "-")
        plot_flex_vs_metrics(
            rows,
            flex_option,
            commodity,
            metric_type,
            group,
            plots_dir
            / f"{flex_option.replace(' ', '-')}__{commodity}__{metric_type}__{safe_group}.png",
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
    help="Where to write flex_option_metrics.csv and flex_plots/",
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
    "--scenarios",
    multiple=True,
    default=SCENARIOS,
    help="R20YY-suffixed scenario names to include",
)
@click.option(
    "--years",
    multiple=True,
    default=(),
    help="Restrict to these target year(s) (e.g. 2050). Default: all found.",
)
@click.option(
    "--plots-only",
    is_flag=True,
    default=False,
    help="Skip GDX/model loading entirely and just re-plot flex_plots/ from an existing flex_option_metrics.csv in --output-dir.",
)
def main(
    balmorel_path: str,
    gams_sysdir: str,
    output_dir: str,
    categorization_csv: str,
    reference_scenario: str,
    scenarios: tuple,
    years: tuple,
    plots_only: bool,
):
    output_path = Path(output_dir)
    plots_dir = output_path / "flex_plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    table_path = output_path / "flex_option_metrics.csv"
    columns = [
        "Scenario",
        "Year",
        "group_type",
        "group",
        "flex_option",
        "Commodity",
        "metric_type",
        "direction",
        "flex_value",
        "cost_beur",
        "emissions_kton",
        "lole_h",
        "ens_twh",
    ]

    if plots_only:
        if not table_path.exists():
            print(f"{table_path} not found - run without --plots-only first to generate it.")
            return
        plot_all(pd.read_csv(table_path), plots_dir)
        return

    categorization_path = (
        Path(categorization_csv)
        if categorization_csv
        else output_path / "categorization.csv"
    )
    if not categorization_path.exists():
        print(
            f"{categorization_path} not found - run categorize_countries.py first. Nothing to compute."
        )
        pd.DataFrame(columns=columns).to_csv(table_path, index=False)
        return

    categorization = pd.read_csv(categorization_path)
    category_map = build_reference_category_map(categorization, reference_scenario)
    if not category_map:
        print(
            f"Reference scenario {reference_scenario!r} not found in {categorization_path}. Categorized plots will be empty."
        )

    scenarios = tuple(dict.fromkeys((*scenarios, reference_scenario)))

    if not any(Path(balmorel_path).glob("*/model/MainResults_*.gdx")):
        print(
            f"No MainResults*.gdx files found under {balmorel_path} - nothing to compute yet."
        )
        pd.DataFrame(columns=columns).to_csv(table_path, index=False)
        return

    model = Balmorel(balmorel_path, gams_system_directory=gams_sysdir)
    model.collect_results(suffix_naming_only=True)
    res = model.results

    # `res.get_result()` re-reads/re-parses a symbol's GDX data on every
    # call, with no cache of its own (see AGENTS.md's pybalmorel note, and
    # docs/adr/0007's rationale for estimate_flexibility_needs.py's own
    # pickle cache). This script now calls the same handful of symbols
    # (PRO_YCRAGF, G_CAP_YCRAF, F_CONS_YCRA, ...) many times over - once per
    # commodity view that needs them - so an in-memory cache per symbol name
    # is needed to keep this run in reasonable time/RAM, not just "nice to
    # have" the way it might have been at the smaller original option count.
    _symbol_cache: dict = {}

    def get_symbol(symbol: str):
        if symbol not in _symbol_cache:
            _symbol_cache[symbol] = res.get_result(symbol)
        return _symbol_cache[symbol]

    dispatch_scenarios = select_scenario_names(model.scenario_names)
    region_to_country = region_to_country_map(get_symbol("PRO_YCRAGF"))

    scenario_metrics = extract_scenario_metrics(model, get_symbol, region_to_country, scenarios)
    sys_metrics = system_totals(scenario_metrics)

    tables = []
    for flex_option, commodities in FLEX_OPTIONS.items():
        for commodity, spec in commodities.items():
            for metric_type in _METRIC_TYPES_BY_KIND[spec["kind"]]:
                for direction, flex_values in extract_flex_option_values(
                    get_symbol, region_to_country, flex_option, commodity, metric_type
                ):
                    flex_values = flex_values[flex_values["Scenario"].isin(dispatch_scenarios)]

                    category_table = build_category_table(
                        flex_values, scenario_metrics, category_map, flex_option, commodity, metric_type, direction
                    )
                    system_table = build_system_table(
                        flex_values, sys_metrics, flex_option, commodity, metric_type, direction
                    )
                    tables.extend([
                        t for t in (category_table, system_table) if not t.empty
                    ])  # TODO: This might be the cause of the scripts' RAM intensiveness - consider appending to .csv instead

    tidy = (
        pd.concat(tables, ignore_index=True)
        if tables
        else pd.DataFrame(columns=columns)
    )
    if years:
        tidy = tidy[tidy["Year"].astype(str).isin([str(y) for y in years])]
    tidy.to_csv(table_path, index=False)

    plot_all(tidy, plots_dir)


if __name__ == "__main__":
    main()
