"""
Create Weather Year Scenario Folders

Scaffolds one scenario folder per weather year for a chosen, already-invested
source scenario - `<source>_WY<year>/`, flat siblings of `<source>/` directly
under scripts/Balmorel/ (see CONTEXT.md's "WY folder", docs/adr/0013/0014).
Each folder gets just what a weather year run's `data`/`model` steps need
- nothing an investment run, `logerror/`, or `output/` would otherwise
produce (GAMS creates `logerror/logerinc` itself on demand, per
Balmorel.gms's own `$ifi not dexist ... execute 'mkdir -p ...'`, so it isn't
pre-created here either):

- `data/`: whatever's in the source scenario's own `data/` folder (in
  practice just Y.inc for most scenarios) - overwritten at run time anyway
  by fullyear_2050_wy.sh/rolling_2050_wy.sh's own Y/T/S and weather-file
  swaps, copied here only so a scenario with something extra in `data/`
  isn't silently missing it.
- `model/`: only the static files the WY job scripts actually reference -
  Balmorel.gms, cplex.op2, cplex.op4, balopt_full.opt, balopt_roll.opt.
  Not balopt_inv.opt (no investment step) or cplex.op3 (no warm-start
  support in the WY fullyear script - see docs/adr/0014).
- `simex/`: created empty. `fullyear_2050_wy.sh` populates it at run time
  from `../<source>/simex_INV/` directly - never from a copy made here (a
  WY folder never has its own simex_INV, there's no investment run to
  produce one).
- `config.sh`: copied verbatim from the source scenario.

Never touches HPC or Snakemake - this is local scaffolding, meant to be
`rsync`'d up (`pixi run sync-up`) and run via `jobs/slurm/submit_weather_years.sh`
afterwards. Exposed as the `create-weather-year-scenarios` pixi task.

Created on 21.08.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import shutil
from pathlib import Path

import click

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #

# 1982-2020 - see CONTEXT.md's "Weather year". Edit this list directly for
# a one-off subset instead of the full range (--years also overrides it).
YEARS = list(range(1982, 2021))

MODEL_FILES_TO_COPY = ["Balmorel.gms", "cplex.op2", "cplex.op4", "balopt_full.opt", "balopt_roll.opt"]


def create_weather_year_folder(balmorel_path: Path, scenario: str, year: int) -> Path:
    """Scaffolds `<balmorel_path>/<scenario>_WY<year>/` from `<scenario>`'s
    own data/model/config.sh (see module docstring for exactly what's
    copied and why). No-op (just returns the path) if the folder already
    exists, so re-running for a partially-created year range is safe."""
    source = balmorel_path / scenario
    target = balmorel_path / f"{scenario}_WY{year}"
    if target.exists():
        print(f"{target} already exists - skipping.")
        return target

    (target / "data").mkdir(parents=True)
    (target / "model").mkdir()
    (target / "simex").mkdir()

    for source_file in (source / "data").iterdir():
        if source_file.is_file():
            shutil.copy2(source_file, target / "data" / source_file.name)

    for filename in MODEL_FILES_TO_COPY:
        shutil.copy2(source / "model" / filename, target / "model" / filename)

    shutil.copy2(source / "config.sh", target / "config.sh")
    return target


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


@click.command()
@click.option(
    "--scenario",
    type=str,
    required=True,
    help="Source scenario folder name (e.g. H2NHPN) whose simex_INV every weather year run reuses.",
)
@click.option("--balmorel-path", type=str, default="scripts/Balmorel", help="Path to the top level of Balmorel scenario folders")
@click.option(
    "--years",
    multiple=True,
    type=int,
    default=(),
    help="Weather years to create folders for. Default: this script's own YEARS constant (1982-2020).",
)
def main(scenario: str, balmorel_path: str, years: tuple):
    balmorel_dir = Path(balmorel_path)
    source = balmorel_dir / scenario
    if not source.is_dir():
        raise click.ClickException(f"Source scenario folder {source} does not exist.")

    selected_years = list(years) if years else YEARS
    print(f"Creating {len(selected_years)} weather year scenario folder(s) for source scenario {scenario!r}...")
    for year in selected_years:
        folder = create_weather_year_folder(balmorel_dir, scenario, year)
        print(f"  {folder}")


if __name__ == "__main__":
    main()
