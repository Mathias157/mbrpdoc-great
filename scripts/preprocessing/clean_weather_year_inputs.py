"""
Clean Weather-Year Inputs Down to Balmorel-Ready .inc Files

For one historical weather year, trims generate_weather_year_inputs.py's
full raw output (Excel review files, per-technology stats, CapDev, ...)
down to just the two .inc file sets a weather year run actually needs -
HourlyDispatch/raw (8760h resolution, feeds rolling runs) and
HourlyDispatch/scaled_long_term (long-term-corrected aggregated resolution,
feeds fullyear runs) - copying them into the shared, gitignored
scripts/Balmorel/weatheryeardata/{data_raw,data_scaled}/<year>/ that
jobs/slurm/fullyear_2050_wy.sh/rolling_2050_wy.sh read from at run time.
Only .inc files are copied (not the .csv siblings in the same source
folders - Balmorel never reads those). See docs/adr/0014.

Meant to be driven by rules/weatheryear.smk (one Snakemake job per year,
after generate_weather_year_inputs.py has produced that year's raw output),
though it works standalone too. --raw-dir's <year>/ subfolder is left in
place afterwards, not deleted - see docs/adr/0014's discussion of why
auto-deleting it here would break Snakemake's own incremental tracking of
generate_weather_year_inputs.py's output; delete data/weatheryear_raw/
by hand once scripts/Balmorel/weatheryeardata/ looks right for every year.

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

# (source subfolder under <raw-dir>/<year>/to_balmorel/HourlyDispatch/,
# destination subfolder under --output-dir) - see docs/adr/0014 and
# CONTEXT.md's "weatheryeardata".
_VARIANTS = [
    ("raw", "data_raw"),
    ("scaled_long_term", "data_scaled"),
]


def copy_variant(source_dir: Path, dest_dir: Path) -> int:
    """Copies every *.inc file from `source_dir` into `dest_dir` (created if
    needed). Returns how many files were copied."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    inc_files = sorted(source_dir.glob("*.inc"))
    for inc_file in inc_files:
        shutil.copy2(inc_file, dest_dir / inc_file.name)
    return len(inc_files)


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


@click.command()
@click.option("--year", type=int, required=True, help="Weather year to clean (1982-2020).")
@click.option(
    "--raw-dir",
    type=str,
    default="data/weatheryear_raw",
    help="Parent folder generate_weather_year_inputs.py wrote <year>/ under.",
)
@click.option(
    "--output-dir",
    type=str,
    default="scripts/Balmorel/weatheryeardata",
    help="Where to write data_raw/<year>/ and data_scaled/<year>/.",
)
def main(year: int, raw_dir: str, output_dir: str):
    hourly_dispatch = Path(raw_dir) / str(year) / "to_balmorel" / "HourlyDispatch"
    if not hourly_dispatch.exists():
        raise click.ClickException(
            f"{hourly_dispatch} not found - run generate_weather_year_inputs.py --year {year} first."
        )

    output_path = Path(output_dir)
    for source_name, dest_name in _VARIANTS:
        source_dir = hourly_dispatch / source_name
        dest_dir = output_path / dest_name / str(year)
        count = copy_variant(source_dir, dest_dir)
        print(f"Weather year {year}: copied {count} .inc file(s) from {source_dir} to {dest_dir}")


if __name__ == "__main__":
    main()
