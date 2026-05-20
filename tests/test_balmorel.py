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

from pybalmorel import Balmorel, IncFile
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


# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def test_transmaxinv(balmorel_already_run: bool = False):

    if not balmorel_already_run:
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
