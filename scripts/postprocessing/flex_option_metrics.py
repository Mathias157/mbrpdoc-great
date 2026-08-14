"""
Flexibility-Option Priority Scatter Plots

For each flexibility option (heat pumps, storage, V2G, transmission, ...),
plots its capacity or use (Y-axis) against system cost, emissions, and
security of supply/LOLE (X-axis), one dot per (scenario, year), separately
per Demand/VRE Combined category (default) or system-wide. See CONTEXT.md
("Flexibility option") and docs/adr/0005 for the definitions this script
implements, and the design record captured there for why V2G/demand
response are handled differently from every other option.

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

# Each option's metric_types lists which of "capacity"/"use" are valid to
# request - most support both (see CONTEXT.md "Flexibility option"); V2G and
# demand response are use-only, since their capacity is an exogenous model
# assumption rather than an endogenously optimised decision.
FLEX_OPTIONS = {
    "Electricity transmission": {
        "kind": "transmission",
        "capacity_symbol": "X_CAP_YCR",
        "use_symbol": "X_FLOW_YCR",
        "metric_types": ("capacity", "use"),
    },
    "Hydrogen transmission": {
        "kind": "transmission",
        "capacity_symbol": "XH2_CAP_YCR",
        "use_symbol": "XH2_FLOW_YCR",
        "metric_types": ("capacity", "use"),
    },
    "Heat pumps": {
        "kind": "technology",
        "technologies": ["ELECT-TO-HEAT"],
        "metric_types": ("capacity", "use"),
    },
    "Electricity storage": {
        "kind": "technology",
        "technologies": ["INTRASEASONAL-ELECT-STORAGE"],
        "metric_types": ("capacity", "use"),
    },
    "Heat storage": {
        "kind": "technology",
        "technologies": ["INTERSEASONAL-HEAT-STORAGE", "INTRASEASONAL-HEAT-STORAGE"],
        "metric_types": ("capacity", "use"),
    },
    "Hydrogen storage": {
        "kind": "technology",
        "technologies": ["H2-STORAGE"],
        "metric_types": ("capacity", "use"),
    },
    "Electrolysers": {
        "kind": "technology",
        "technologies": ["ELECTROLYZER"],
        "metric_types": ("capacity", "use"),
    },
    "V2G": {
        "kind": "region_symbol",
        "symbol": "V2G_FLEX_YCR",
        "metric_types": ("use",),
    },
    "Demand response": {
        "kind": "system_only",
        "symbol": "DR_FLEX_Y",
        "metric_types": ("use",),
    },
    "Peaker": {
        "kind": "peaker",
        "metric_types": ("capacity", "use"),
    },
}

# scenario -> colour, year -> marker. Small fixed maps (not analyse.py's
# CLI-only itertools.cycle) since this script isn't invoked through that
# module and wants a deterministic, reproducible mapping across runs.
_COLOURS = ["b", "r", "g", "c", "m", "y", "orange", "purple", "brown", "k"]
_YEAR_MARKERS = {"2030": "o", "2040": "^", "2050": "s"}


def _year_col(df: pd.DataFrame) -> str:
    return "Year" if "Year" in df.columns else "Y"


def _country_col(df: pd.DataFrame) -> str:
    return "Country" if "Country" in df.columns else "RRR"


def extract_flex_option_values(
    model, region_to_country: dict, flex_option: str, metric_type: str
) -> pd.DataFrame:
    """(Scenario, Year, Country, Value) for every option except demand
    response, which returns (Scenario, Year, Value) - it has no country
    dimension in the model's own output (see CONTEXT.md)."""
    spec = FLEX_OPTIONS[flex_option]
    if metric_type not in spec["metric_types"]:
        raise ValueError(
            f"{flex_option!r} has no {metric_type!r} metric - valid: {spec['metric_types']}"
        )

    res = model.results

    if spec["kind"] == "technology":
        symbol = "G_CAP_YCRAF" if metric_type == "capacity" else "PRO_YCRAGF"
        df = res.get_result(symbol).query("Technology in @spec['technologies']")
        return df.groupby(["Scenario", "Year", "Country"])["Value"].sum().reset_index()

    if spec["kind"] == "transmission":
        symbol = (
            spec["capacity_symbol"] if metric_type == "capacity" else spec["use_symbol"]
        )
        df = res.get_result(symbol)
        return df.groupby(["Scenario", "Year", "Country"])["Value"].sum().reset_index()

    if spec["kind"] == "region_symbol":
        # V2G_FLEX_YCR carries no Unit column (a raw domain-fallback
        # symbol) - its physical unit isn't confirmed against a live GDX
        # here, unlike every other symbol this script reads.
        df = res.get_result(spec["symbol"])
        df = df.assign(Country=df[_country_col(df)].map(region_to_country))
        return (
            df
            .dropna(subset=["Country"])
            .groupby(["Scenario", _year_col(df), "Country"])["Value"]
            .sum()
            .reset_index()
            .rename(columns={_year_col(df): "Year"})
        )

    if spec["kind"] == "system_only":
        df = res.get_result(spec["symbol"])
        return df.rename(columns={_year_col(df): "Year"})[["Scenario", "Year", "Value"]]

    if spec["kind"] == "peaker":
        backup = backup_production(
            res.get_result("PRO_YCRAGFST"), commodity="ELECTRICITY"
        )
        if metric_type == "capacity":
            per_region = effective_backup_capacity(backup, nth_max=1)
        else:
            per_region = (
                backup
                .groupby(["Scenario", "Year", "Region"])["Value"]
                .sum()
                .reset_index()
            )
            per_region["Value"] = (
                per_region["Value"] / 1e6
            )  # MWh -> TWh, matching PRO_YCRAGF/X_FLOW_YCR's own "use" unit
        per_region = per_region.assign(
            Country=per_region["Region"].map(region_to_country)
        )
        return (
            per_region
            .dropna(subset=["Country"])
            .groupby(["Scenario", "Year", "Country"])["Value"]
            .sum()
            .reset_index()
        )

    raise ValueError(f"Unknown flex option kind: {spec['kind']!r}")


def extract_scenario_metrics(
    model, region_to_country: dict, scenarios: list | tuple
) -> pd.DataFrame:
    """(Scenario, Year, Country): cost_beur, emissions_kton, lole_h, ens_twh."""
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

    backup = backup_production(res.get_result("PRO_YCRAGFST"), commodity="ELECTRICITY")
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
    metric_type: str,
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
    grouped["metric_type"] = metric_type
    grouped["group_type"] = "category"
    return grouped


def build_system_table(
    flex_values: pd.DataFrame,
    system_metrics: pd.DataFrame,
    flex_option: str,
    metric_type: str,
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
    grouped["metric_type"] = metric_type
    grouped["group_type"] = "system"
    return grouped


def plot_flex_vs_metrics(
    rows: pd.DataFrame,
    flex_option: str,
    metric_type: str,
    group: str,
    output_path: Path,
) -> None:
    """One figure: cost/emissions/LOLE as three subplots, scenario -> colour,
    year -> marker, a degree-1 fit line per subplot as a visual aid."""
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
        ax.set_xlabel(label)
        ax.set_ylabel(f"{flex_option} ({metric_type})")

    handles, labels = axes[0].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    fig.legend(
        by_label.values(),
        by_label.keys(),
        bbox_to_anchor=(1.15, 0.5),
        loc="center left",
        fontsize=8,
    )
    fig.suptitle(f"{flex_option} ({metric_type}) - {group}")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_all(tidy: pd.DataFrame, plots_dir: Path) -> None:
    """One PNG per (flex_option, metric_type, group) in `tidy`."""
    for (flex_option, metric_type, group), rows in tidy.groupby([
        "flex_option",
        "metric_type",
        "group",
    ]):
        safe_group = str(group).replace(" ", "-").replace("/", "-")
        plot_flex_vs_metrics(
            rows,
            flex_option,
            metric_type,
            group,
            plots_dir
            / f"{flex_option.replace(' ', '-')}__{metric_type}__{safe_group}.png",
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
        "metric_type",
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

    dispatch_scenarios = select_scenario_names(model.scenario_names)
    region_to_country = region_to_country_map(res.get_result("PRO_YCRAGF"))

    scenario_metrics = extract_scenario_metrics(model, region_to_country, scenarios)
    sys_metrics = system_totals(scenario_metrics)

    tables = []
    for flex_option, spec in FLEX_OPTIONS.items():
        for metric_type in spec["metric_types"]:
            flex_values = extract_flex_option_values(
                model, region_to_country, flex_option, metric_type
            )
            flex_values = flex_values[flex_values["Scenario"].isin(dispatch_scenarios)]

            category_table = build_category_table(
                flex_values, scenario_metrics, category_map, flex_option, metric_type
            )
            system_table = build_system_table(
                flex_values, sys_metrics, flex_option, metric_type
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
