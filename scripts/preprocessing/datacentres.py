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
import numpy as np
import click
from pybalmorel import IncFile

from scripts.plotting import setup_plot

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def load_excel_sheet(filename, sheet_name, headers):
    """
    Load excel file with sheet name

    Returns:
        pd.DataFrame: Demand output data indexed by region/scenario combinations.

    Raises:
        FileNotFoundError: If TYNDP2024 file not found.
        ValueError: If sheet "3_DEMAND_OUTPUT" not found or is empty.
    """
    try:
        df = pd.read_excel(filename, sheet_name=sheet_name, header=headers)
        if df.empty:
            raise ValueError(f"Sheet '{sheet_name}' is empty")
        return df
    except FileNotFoundError:
        raise FileNotFoundError(
            f"File not found at {filename}. "
            "Ensure data has been downloaded via Snakemake rule 'download_data'."
        )
    except ValueError as e:
        if "does not contain sheet" in str(e):
            raise ValueError(
                f"Sheet '{sheet_name}' not found in {filename}. "
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
    fc = setup_plot(dark=dark, colour_range=tuple(range(0, 255, int(255 / 40))))
    ctx.ensure_object(dict)
    ctx.obj["facecolor"] = fc


@main.command()
@click.argument("scenario", default="DE", type=str)
@click.pass_context
def datacenterload(ctx, scenario):
    """scenario: Either DE (distributed energy) or GA (global ambition)"""

    # Get TYNDP2024 data
    tyndp_file = (
        "data/tyndp-2024/Demand_Scenarios_TYNDP_2024_After_Public_Consultation.xlsb"
    )
    sheet_name = "3_DEMAND_OUTPUT"
    df = load_excel_sheet(tyndp_file, sheet_name, [0, 1])
    df.columns = [df.columns[i][1] for i in range(10)] + [
        f"{df.columns[i][0]} {df.columns[i][1]}" for i in range(10, 15)
    ]
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

    # Get AF25 data
    filename = "data/af25/AF25.xlsx"
    sheet_name = "Elforbrug"
    df_af25 = load_excel_sheet(filename, sheet_name, 131)
    df_af25 = df_af25.iloc[:2, 2:]
    df_af25["COUNTRY"] = ["DK1", "DK2"]
    df_af25 = df_af25.pivot_table(index="COUNTRY", aggfunc=lambda x: np.sum(x) / 1e3)
    df_af25.columns = df_af25.columns.astype(int)

    # Interpolate
    df = pd.concat((df, df_af25))
    years_to_interp = (
        list(range(2020, 2030)) + list(range(2031, 2040)) + list(range(2041, 2050))
    )
    df_expanded = df.reindex(columns=sorted(set(df.columns) | set(years_to_interp)))
    df_interp = df_expanded.interpolate(axis=1)

    # Assume even distribution of datacentres to bidding zones
    # NOTE: Making no assumptions for non-EU member states, i.e.: no demand for datacentres in Norway, UK etc.
    df_interp.index = df_interp.index.str.replace("FI", "FIN")
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

    # Plot
    fig, ax = plt.subplots()
    df_interp.T.plot(ax=ax, kind="area")
    ax.set_facecolor(ctx.obj["facecolor"])
    ax.legend(loc="center right", bbox_to_anchor=(1.5, 0.5), ncols=2)
    ax.set_xlim([2025, 2050])
    ax.set_ylabel("Datacenter Electricity Consumption [TWh]")
    fig.savefig(
        "wiki/sources/analyses/plots/datacenter_electricity_consumption.pdf",
        bbox_inches="tight",
        transparent=True,
    )

    # Make .inc file
    df_interp = df_interp.drop(columns=[2019 + i for i in range(6)]) * 1e6
    df_interp.index.name = ""

    IncFile(
        name="DE_DATACENTER",
        path="scripts/Balmorel/base/data",
        prefix="TABLE   DE_DATACENTER(RRR,YYY)   'Datacenter electricity consumption (MWh)'\n",
        body=df_interp,
        suffix="\n;\nDE(YYY,RRR,'DATACENTER')=DE_DATACENTER(RRR,YYY);\nDE_DATACENTER(RRR,YYY)=0;",
    ).save()


if __name__ == "__main__":
    main()
