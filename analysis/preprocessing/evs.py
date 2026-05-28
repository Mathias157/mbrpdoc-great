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
from analysis.utils import setup_plot
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

    # High EV scenario
    fig = plt.figure(figsize=(7, 5))
    gs = fig.add_gridspec(2, hspace=0.3)
    ax1, ax2 = gs.subplots(sharex=True)
    df.plot(ax=ax1, kind="area", legend=False)
    ax1.set_facecolor(fc)
    ax1.set_ylim([0, 250])
    ax1.set_ylabel("EV Vehicles [mio.]")
    ax1.set_title("High EV scenario")

    # Low EV scenario
    df = df / 0.95 * 0.78
    df.plot(ax=ax2, kind="area")
    ax2.set_facecolor(fc)
    ax2.legend(loc="center right", bbox_to_anchor=(1.44, 1.1), ncols=2)
    ax2.set_ylabel("EV Vehicles [mio.]")
    ax2.set_xlabel("")
    ax2.set_title("Low EV scenario")
    ax2.set_ylim([0, 250])
    ax2.set_xlim([2025, 2050])
    fig.savefig(
        "analysis/plots/ev_scenarios.pdf",
        bbox_inches="tight",
        transparent=True,
    )


if __name__ == "__main__":
    main()
