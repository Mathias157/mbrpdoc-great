"""
Industrial Demand Scenarios

Pre-processing for industry demand scenarios

Created on 22.05.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import sys
from pathlib import Path
import os

# Add repo root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import matplotlib.pyplot as plt
from analysis.utils import load_industry_production
import pandas as pd
import numpy as np
import click
from pybalmorel import Balmorel
from pybalmorel.formatting import balmorel_colours

balmorel_colours["Electricity"] = "#3f7fa3"
balmorel_colours["Heat"] = "#f46566"
balmorel_colours["Hydrogen"] = "#927b5d"
balmorel_colours["WOODPELLETS"] = "#3f7fa3"
balmorel_colours["WOODWASTE"] = "#927b5d"

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def load_current_demand():
    model = Balmorel("analysis/Balmorel", os.getenv("GAMS_SYSTEM_DIR"))
    model.load_incfiles("base")

    # Get commodity demands related to industry
    df_el = (
        model
        .get_input("DE")
        .query('DEUSER == "PII"')
        .drop(columns="DEUSER")
        .rename(columns={"RRR": "Country"})
    )
    df_el["Commodity"] = "Electricity"
    df_h = (
        model
        .get_input("DH")
        .query('DHUSER.str.contains("IND")')
        .drop(columns="DHUSER")
        .rename(columns={"AAA": "Country"})
    )
    df_h["Commodity"] = "Heat"
    df_h2 = model.get_input("HYDROGEN_DH2").rename(columns={"CCCRRRAAA": "Country"})
    df_h2["Commodity"] = "Hydrogen"

    df_el.Country = df_el.Country.str[:2]
    df_h.Country = df_h.Country.str[:2]
    df_h2.Country = df_h2.Country.str[:2]
    df = pd.concat((df_el, df_h, df_h2))

    return df


def load_high_ee_demand():

    df = load_current_demand()
    idx = df.query(
        '(Commodity == "Heat" or Commodity == "Hydrogen") and YYY == "2030"'
    ).index
    df.loc[idx, "Value"] = df.loc[idx, "Value"] * 0.87107
    idx = df.query(
        '(Commodity == "Heat" or Commodity == "Hydrogen")  and YYY == "2050"'
    ).index
    df.loc[idx, "Value"] = df.loc[idx, "Value"] * 0.69961

    return df


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


@click.group()
def main():

    pass


@main.command()
def demand_scenarios():
    """What is the current assumed demand in Balmorel?"""

    df_base = load_current_demand()
    df_highee = load_high_ee_demand()
    names = ["base", "high_ee"]

    for i, df in enumerate([df_base, df_highee]):
        fig, ax = plt.subplots(figsize=(7, 4))
        df.query('YYY in ["2016", "2030", "2050"]').pivot_table(
            index="YYY",
            columns="Commodity",
            values="Value",
            aggfunc=lambda x: np.sum(x) / 1e6 * 3.6,
        ).plot(ax=ax, kind="bar", stacked=True, color=balmorel_colours)
        ax.set_ylabel("Industrial Demand [PJ]")
        ax.set_xlabel("")
        ax.legend(loc="lower center", ncols=3, bbox_to_anchor=(0.5, 1))
        fig.savefig(
            f"analysis/plots/balmorel_{names[i]}_industry.pdf",
            bbox_inches="tight",
            transparent=True,
        )


@main.command()
@click.argument("scenario", type=str, default="APS_base_allflex_INV")
def electrify_extent(scenario):
    """To which extent is Balmorel electrifying industry, based on a scenario result?"""

    # Should it be an operational run instead ...?

    # Load result
    # Get PtH production in industry heat areas
    # Get PtH2 production for hydrogen
    df = load_industry_production(scenario)

    fig = plt.figure(figsize=(6, 5))
    gs = fig.add_gridspec(1, 2, wspace=0)
    ax1, ax2 = gs.subplots(sharey=True)  # pyright: ignore

    df.query('Commodity=="HEAT" and Value > 1e-1').pivot_table(
        index="Year",
        columns="Fuel",
        values="Value",
        aggfunc=lambda x: np.sum(x) * 3.6,
    ).plot(ax=ax1, kind="bar", stacked=True, color=balmorel_colours)
    df.query('Commodity=="HYDROGEN"').pivot_table(
        index="Year",
        columns="Fuel",
        values="Value",
        aggfunc=lambda x: np.sum(x) * 3.6,
    ).plot(ax=ax2, kind="bar", stacked=True, color=balmorel_colours)
    ax1.set_ylabel("Production for Industry [PJ]")
    ax2.legend(title="Fuel for H2 Demand")
    ax1.set_xlabel("")
    ax1.set_title("Heat Demand")
    ax2.set_xlabel("")
    ax2.set_title("Hydrogen Demand")
    ax1.legend(
        loc="center", bbox_to_anchor=(1, 1.2), ncols=3, title="Fuel for Heat Demand"
    )
    fig.savefig(
        "analysis/plots/balmorel_results_industry.pdf",
        bbox_inches="tight",
        transparent=True,
    )


if __name__ == "__main__":
    main()
