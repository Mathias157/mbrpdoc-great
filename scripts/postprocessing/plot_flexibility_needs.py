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
    ax.axhline(0, color="black", linewidth=0.8)
    if show_total_line:
        ax.hlines(
            totals,
            x - width / 2,
            x + width / 2,
            colors="black",
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
    rows: pd.DataFrame, title: str, output_path: Path, hue_col: str = "group"
) -> None:
    """One figure, one panel per timescale: x-axis = scenario, one *stacked*
    bar per timescale (each `hue_col` value stacked in turn, see
    `_stack_bars`), height = flex_need_twh. `hue_col` defaults to "group"
    (spatial grouping: system/category/country); pass "flex_option" to
    stack by flex option instead (also draws the dashed total-need line,
    see `_stack_bars`)."""
    timescales = ["Daily", "Weekly", "Annual"]
    scenarios = sorted(rows["Scenario"].unique())
    groups = _ordered_hues(hue_col, rows[hue_col].unique())
    x = np.arange(len(scenarios))
    width = 0.6
    ylim = _shared_ylim(rows, hue_col)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
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
        )
        ax.set_xticks(x)
        ax.set_xticklabels(scenarios, rotation=45, ha="right")
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
    rows: pd.DataFrame, title: str, output_path: Path
) -> None:
    """Grid: one row per Combined category, one column per timescale; each
    subplot stacks scenario x flex option (see `_stack_bars`, including the
    dashed total-need line) - the category-level counterpart to
    `plot_flexibility_needs(..., hue_col="flex_option")`'s system-wide plot,
    which can't itself carry a second (category) dimension.

    The y-axis is shared *within* a category's own row (its Daily/Weekly/
    Annual columns), not across categories - different categories can have
    wildly different absolute magnitudes (e.g. "High Demand" vs "Low
    Demand"), so a grid-wide shared axis would flatten smaller categories
    to invisible slivers; each row scaling to its own data keeps every
    category readable while still letting its three timescales be compared
    against each other."""
    timescales = ["Daily", "Weekly", "Annual"]
    categories = sorted(rows["group"].unique())
    flex_options = _ordered_hues("flex_option", rows["flex_option"].unique())
    scenarios = sorted(rows["Scenario"].unique())
    x = np.arange(len(scenarios))
    width = 0.6

    fig, axes = plt.subplots(
        len(categories), 3, figsize=(15, 4 * len(categories)), squeeze=False
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
            )
            ax.set_ylim(row_ylim)
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha="right")
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
def main(output_dir: str, table_csv: str):
    output_path = Path(output_dir)
    plots_dir = output_path / "flex_needs_plots"

    table_path = Path(table_csv) if table_csv else output_path / "flexibility_needs.csv"
    if not table_path.exists():
        print(
            f"{table_path} not found - run estimate_flexibility_needs.py first. Nothing to plot."
        )
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
