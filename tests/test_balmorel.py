"""
Verifications and Validations for Balmorel

Testing Balmorel for the changes, and making plots

Created on 19.05.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

from analysis.utils import load_industry_production
from pybalmorel import Balmorel, IncFile
from pybalmorel.formatting import balmorel_colours

balmorel_colours["WOODPELLETS"] = "#3f7fa3"
balmorel_colours["WOODWASTE"] = "#927b5d"
import numpy as np
import matplotlib.pyplot as plt
import os
from pathlib import Path
import shutil

model = Balmorel(
    "analysis/Balmorel", gams_system_directory=os.getenv("GAMS_SYSTEM_DIR")
)
path = Path("analysis/Balmorel/tests/model")
data_path = Path("analysis/Balmorel/tests/data")
files = [Path("cplex.op4"), Path("Balmorel.gms")]
if not path.exists():
    path.mkdir(parents=True)
if not data_path.exists():
    data_path.mkdir()
for file in files:
    if not file.exists():
        shutil.copy(f"analysis/Balmorel/base/model/{file}", f"{path}/{file}")

# Set temporal resolution
IncFile(
    name="T",
    path=str(data_path),
    prefix="SET T(TTT)  'Time periods within a season in the simulation'",
    body="""\n/\nT010\n/;""",
).save()

IncFile(
    name="S",
    path=str(data_path),
    prefix="SET S(SSS)  'Seasons in the simulation'",
    body="""\n/\nS26\n/;""",
).save()

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def test_transmaxinv(balmorel_already_run: bool = True):

    if not balmorel_already_run:
        # Run tests
        model.run("tests", {"--scenario_name": "unconstrained"})
        model.run("tests", {"--scenario_name": "constrained", "--tyndp2039": "yes"})

    # Load results and plot maps
    model.collect_results(suffix_naming_only=True)

    assert (
        "unconstrained" in model.scfolder_to_scname["tests"]
        and "constrained" in model.scfolder_to_scname["tests"]
    ), (
        "Couldn't find MainResults_unconstrained.gdx and MainResults_constrained.gdx in tests/model! Run this on HPC with balmorel_already_run = False to produce them"
    )

    fig, _ = model.results.plot_map(
        "unconstrained", 2050, "Electricity", lines="Capacity", exo_end="Exogenous"
    )
    fig.savefig("analysis/plots/tests/trans_exogenous_el.pdf")
    fig, _ = model.results.plot_map(
        "unconstrained",
        2050,
        "Electricity",
        lines="Capacity",
    )
    fig.savefig("analysis/plots/tests/trans_unconstrained_el.pdf")
    fig, _ = model.results.plot_map("unconstrained", 2050, "Hydrogen", lines="Capacity")
    fig.savefig("analysis/plots/tests/trans_unconstrained_h2.pdf")
    fig, _ = model.results.plot_map(
        "constrained", 2050, "Electricity", lines="Capacity"
    )
    fig.savefig("analysis/plots/tests/trans_constrained_el.pdf")
    fig, _ = model.results.plot_map("constrained", 2050, "Hydrogen", lines="Capacity")
    fig.savefig("analysis/plots/tests/trans_constrained_h2.pdf")


def test_industry_scenario(balmorel_already_run: bool = True):
    if not balmorel_already_run:
        # Run tests
        model.run(
            "tests",
            {
                "--scenario_name": "high_ee_industry",
                "--high_efficiency_industry": "yes",
            },
        )

    # Load results
    model.collect_results(suffix_naming_only=True)

    assert (
        "unconstrained" in model.scfolder_to_scname["tests"]
        and "high_ee_industry" in model.scfolder_to_scname["tests"]
    ), (
        "Couldn't find MainResults_unconstrained.gdx and MainResults_high_ee_industry.gdx in tests/model! Run this on HPC with balmorel_already_run = False to produce them"
    )

    df_before = load_industry_production("unconstrained", "tests")
    df_after = load_industry_production("high_ee_industry", "tests")

    fig = plt.figure(figsize=(6, 10))
    gs = fig.add_gridspec(2, 2, wspace=0, hspace=0.6)
    (ax1, ax2), (ax3, ax4) = gs.subplots(sharey=True)

    for df, ax_a, ax_b in [
        (df_before, ax1, ax2),
        (df_after, ax3, ax4),
    ]:
        df.query('Commodity=="HEAT" and Value > 1e-1').pivot_table(
            index="Year",
            columns="Fuel",
            values="Value",
            aggfunc=lambda x: np.sum(x) * 3.6,
        ).plot(ax=ax_a, kind="bar", stacked=True, color=balmorel_colours)
        df.query('Commodity=="HYDROGEN"').pivot_table(
            index="Year",
            columns="Fuel",
            values="Value",
            aggfunc=lambda x: np.sum(x) * 3.6,
        ).plot(ax=ax_b, kind="bar", stacked=True, color=balmorel_colours)
        ax_a.set_ylabel("Production for Industry [PJ]")
        ax_b.legend(title="Fuel for H2 Demand")
        ax_a.set_xlabel("")
        ax_a.set_title("Heat Demand")
        ax_b.set_xlabel("")
        ax_b.set_title("Hydrogen Demand")
        ax_a.legend(
            loc="lower center",
            bbox_to_anchor=(1, 1.1),
            ncols=3,
            title="Fuel for Heat Demand",
        )
    fig.savefig(
        "analysis/plots/tests/balmorel_results_industry.pdf",
        bbox_inches="tight",
        transparent=True,
    )
