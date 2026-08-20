"""
Plot Daily / Weekly / Annual Flexibility Needs

Reads flexibility_needs.csv (written by estimate_flexibility_needs.py) and
renders the Daily/Weekly/Annual bar charts into flex_needs_plots/, per
commodity (electricity, heat, hydrogen - see docs/adr/0009): residual
load's own system/category breakdown, and each flexibility option's own
timescale decomposition, system-wide and per Combined category (see
docs/adr/0007, 0008). Bars are stacked, with flex-option bars carrying a
demand/supply sign (heat pumps/electrolysers stack below the zero line,
everything else above - see docs/adr/0011): negative values in the CSV are
expected, not a bug.

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

from pathlib import Path

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #

# Display order for the per-commodity plot loop below - must match
# estimate_flexibility_needs.COMMODITIES. Kept as its own copy rather than
# importing that module, so this script stays free of its GDX/GAMS/
# pybalmorel import chain (the whole point of the split, see module
# docstring) - it's three fixed strings, not worth the coupling.
COMMODITIES = ("ELECTRICITY", "HEAT", "HYDROGEN")


def _stack_bars(
    ax,
    x: np.ndarray,
    sub: pd.DataFrame,
    hue_col: str,
    hues: list,
    scenarios: list,
    width: float,
) -> None:
    """Draws one stacked bar per `x` position (scenario): each `hues` value's
    flex_need_twh is stacked in turn - positive values upward from the
    running positive top, negative values downward from the running
    negative bottom. Residual load's own rows (group_type system/category)
    are always >=0, so they simply stack upward; flex-option rows
    (group_type flex_option_system/flex_option_category) carry a
    demand/supply sign attached by estimate_flexibility_needs.py's `main()`
    (see docs/adr/0011), so e.g. heat pumps/electrolysers stack below the
    zero line rather than on top of supply-side options."""
    bottom_pos = np.zeros(len(x))
    bottom_neg = np.zeros(len(x))
    for hue in hues:
        heights = np.array([
            sub.loc[
                (sub["Scenario"] == sc) & (sub[hue_col] == hue), "flex_need_twh"
            ].sum()
            for sc in scenarios
        ])
        pos = np.where(heights >= 0, heights, 0.0)
        neg = np.where(heights < 0, heights, 0.0)
        bars = ax.bar(x, pos, width, bottom=bottom_pos, label=hue)
        color = bars.patches[0].get_facecolor()
        ax.bar(x, neg, width, bottom=bottom_neg, color=color)
        bottom_pos += pos
        bottom_neg += neg
    ax.axhline(0, color="black", linewidth=0.8)


def plot_flexibility_needs(
    rows: pd.DataFrame, title: str, output_path: Path, hue_col: str = "group"
) -> None:
    """One figure, one panel per timescale: x-axis = scenario, one *stacked*
    bar per timescale (each `hue_col` value stacked in turn, see
    `_stack_bars`), height = flex_need_twh. `hue_col` defaults to "group"
    (spatial grouping: system/category/country); pass "flex_option" to
    stack by flex option instead."""
    timescales = ["Daily", "Weekly", "Annual"]
    scenarios = sorted(rows["Scenario"].unique())
    groups = sorted(rows[hue_col].unique())
    x = np.arange(len(scenarios))
    width = 0.6

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, timescale in zip(axes, timescales):
        sub = rows[rows["timescale"] == timescale]
        _stack_bars(ax, x, sub, hue_col, groups, scenarios, width)
        ax.set_xticks(x)
        ax.set_xticklabels(scenarios, rotation=45, ha="right")
        ax.set_title(f"{timescale} flexibility need")
        ax.set_ylabel("Flexibility need [TWh/a]")

    handles, labels = axes[0].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    fig.legend(
        by_label.values(),
        by_label.keys(),
        bbox_to_anchor=(1.1, 0.5),
        loc="center left",
        fontsize=8,
    )
    fig.suptitle(f"Flexibility needs ({title})")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_flex_option_category_grid(
    rows: pd.DataFrame, title: str, output_path: Path
) -> None:
    """Grid: one row per Combined category, one column per timescale; each
    subplot stacks scenario x flex option (see `_stack_bars`) - the
    category-level counterpart to `plot_flexibility_needs(...,
    hue_col="flex_option")`'s system-wide plot, which can't itself carry a
    second (category) dimension."""
    timescales = ["Daily", "Weekly", "Annual"]
    categories = sorted(rows["group"].unique())
    flex_options = sorted(rows["flex_option"].unique())
    scenarios = sorted(rows["Scenario"].unique())
    x = np.arange(len(scenarios))
    width = 0.6

    fig, axes = plt.subplots(
        len(categories), 3, figsize=(15, 4 * len(categories)), squeeze=False
    )
    for row_i, category in enumerate(categories):
        cat_rows = rows[rows["group"] == category]
        for col_i, timescale in enumerate(timescales):
            ax = axes[row_i][col_i]
            sub = cat_rows[cat_rows["timescale"] == timescale]
            _stack_bars(ax, x, sub, "flex_option", flex_options, scenarios, width)
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha="right")
            if row_i == 0:
                ax.set_title(f"{timescale} flexibility need")
            if col_i == 0:
                ax.set_ylabel(f"{category}\nFlex need [TWh/a]")

    handles, labels = axes[0][0].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    fig.legend(
        by_label.values(),
        by_label.keys(),
        bbox_to_anchor=(1.06, 0.5),
        loc="center left",
        fontsize=8,
    )
    fig.suptitle(f"Flexibility-option use, by Combined category ({title})")
    fig.tight_layout()
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
def main(output_dir: str, table_csv: str):
    output_path = Path(output_dir)
    plots_dir = output_path / "flex_needs_plots"

    table_path = Path(table_csv) if table_csv else output_path / "flexibility_needs.csv"
    if not table_path.exists():
        print(f"{table_path} not found - run estimate_flexibility_needs.py first. Nothing to plot.")
        return

    tidy = pd.read_csv(table_path)
    if tidy.empty:
        print(f"{table_path} is empty - nothing to plot.")
        return

    plots_dir.mkdir(parents=True, exist_ok=True)

    for commodity in COMMODITIES:
        by_commodity = tidy[tidy["Commodity"] == commodity]
        if by_commodity.empty:
            continue

        for group_type in ("system", "category"):
            subset = by_commodity[by_commodity["group_type"] == group_type]
            if subset.empty:
                continue
            plot_flexibility_needs(
                subset,
                f"{group_type}, {commodity}",
                plots_dir / f"{group_type}_{commodity}.png",
            )

        option_system_rows = by_commodity[
            by_commodity["group_type"] == "flex_option_system"
        ]
        if not option_system_rows.empty:
            plot_flexibility_needs(
                option_system_rows,
                f"flexibility options, system-wide ({commodity})",
                plots_dir / f"system_by_option_{commodity}.png",
                hue_col="flex_option",
            )

        option_category_rows = by_commodity[
            by_commodity["group_type"] == "flex_option_category"
        ]
        if not option_category_rows.empty:
            plot_flex_option_category_grid(
                option_category_rows,
                commodity,
                plots_dir / f"category_by_option_{commodity}.png",
            )

    print(f"Wrote plots to {plots_dir}.")


if __name__ == "__main__":
    main()
