"""
Generate Raw Weather-Year Inputs

For one historical weather year (1982-2020), runs pybalmorel's WEATHERYEAR
module against the manually-downloaded raw model outputs in
data/weatheryear_inputs/ (CorRES/demand/hydro/COP - see
config/weatheryear.yml's weatheryear_inputs_folder), producing that year's
full .inc/Excel output tree under --output-dir/<year>/ - the same shape
pybalmorel's own docs describe. Reproduces, inside this repo, what
previously lived only as a hand-run process into the sibling pybalmorel
repo's results/ folder (see docs/adr/0014).

This is intentionally the "raw" half only - most of what WEATHERYEAR writes
(Excel review files, per-technology stats, HourlyDispatch) is never used
downstream. clean_weather_year_inputs.py trims one year's output from here
down to just the CapDev raw/scaled_full_year .inc files a weather year run
actually needs, into scripts/Balmorel/weatheryeardata/. Meant to be driven
by rules/weatheryear.smk (one Snakemake job per year, wildcarded on --year,
kept out of the main Snakefile DAG - see docs/adr/0014) rather than invoked
directly, though it works standalone too.

Created on 21.08.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import click
from pybalmorel import WEATHERYEAR

# ------------------------------- #
#            1. Main              #
# ------------------------------- #


@click.command()
@click.option("--year", type=int, required=True, help="Weather year to generate inputs for (1982-2020).")
@click.option("--config", type=str, default="config/weatheryear.yml", help="Path to the WEATHERYEAR config YAML.")
@click.option(
    "--output-dir",
    type=str,
    default="data/weatheryear_raw",
    help="Parent folder for this year's raw WEATHERYEAR output (written to <output-dir>/<year>/).",
)
def main(year: int, config: str, output_dir: str):
    print(f"Generating weather year {year} inputs into {output_dir}/{year}/ ...")
    wy = WEATHERYEAR(year=year, config_fn=config, output_folder=output_dir)
    wy.get_vre_data()
    wy.get_vre_related_files()
    wy.get_demand_data()
    wy.get_hydro_data()
    wy.get_cop_data()
    print(f"Done: weather year {year}.")


if __name__ == "__main__":
    main()
