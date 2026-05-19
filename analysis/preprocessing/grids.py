"""
Assumptions for Grid Development

Will produce input data for Balmorel that restricts transmission expansion to
TYNDP2024 reference grid + candidates until 2039 capacity.

Created on 18.05.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import sys
import os
from pathlib import Path

# Add repo root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np
from pybalmorel import IncFile, Balmorel
from analysis.utils.plotting import setup_plot
from analysis.utils.formats import tynd_to_balmorel
from analysis.utils import load_excel_sheet


# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def load_possible_connections():
    m = Balmorel("analysis/Balmorel", os.getenv("GAMS_SYSTEM_DIR"))
    m.load_incfiles("base")
    possible_connections = m.get_input("XINVCOST").pivot_table(
        index="IRRRE", columns="IRRRI", aggfunc="count", values="Value", fill_value=0
    )
    return possible_connections


def add_new_rows(
    df: pd.DataFrame,
    region_list: list,
    row_number: int,
    to_or_from: str,
):

    for region in region_list:
        new_row = df.loc[row_number].copy()
        new_row["Value"] = new_row.Value
        new_row[to_or_from] = region
        df.loc[len(df)] = new_row

    # Return excess capacity
    excess_capacity = df.loc[row_number, "Value"] * (len(region_list) - 1)

    # Set previous row to zero value so the sum will fit later
    df.loc[row_number, "Value"] = 0

    return excess_capacity


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


def main():

    # Load sheets and Balmorel input data
    df = load_excel_sheet(
        "wiki/sources/analyses/20231103-TYNDP2024-GRID.xlsx",
        "BALMOREL_XTRANS_POT",
        0,
    )

    sum_before = df.Value.sum()
    excess_capacity = 0

    # Convert TYNDP region codes to BALMOREL codes
    # Append new rows when Balmorel has more regions
    for _ in range(2):
        length = df.shape[0]
        for row in range(length):
            try:
                from_region = tynd_to_balmorel[df.From[row]]
                if type(from_region) is list:
                    excess_capacity += add_new_rows(df, from_region, row, "From")
            except KeyError:
                # was converted in the last round
                pass
            try:
                to_region = tynd_to_balmorel[df.To[row]]
                if type(to_region) is list:
                    excess_capacity += add_new_rows(df, to_region, row, "To")
            except KeyError:
                # was converted in the last round
                pass

    # Convert names
    length = df.shape[0]
    for row in range(length):
        try:
            from_region = tynd_to_balmorel[df.From[row]]
            if type(from_region) is str:
                df.loc[row, "From"] = from_region
        except KeyError:
            # print(f"{df.From[row]} already handled")
            pass
        try:
            to_region = tynd_to_balmorel[df.To[row]]
            if type(to_region) is str:
                df.loc[row, "To"] = to_region
        except KeyError:
            # print(f"{df.To[row]} already handled")
            pass

    sum_after_new_rows = df.Value.sum()
    assert sum_before == sum_after_new_rows - excess_capacity, (
        "Data cleaning went wrong! Sum of capacities not the same as on input side"
    )

    # Set connections not possible Balmorel to zero
    drop_rows = []
    for row in range(length):
        try:
            from_region = tynd_to_balmorel[df.From[row]]
            if from_region is None or df.Value[row] == 0:
                drop_rows.append(row)
        except KeyError:
            pass
        try:
            to_region = tynd_to_balmorel[df.To[row]]
            if to_region is None or df.Value[row] == 0:
                drop_rows.append(row)
        except KeyError:
            pass

    df = df.drop(index=np.unique(drop_rows))
    dropped_capacities = sum_after_new_rows - df.Value.sum()

    # Only possible connections allowed
    possible_connections = load_possible_connections()
    for i, _ in df.iterrows():
        from_region = df.loc[i, "From"]
        to_region = df.loc[i, "To"]
        if possible_connections.loc[from_region, to_region] == 0:
            df.loc[i, "Value"] = 0

    # Final, manual adjustments
    df = df.pivot_table(index="From", columns="To", values="Value", aggfunc="sum")

    # Multiple links should be halfed
    df.loc["CZ", "DE4-E"] = df.loc["CZ", "DE4-E"] / 2
    df.loc["CZ", "DE4-S"] = df.loc["CZ", "DE4-S"] / 2
    df.loc["DE4-E", "CZ"] = df.loc["DE4-E", "CZ"] / 2
    df.loc["DE4-S", "CZ"] = df.loc["DE4-S", "CZ"] / 2
    df.loc["DE4-S", "BE"] = df.loc["DE4-S", "BE"] / 2
    df.loc["DE4-W", "BE"] = df.loc["DE4-W", "BE"] / 2
    df.loc["BE", "DE4-S"] = df.loc["BE", "DE4-S"] / 2
    df.loc["BE", "DE4-W"] = df.loc["BE", "DE4-W"] / 2
    df.loc["SE4", "DE4-N"] = df.loc["SE4", "DE4-N"] / 2
    df.loc["SE4", "DE4-E"] = df.loc["SE4", "DE4-E"] / 2
    df.loc["DE4-N", "SE4"] = df.loc["DE4-N", "SE4"] / 2
    df.loc["DE4-E", "SE4"] = df.loc["DE4-E", "SE4"] / 2
    df.loc["NO3", "NO1"] = df.loc["NO3", "NO1"] / 2
    df.loc["NO3", "NO5"] = df.loc["NO3", "NO5"] / 2
    df.loc["NO1", "NO3"] = df.loc["NO3", "NO1"] / 2
    df.loc["NO5", "NO3"] = df.loc["NO3", "NO5"] / 2

    # Internal DE links come from the offshore KF connection between DK2 and DE4-E
    df.loc["DE4-E", "DK2"] += df.loc["DE4-E", "DE4-S"]
    df.loc["DK2", "DE4-E"] += df.loc["DE4-S", "DE4-E"]
    df.loc["DE4-E", "DE4-S"] = 0
    df.loc["DE4-E", "DE4-N"] = 0
    df.loc["DE4-E", "DE4-W"] = 0
    df.loc["DE4-N", "DE4-E"] = 0
    df.loc["DE4-S", "DE4-E"] = 0
    df.loc["DE4-W", "DE4-E"] = 0

    # Create .inc file
    incfile = IncFile(
        name="XMAXINV",
        prefix="TABLE XMAXINV(IRRRE,IRRRI)   'Max investment in transmission capacity between two regions for each simulated year(each 5th year)'\n$ifi not %tyndp2039%==yes  $goto unconstrained\n",
        suffix="\n$label unconstrained\n;",
        path="analysis/Balmorel/base/data",
    )
    idx = df < 1e-5
    df[idx] = ""
    incfile.body = df.fillna("")
    incfile.body.index.name = ""
    incfile.body.columns.name = ""
    incfile.save()


if __name__ == "__main__":
    main()
