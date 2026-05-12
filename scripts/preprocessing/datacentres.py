"""
Pre-processing of TYNDP2024 Data

Will generate inputs for datacenter demand and demand response potential

Created on 08.05.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import sys
from pathlib import Path

# Add repo root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import matplotlib.pyplot as plt
import pandas as pd
import click

from scripts.plotting import setup_plot

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def load_tyndp_demand_output():
    """
    Load TYNDP 2024 demand output data from sheet "3_DEMAND_OUTPUT".

    Returns:
        pd.DataFrame: Demand output data indexed by region/scenario combinations.

    Raises:
        FileNotFoundError: If TYNDP2024 file not found.
        ValueError: If sheet "3_DEMAND_OUTPUT" not found or is empty.
    """
    tyndp_file = (
        "data/tyndp-2024/Demand_Scenarios_TYNDP_2024_After_Public_Consultation.xlsb"
    )
    sheet_name = "3_DEMAND_OUTPUT"

    try:
        df = pd.read_excel(tyndp_file, sheet_name=sheet_name, header=[0, 1])
        if df.empty:
            raise ValueError(f"Sheet '{sheet_name}' is empty")
        df.columns = [df.columns[i][1] for i in range(10)] + [
            f"{df.columns[i][0]} {df.columns[i][1]}" for i in range(10, 15)
        ]
        return df
    except FileNotFoundError:
        raise FileNotFoundError(
            f"TYNDP2024 file not found at {tyndp_file}. "
            "Ensure data has been downloaded via Snakemake rule 'download_data'."
        )
    except ValueError as e:
        if "does not contain sheet" in str(e):
            raise ValueError(
                f"Sheet '{sheet_name}' not found in {tyndp_file}. "
                "Check available sheets with: pd.read_excel(..., sheet_name=None)"
            )
        raise


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


@click.group()
@click.option("--dark", is_flag=True, help="Make dark plot?")
@click.pass_context
def main(ctx, dark):
    # Apply color-deficiency-friendly palettes globally
    fc = setup_plot(dark=dark)
    ctx.ensure_object(dict)
    ctx.obj["facecolor"] = fc


@main.command()
@click.argument("scenario", default="DE", type=str)
@click.pass_context
def datacenterload(ctx, scenario):
    """scenario: Either DE (distributed energy) or GA (global ambition)"""

    # Get TYNDP2024 data
    df = load_tyndp_demand_output()
    sc_idx = (
        df.columns.str.contains(scenario)
        | df.columns.str.contains("REF")
        | df.columns.str.contains("COUNTRY")
    )
    df = (
        df
        .query('SUBSECTOR == "Datacenters" and COUNTRY != "EU"')
        .loc[:, sc_idx]
        .pivot_table(index="COUNTRY")
    )

    # Format years
    df.columns = (
        df.columns.str
        .replace(" ", "")
        .str.replace(r"[a-zA-Z ]", "", regex=True)
        .astype(int)
    )

    # Interpolate
    years_to_interp = (
        list(range(2020, 2030)) + list(range(2031, 2040)) + list(range(2041, 2050))
    )
    df_expanded = df.reindex(columns=sorted(set(df.columns) | set(years_to_interp)))
    df_interp = df_expanded.interpolate(axis=1)

    # Plot
    fig, ax = plt.subplots()
    df_interp.T.plot(ax=ax, kind="area")
    ax.set_facecolor(ctx.obj["facecolor"])
    ax.legend(loc="center right", bbox_to_anchor=(1.35, 0.5), ncols=2)
    ax.set_xlim([2019, 2050])
    ax.set_ylabel("Datacenter Electricity Consumption [TWh]")
    fig.savefig(
        "wiki/sources/analyses/plots/datacenter_electricity_consumption.pdf",
        bbox_inches="tight",
        transparent=True,
    )

    # Assume even distribution of datacentres to bidding zones
    df_interp.index = df_interp.index.str.replace("FI", "FIN")
    df_interp.loc["DK", :] = df_interp.loc["DK", :] / 2
    df_interp.loc["DK1", :] = df_interp.loc["DK", :]
    df_interp.loc["DK2", :] = df_interp.loc["DK", :]
    df_interp.loc["SE", :] = df_interp.loc["SE", :] / 4
    df_interp.loc["SE1", :] = df_interp.loc["SE", :]
    df_interp.loc["SE2", :] = df_interp.loc["SE", :]
    df_interp.loc["SE3", :] = df_interp.loc["SE", :]
    df_interp.loc["SE4", :] = df_interp.loc["SE", :]
    df_interp.loc["DE", :] = df_interp.loc["DE", :] / 4
    df_interp.loc["DE4-E", :] = df_interp.loc["DE", :]
    df_interp.loc["DE4-W", :] = df_interp.loc["DE", :]
    df_interp.loc["DE4-S", :] = df_interp.loc["DE", :]
    df_interp.loc["DE4-N", :] = df_interp.loc["DE", :]
    df_interp = df_interp.drop(index=["DK", "SE", "DE"])

    # Making no assumptions for non-EU member states, i.e.: no demand for datacentres.

    df_interp.to_csv("scripts/Balmorel/base/data/DE_DATACENTER.inc")


if __name__ == "__main__":
    main()
