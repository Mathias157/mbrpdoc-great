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

from scripts.utils.plotting import setup_plot
from scripts.utils import load_excel_sheet

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


def main():

    df = load_excel_sheet(
        "wiki/sources/analyses/20231103-TYNDP2024-GRID.xlsx",
        "BALMOREL_XTRANS_POT",
        0,
    )

    print(df)


if __name__ == "__main__":
    main()
