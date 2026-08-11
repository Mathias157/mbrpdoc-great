"""
Aggregate System Cost by VRE/Demand Category, Across Scenarios

For each flexibility-option scenario, sums each country's combined
capex+opex system cost (see functions.costs.combine_capex_opex) into its
Combined category (Demand x VRE, from categorize_countries.py), so costs can
be compared category-by-category across the scenario sweep to see which
flexibility option matters most for which system type.

Category membership is NOT recomputed per scenario. It's fixed once from a
single reference scenario (default base_R2050) and reused for every other
scenario, so each category tracks a constant set of countries across the
whole comparison - see CONTEXT.md ("Reference scenario") and
docs/adr/0004-fixed-category-membership-for-cost-aggregation.md for why.

Created on 11.08.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import sys
from pathlib import Path

# Add repo root (for scripts.postprocessing.categorize_countries) and the
# Balmorel submodule's analysis/ dir (for functions.costs/functions.heatmap,
# which assume analysis/ itself is on sys.path - see AGENTS.md's note on how
# `pixi run analyse` invokes analyse.py) to path for imports.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "Balmorel" / "analysis"))

import click
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from decouple import config
from matplotlib.colors import TwoSlopeNorm
from cmcrameri import cm as cmc
from pybalmorel import Balmorel

from functions.costs import combine_capex_opex
from functions.heatmap import SCENARIOS, SCENARIO_LABELS
from scripts.postprocessing.categorize_countries import COMBINED_CATEGORIES

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def build_reference_category_map(categorization: pd.DataFrame, reference_scenario: str) -> dict:
    """Country -> combined_category, fixed from a single reference scenario
    so every other scenario's cost aggregation groups the same countries."""
    reference = categorization.loc[categorization["Scenario"] == reference_scenario]
    return reference.set_index("Country")["combined_category"].to_dict()


def aggregate_category_costs(combined: pd.DataFrame, category_map: dict, aggfunc: str = "sum") -> pd.DataFrame:
    """Total system cost (B€) per (Scenario, combined_category), grouping
    countries by the fixed `category_map`. Countries missing from it (e.g.
    zero-demand countries categorize_countries.py excludes) are dropped."""
    df = combined.assign(combined_category=combined["Country"].map(category_map))
    df = df.dropna(subset=["combined_category"])

    grouped = df.groupby(["Scenario", "combined_category"])["Value"].agg(aggfunc) / 1e3
    return grouped.rename("cost_beur").reset_index()


def plot_category_cost_heatmap(
    pivot_abs: pd.DataFrame, reference_scenario: str, scenario_labels: dict, output_path: Path
) -> None:
    """Rows = Combined category, columns = scenario. Colour is each cell's
    deviation from `reference_scenario`'s cost for that same category (one
    shared, diverging colourbar - comparable in real B€ across rows); the
    cell text is the category's absolute cost (B€) in that scenario."""
    pivot_abs = pivot_abs.reindex(COMBINED_CATEGORIES)
    deviation = pivot_abs.sub(pivot_abs[reference_scenario], axis=0)

    rows = pivot_abs.index.tolist()
    cols = pivot_abs.columns.tolist()
    cols_display = [scenario_labels.get(c, c) for c in cols]
    nrows, ncols = len(rows), len(cols)

    values = deviation.to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    vmax = np.abs(finite).max() if finite.size else 1.0
    vmax = vmax if vmax > 0 else 1.0
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

    cmap = cmc.vik.copy()
    cmap.set_bad("#D9D9D9")
    masked = np.ma.masked_invalid(values)

    fig, ax = plt.subplots(figsize=(max(ncols * 0.9, 8), max(nrows * 0.6, 5)))
    mesh = ax.pcolormesh(masked, cmap=cmap, norm=norm, edgecolors="white", linewidth=0.5)

    absolute = pivot_abs.to_numpy(dtype=float)
    for i in range(nrows):
        for j in range(ncols):
            if not np.isnan(absolute[i, j]):
                ax.text(j + 0.5, i + 0.5, f"{absolute[i, j]:.1f}", ha="center", va="center", fontsize=8)

    ax.set_xticks(np.arange(ncols) + 0.5)
    ax.set_xticklabels(cols_display, rotation=45, ha="right")
    ax.set_yticks(np.arange(nrows) + 0.5)
    ax.set_yticklabels(rows)
    ax.invert_yaxis()

    reference_label = scenario_labels.get(reference_scenario, reference_scenario)
    ax.set_title(f"System cost by category [B€]\n(cell text = absolute cost, colour = deviation from {reference_label})", fontsize=11, fontweight="bold", pad=15)

    cbar = fig.colorbar(mesh, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label(f"Deviation from {reference_label} [B€]")

    plt.tight_layout()
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
    help="Where to write category_costs.csv and category_costs_heatmap.png",
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
    help="R20YY-suffixed scenario names to aggregate cost for",
)
@click.option(
    "--aggfunc",
    type=click.Choice(["sum", "mean"]),
    default="sum",
    help="How to combine countries' costs within a category",
)
def main(
    balmorel_path: str,
    gams_sysdir: str,
    output_dir: str,
    categorization_csv: str,
    reference_scenario: str,
    scenarios: tuple,
    aggfunc: str,
):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    table_path = output_path / "category_costs.csv"
    columns = ["Scenario", "combined_category", "cost_beur"]

    categorization_path = Path(categorization_csv) if categorization_csv else output_path / "categorization.csv"
    if not categorization_path.exists():
        print(f"{categorization_path} not found - run categorize_countries.py first. Nothing to aggregate.")
        pd.DataFrame(columns=columns).to_csv(table_path, index=False)
        return

    categorization = pd.read_csv(categorization_path)
    category_map = build_reference_category_map(categorization, reference_scenario)
    if not category_map:
        print(f"Reference scenario {reference_scenario!r} not found in {categorization_path}. Nothing to aggregate.")
        pd.DataFrame(columns=columns).to_csv(table_path, index=False)
        return

    # Always pull the reference scenario too, so the heatmap has a 0-deviation column.
    scenarios = tuple(dict.fromkeys((*scenarios, reference_scenario)))

    if not any(Path(balmorel_path).glob("*/model/MainResults_*.gdx")):
        print(f"No MainResults*.gdx files found under {balmorel_path} - nothing to aggregate yet.")
        pd.DataFrame(columns=columns).to_csv(table_path, index=False)
        return

    model = Balmorel(balmorel_path, gams_system_directory=gams_sysdir)
    model.collect_results(suffix_naming_only=True)
    obj = model.results.get_result("OBJ_YCR")

    combined, missing = combine_capex_opex(obj, model.scenario_names, scenarios)
    if missing:
        print(f"Missing investment or operational MainResults for: {missing} - excluded from aggregation.")

    category_costs = aggregate_category_costs(combined, category_map, aggfunc)
    category_costs.to_csv(table_path, index=False)

    if category_costs.empty:
        return

    pivot_abs = category_costs.pivot(index="combined_category", columns="Scenario", values="cost_beur")
    pivot_abs = pivot_abs[[sc for sc in scenarios if sc in pivot_abs.columns]]
    if reference_scenario not in pivot_abs.columns:
        print(f"No cost results for reference scenario {reference_scenario!r} - skipping heatmap.")
        return

    plot_category_cost_heatmap(
        pivot_abs, reference_scenario, SCENARIO_LABELS, output_path / "category_costs_heatmap.png"
    )


if __name__ == "__main__":
    main()
