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

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import click

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
            "Ensure data has been downloaded via Snakemake rule 'download_tyndp2024'."
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
def main():

    pass


@main.command()
@click.argument("scenario", default="DE", type=str)
def datacenterload(scenario):
    """scenario: Either DE (distributed energy) or GA (global ambition)"""

    df = load_tyndp_demand_output()
    sc_idx = (
        df.columns.str.contains(scenario)
        | df.columns.str.contains("REF")
        | df.columns.str.contains("COUNTRY")
    )
    print(df.query('SUBSECTOR == "Datacenters" and COUNTRY != "EU"').loc[:, sc_idx])


if __name__ == "__main__":
    main()
