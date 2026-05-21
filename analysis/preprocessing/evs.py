"""
EV Data Assumptions

Pre-processing for EV scenarios

Created on 21.05.2026
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
from analysis.formats import setup_plot
import numpy as np
import click

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def load_ev_data():
    df = pd.read_csv("data/balanza2026/EV_BEV_available.csv")
    return df


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


@click.command()
@click.option("--dark", is_flag=True, help="Make dark plot?")
def main(dark):

    fc = setup_plot(dark=dark, colour_range=tuple(range(0, 255, int(255 / 40))))
    df = load_ev_data().pivot_table(
        index="YYY", columns="RRR", values="Value", aggfunc=lambda x: np.sum(x) / 1e6
    )

    fig, ax = plt.subplots()
    df.plot(ax=ax, kind="area")
    ax.set_facecolor(fc)
    ax.legend(loc="center right", bbox_to_anchor=(1.5, 0.5), ncols=2)
    ax.set_ylabel("EV Vehicles [mio.]")
    ax.set_xlabel("")
    ax.set_xlim([2025, 2050])
    fig.savefig(
        "analysis/plots/ev_evolution_before.pdf",
        bbox_inches="tight",
        transparent=True,
    )


if __name__ == "__main__":
    main()
