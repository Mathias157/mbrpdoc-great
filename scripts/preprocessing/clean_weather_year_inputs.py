"""
Clean Weather-Year Inputs Down to Balmorel-Ready .inc Files

For one historical weather year, trims generate_weather_year_inputs.py's
full raw output (Excel review files, per-technology stats, ...) down to
just the .inc file sets a weather year run - or a future weather-year-aware
investment run - could need, copying them into the shared, gitignored
scripts/Balmorel/weatheryeardata/<variant>/<year>/ that
jobs/slurm/fullyear_2050_wy.sh/rolling_2050_wy.sh read from at run time:

- HourlyDispatch/raw -> data_raw (8760h resolution, feeds rolling runs)
- HourlyDispatch/scaled_long_term -> data_scaled (long-term-corrected,
  aggregated resolution, feeds fullyear runs)
- CapDev/{raw,scaled_long_term,scaled_full_year} -> capdev_raw/
  capdev_scaled_long_term/capdev_scaled_full_year - investment-resolution
  timesteps. Nothing in this pipeline reads these yet (weather year runs
  never re-invest, see docs/adr/0013) - kept anyway for a possible future
  weather-year-aware investment run.

Not a blind copy: `base/model/bb4datainc.inc` only picks up a scenario's
own `data/<NAME>.inc` override if the *filename* matches exactly what it
`$INCLUDE`s, and some of WEATHERYEAR's output uses a different filename or
is split across several files where Balmorel expects one. Per file (see
docs/adr/0015 for how each was verified against the actual override
mechanism, not assumed):
- PASSTHROUGH_FILES: already the exact expected filename, and (for
  WND_VAR_T.inc/SOLE_VAR_T.inc specifically) already end with their own
  `X(model domain) = X1(raw domain); X1(...)=0;` GAMS reassignment -
  confirmed by inspecting the actual file content, not assumed from the
  base data's equivalent chain file. Copied byte-for-byte.
- RENAME_FILES: WEATHERYEAR's own `_WY` suffix stripped - already the
  right GAMS format (direct `X(idx...) = value;` assignment statements),
  just the wrong filename for bb4datainc.inc's override check to find.
- CONCAT_FILES: WEATHERYEAR splits electricity/heat demand by
  DEUSER/DHUSER category (OTHER+RESE, RESIDENTIAL+RESH+TERTIARY);
  Balmorel's override slot expects one DE_VAR_T.inc/DH_VAR_T.inc. Safe to
  concatenate since these are also direct assignment statements, not
  TABLE declarations - each line just sets its own (region, user-type,
  season, time) cell independently. INDUSTRY_DE_VAR_T/INDUSTRY_DH_VAR_T
  are NOT weather-dependent and are deliberately left untouched (base
  default keeps being used).

Only .inc files are copied - not the .csv siblings in the same source
folders (Balmorel never reads those), and not COP_WY_air_air.inc/
COP_WY_air_water.inc (the annual-average COP companion to COP_VAR_T -
out of scope for now, not wired into any override chain yet).

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

# Source path under <raw-dir>/<year>/to_balmorel/, destination subfolder
# under --output-dir - see docs/adr/0014 and CONTEXT.md's "weatheryeardata".
_VARIANTS = [
    ("HourlyDispatch/raw", "data_raw"),
    ("HourlyDispatch/scaled_long_term", "data_scaled"),
    ("CapDev/raw", "capdev_raw"),
    ("CapDev/scaled_long_term", "capdev_scaled_long_term"),
    ("CapDev/scaled_full_year", "capdev_scaled_full_year"),
]

# See module docstring and docs/adr/0015 for why each of these three is
# handled the way it is.
PASSTHROUGH_FILES = [
    "WND_VAR_T.inc",
    "SOLE_VAR_T.inc",
    "WNDFLH.inc",
    "SOLEFLH.inc",
    "SEASONALCOP_COP_VAR_T_WY_air_air.inc",
    "SEASONALCOP_COP_VAR_T_WY_air_water.inc",
]

RENAME_FILES = {
    "WTRRSVAR_S_WY.inc": "WTRRSVAR_S.inc",
    "WTRRRVAR_T_WY.inc": "WTRRRVAR_T.inc",
    "WTRRSFLH_WY.inc": "WTRRSFLH.inc",
    "WTRRRFLH_WY.inc": "WTRRRFLH.inc",
}

CONCAT_FILES = {
    "DE_VAR_T.inc": ["DE_VAR_T_OTHER.inc", "DE_VAR_T_RESE.inc"],
    "DH_VAR_T.inc": ["DH_VAR_T_RESIDENTIAL.inc", "DH_VAR_T_RESH.inc", "DH_VAR_T_TERTIARY.inc"],
}


def copy_variant(source_dir: Path, dest_dir: Path) -> int:
    """Applies PASSTHROUGH_FILES/RENAME_FILES/CONCAT_FILES against every
    *.inc file in `source_dir`, writing the result into `dest_dir`
    (created if needed). Returns how many destination files were written.
    Silently skips any source file that isn't listed anywhere above (see
    module docstring - e.g. the COP_WY_*.inc annual-average files)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    written = 0

    for filename in PASSTHROUGH_FILES:
        source_file = source_dir / filename
        if source_file.exists():
            shutil.copy2(source_file, dest_dir / filename)
            written += 1

    for source_name, dest_name in RENAME_FILES.items():
        source_file = source_dir / source_name
        if source_file.exists():
            shutil.copy2(source_file, dest_dir / dest_name)
            written += 1

    for dest_name, source_names in CONCAT_FILES.items():
        source_files = [source_dir / name for name in source_names]
        if all(f.exists() for f in source_files):
            with open(dest_dir / dest_name, "w") as out:
                for source_file in source_files:
                    out.write(source_file.read_text())
            written += 1

    return written


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
    help="Where to write each variant's <year>/ subfolder - see _VARIANTS.",
)
def main(year: int, raw_dir: str, output_dir: str):
    to_balmorel = Path(raw_dir) / str(year) / "to_balmorel"
    if not to_balmorel.exists():
        raise click.ClickException(
            f"{to_balmorel} not found - run generate_weather_year_inputs.py --year {year} first."
        )

    output_path = Path(output_dir)
    for source_subpath, dest_name in _VARIANTS:
        source_dir = to_balmorel / source_subpath
        dest_dir = output_path / dest_name / str(year)
        count = copy_variant(source_dir, dest_dir)
        print(f"Weather year {year}: wrote {count} .inc file(s) from {source_dir} to {dest_dir}")


if __name__ == "__main__":
    main()
