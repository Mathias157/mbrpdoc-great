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
from pathlib import Path

# Add repo root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from scripts.utils.plotting import setup_plot
from scripts.utils.formats import tynd_to_balmorel
from scripts.utils import load_excel_sheet


# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def add_new_rows(df: pd.DataFrame, region_list: list, row_number: int, to_or_from: str):
    for region in region_list:
        new_row = df.loc[row_number].copy()
        new_row["Value"] = new_row.Value / len(region_list)
        new_row[to_or_from] = region
        df.loc[len(df)] = new_row

    # Set previous row to zero value so the sum will fit later
    df.loc[row_number, "Value"] = 0


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


def main():

    df = load_excel_sheet(
        "wiki/sources/analyses/20231103-TYNDP2024-GRID.xlsx",
        "BALMOREL_XTRANS_POT",
        0,
    )

    sum_before = df.Value.sum()

    # Convert TYNDP region codes to BALMOREL codes
    # First: Append new rows when Balmorel has more regions
    length = df.shape[0]
    for row in range(length):
        from_region = tynd_to_balmorel[df.From[row]]
        to_region = tynd_to_balmorel[df.To[row]]
        if type(from_region) is list:
            add_new_rows(df, from_region, row, "From")
        if type(to_region) is list:
            add_new_rows(df, to_region, row, "To")

    # Second: Convert names
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

    assert sum_before == df.Value.sum(), (
        "Data cleaning went wrong! Sum of capacities not the same as on input side"
    )


if __name__ == "__main__":
    main()
