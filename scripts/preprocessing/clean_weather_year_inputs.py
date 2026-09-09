"""
Clean Weather-Year Inputs Down to Balmorel-Ready .inc Files

For one historical weather year, trims generate_weather_year_inputs.py's
full raw output (Excel review files, per-technology stats, ...) down to
just the .inc file sets a weather year run needs, copying them into the
shared, gitignored scripts/Balmorel/weatheryeardata/<variant>/<year>/ that
jobs/slurm/fullyear_2050_wy.sh/rolling_2050_wy.sh read from at run time:

- CapDev/raw -> data_raw (feeds rolling runs)
- CapDev/scaled_full_year -> data_scaled (feeds fullyear runs)
- to_balmorel/*.inc (topology: GGG/AAA/INVDATASET/INVDATA/GKFX/... -
  see docs/adr/0021) -> both variants, unchanged by which run type

Deliberately from CapDev, not HourlyDispatch - confirmed with the user
(2026-08-21) that HourlyDispatch's output isn't needed here at all, so it's
not read or copied. CapDev/scaled_long_term is likewise not copied - not
needed by either job script.

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
  base data's equivalent chain file. Copied byte-for-byte, aside from the
  cross-cutting cleanups below.
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
  default keeps being used). DE_VAR_T.inc/DH_VAR_T.inc additionally get
  `$include '../../base/data/<NAME>.inc';` prepended (CONCAT_FILE_BASE_INCLUDE)
  - unlike WTRRRFLH/DH, these are plain absolute-value assignments covering
  only their own DEUSER/DHUSER categories, not scaling factors, but every
  other DEUSER/DHUSER/region/time combination still needs the base default
  - see docs/adr/0021 for why the base has to load *first* here too, for a
  different reason than WTRRRFLH/WTRRSFLH (a later plain assignment always
  overwrites, regardless of $onMulti, so the base can't safely go last).
- FILES_NEEDING_T001_DEDUP (currently just WTRRSVAR_S_WY.inc): workaround
  for an upstream pybalmorel WEATHERYEAR bug that gives this (AAA,SSS)-only
  parameter a spurious T dimension. Applied on top of RENAME_FILES.
- FLH_BASE_FALLBACK_FILES (WTRRRFLH.inc/WTRRSFLH.inc): WEATHERYEAR's
  WTRRRFLH_WY.inc/WTRRSFLH_WY.inc values are scaling factors relative to
  the base full-load-hours (typically close to 1.0), not absolute hours,
  and cover only a subset of AAA (e.g. 25 of 48 for WTRRRFLH in the 1982
  raw output) - see docs/adr/0021 for how this was confirmed (both against
  the actual values and by testing GAMS's $onMulti semantics directly)
  and why the base file's own $include has to run *before* the scaling
  assignments, not after.
- STATIC_FILES (every top-level to_balmorel/*.inc except
  STATIC_FILE_EXCLUDE - GGG_renewable, AAA_renewable, INVDATASET_renewables,
  INVDATA_renewable, RRRAAA_renewable, CCCRRRAAA_renewable, GKFX_renewable,
  ALLOWEDINV, ANNUITYCG_renewables, DISCOST_H_renewable, GDATA_renewable,
  G_renewable, DH_RESH/DH_RESIDENTIAL/DH_TERTIARY): technology/topology
  additions that don't depend on the weather year's actual met data (only
  on which turbines/PV/regions are enabled) - see docs/adr/0021. Not fully
  guaranteed identical across years (raw-data gaps for one region/turbine
  in one year can drop a member that another year has), so each year's own
  output is copied rather than reusing a single canonical year - each WY
  scenario only needs to be internally consistent with its own data, not
  identical to every other year. Already self-contained pybalmorel output
  (own `$onMulti` + SET/PARAMETER/TABLE header) - copied as-is, aside from
  the cross-cutting cleanups below. How a WY scenario's `data/` folder
  actually gets these included by GAMS is not yet wired up by this script -
  see docs/adr/0021's Consequences.
- STATIC_FILE_EXCLUDE (currently just SUBTECHGROUPKPOT.inc): not copied at
  all, at the user's request.
- DH.inc (DH_INC_CONTENT): not produced by WEATHERYEAR itself, but written
  unconditionally here - see docs/adr/0021 for why DH_RESH.inc/
  DH_RESIDENTIAL.inc/DH_TERTIARY.inc (self-multiplicative, same shape as
  WTRRRFLH/WTRRSFLH) need this composing override to load the base DH
  first, and why that specifically doesn't need $onMulti despite the
  surface similarity to WTRRRFLH/WTRRSFLH.
- ALBANIA_WIND_FALLBACK: WNDFLH.inc/WND_VAR_T.inc (PASSTHROUGH_FILES) get
  one line appended unconditionally, permanently pointing Albania's
  turbine-less "Existing" onshore category at the SP199-HH150 profile - see
  docs/adr/0021.

Two cross-cutting cleanups are applied to every file this script writes
(both the CapDev variant files above and STATIC_FILES), regardless of
category, since both are pybalmorel-output artifacts unrelated to the
per-file logic above:
- DK3 (a legacy, currently-unused Baltic offshore zone - not part of this
  model) is dropped everywhere it appears, even though config/weatheryear.yml
  still lists DK3_OFF in Regions_to_keep (see docs/adr/0021 for why this is
  filtered here instead of at the config, and why WND_VAR_T.inc/
  SOLE_VAR_T.inc need a different, alignment-preserving removal since DK3
  is a TABLE column there, not an independent line - naively dropping the
  header line desyncs every data row's column count).
- RG1_OFF/RG2_OFF/RG3_OFF (how WEATHERYEAR labels offshore resource grades
  in GDATA_renewable.inc's GDSUBTECHGROUP column) are normalised to bare
  RG1/RG2/RG3, matching SUBTECHGROUPKPOT's SUBTECH_GROUP domain - see
  docs/adr/0021.

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

import re
from pathlib import Path

import click

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #

# Source path under <raw-dir>/<year>/to_balmorel/, destination subfolder
# under --output-dir - see docs/adr/0014 and CONTEXT.md's "weatheryeardata".
_VARIANTS = [
    ("CapDev/raw", "data_raw"),
    ("CapDev/scaled_full_year", "data_scaled"),
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

# Workaround for an upstream pybalmorel WEATHERYEAR bug (see docs/adr/0015):
# WTRRSVAR_S is a (AAA,SSS)-only parameter (base/data/WTRRSVAR_S.inc has no T
# index), but WEATHERYEAR's export gives every row a spurious 'T001'..'T168'
# T-dimension, repeating the same S-level value across every T instead of
# writing it once. Drop until a pybalmorel patch lands: keep only each row's
# T001 copy, then strip the ', 'T001'' index entirely.
FILES_NEEDING_T001_DEDUP = {"WTRRSVAR_S_WY.inc"}

# See module docstring (FLH_BASE_FALLBACK_FILES) and docs/adr/0021.
FLH_BASE_FALLBACK_FILES = {"WTRRRFLH.inc", "WTRRSFLH.inc"}

# TABLE-format files where a region is a COLUMN, not a row/line - dropping
# "any line containing DK3" would only strip the header label and desync
# every data row's column count. See _strip_dk3_wide_table_column.
WIDE_TABLE_FILES = {"WND_VAR_T.inc", "SOLE_VAR_T.inc"}

# STATIC_FILES (see module docstring) this script does NOT copy through,
# even though they're produced as top-level to_balmorel/*.inc output.
STATIC_FILE_EXCLUDE = {"SUBTECHGROUPKPOT.inc"}

# Albania (AL) lacks its own onshore profile for some turbines in some
# years' raw CorRES data (e.g. AL_VRE-ONS_SP199-HH100_RG1 is present in
# 1985's WEATHERYEAR output but missing from 1982's - see docs/adr/0021).
# Rather than leave AL's "Existing" onshore category undefined whenever
# that gap recurs, permanently borrow the SP199-HH150 profile for it -
# appended unconditionally (not just as a gap-fill) since "Existing" has no
# turbine-specific profile of its own to begin with.
ALBANIA_WIND_FALLBACK = {
    "WNDFLH.inc": "WNDFLH('AL_ONS_Existing_RG1') = WNDFLH('AL_VRE-ONS_SP199-HH150_RG1');\n",
    "WND_VAR_T.inc": (
        "WND_VAR_T('AL_ONS_Existing_RG1',SSS,TTT)"
        "=WND_VAR_T('AL_VRE-ONS_SP199-HH150_RG1',SSS,TTT);\n"
    ),
}

# DH_RESH.inc/DH_RESIDENTIAL.inc/DH_TERTIARY.inc (copied through by
# STATIC_FILES) are themselves self-multiplicative
# (DH(...)=DH(...)*factor;), same shape as WTRRRFLH/WTRRSFLH - they need
# the base DH loaded first. Unlike WTRRRFLH.inc, base/data/DH.inc's own
# `PARAMETER DH(...);` line is a bare re-declaration with no attached data
# list, which GAMS allows without $onMulti (confirmed: only a second data
# *list* into an already-populated symbol needs $onMulti, not a bare
# re-declaration) - see docs/adr/0021.
DH_INC_CONTENT = (
    "$include '../../base/data/DH.inc';\n"
    "$include '../data/DH_RESH.inc';\n"
    "$include '../data/DH_RESIDENTIAL.inc';\n"
    "$include '../data/DH_TERTIARY.inc';\n"
)

# DE_VAR_T_OTHER.inc/DE_VAR_T_RESE.inc and DH_VAR_T_RESIDENTIAL.inc/
# DH_VAR_T_RESH.inc/DH_VAR_T_TERTIARY.inc (CONCAT_FILES sources) are plain
# absolute-value assignments (e.g. DE_VAR_T(...)=value;), not scaling
# factors - but each only covers its own DEUSER/DHUSER categories, so the
# base default still has to load first to fill every other DEUSER/DHUSER/
# region/time combination they don't touch. Since these are plain
# assignments (not a $onMulti data list), no $onMulti is needed here
# either - see docs/adr/0021.
CONCAT_FILE_BASE_INCLUDE = {
    "DE_VAR_T.inc": "$include '../../base/data/DE_VAR_T.inc';\n",
    "DH_VAR_T.inc": "$include '../../base/data/DH_VAR_T.inc';\n",
}

_RG_OFF_TO_BARE = {"RG1_OFF": "RG1", "RG2_OFF": "RG2", "RG3_OFF": "RG3"}

_FLH_ASSIGNMENT = re.compile(
    r"^(?P<param>WTRRRFLH|WTRRSFLH)\((?P<idx>'[^']+')\)\s*=\s*(?P<val>[^;]+);",
    re.MULTILINE,
)


def _dedup_t001(text: str) -> str:
    kept_lines = (line for line in text.splitlines(keepends=True) if "T001" in line)
    return "".join(kept_lines).replace(", 'T001'", "")


def _drop_dk3_lines(text: str) -> str:
    """Safe where each region occupies its own line (SET member lists,
    PARAMETER assignment lists, or a TABLE where the region is the row key,
    e.g. SUBTECHGROUPKPOT.inc) - NOT safe for WIDE_TABLE_FILES, see
    _strip_dk3_wide_table_column."""
    return "".join(line for line in text.splitlines(keepends=True) if "DK3" not in line)


def _strip_dk3_wide_table_column(text: str) -> str:
    """WND_VAR_T.inc/SOLE_VAR_T.inc are TABLE(SSS,TTT,AAA) declarations with
    AAA as columns - dropping the header line would remove the DK3 label
    but leave every data row with one more value than the (now shorter)
    header has columns, desyncing all columns after it. Instead, locate the
    DK3 column's exact character span in the header (matching header token i
    to row token i - confirmed against a real GAMS compile that plain
    re-joining with normalised whitespace, even without removing anything,
    corrupts this TABLE format; only excising the exact original span
    survives a real `gams` compile) and excise the same span from every row.
    """
    lines = text.splitlines(keepends=True)
    try:
        header_idx = next(i for i, line in enumerate(lines) if "DK3" in line)
    except StopIteration:
        return text
    header_matches = list(re.finditer(r"\S+", lines[header_idx]))
    drop_positions = [i for i, m in enumerate(header_matches) if "DK3" in m.group()]
    if not drop_positions:
        return text

    def _splice(line: str, matches: list, positions: list) -> str:
        spans = []
        for pos in positions:
            start = matches[pos - 1].end() if pos > 0 else 0
            end = matches[pos].end()
            spans.append((start, end))
        for start, end in sorted(spans, reverse=True):
            line = line[:start] + line[end:]
        return line

    lines[header_idx] = _splice(lines[header_idx], header_matches, drop_positions)

    in_table = True
    for i in range(header_idx + 1, len(lines)):
        line = lines[i]
        if in_table and line.strip() == ";":
            in_table = False
            continue
        if not in_table:
            continue
        row_matches = list(re.finditer(r"\S+", line))
        if len(row_matches) != len(header_matches) + 1:
            continue
        # Row token 0 is the row label (e.g. 'S01.T001'); values start at 1.
        lines[i] = _splice(line, row_matches, [p + 1 for p in drop_positions])
    return "".join(lines)


def _replace_rg_off(text: str) -> str:
    for off, bare in _RG_OFF_TO_BARE.items():
        text = text.replace(off, bare)
    return text


def _finalize(text: str, filename: str) -> str:
    """Cross-cutting cleanups applied to every file this script writes -
    see module docstring."""
    if filename in WIDE_TABLE_FILES:
        text = _strip_dk3_wide_table_column(text)
    else:
        text = _drop_dk3_lines(text)
    return _replace_rg_off(text)


def _make_flh_multiplicative(text: str) -> str:
    """WTRRRFLH_WY.inc/WTRRSFLH_WY.inc values are scaling factors - rewrite
    "WTRRRFLH('AT_A') = 1.0145;" into "WTRRRFLH('AT_A') = 1.0145*WTRRRFLH('AT_A');"
    so it scales whatever is already loaded (the base default - see
    _with_base_fallback) instead of replacing it outright."""

    def _sub(m: re.Match) -> str:
        param, idx, val = m.group("param"), m.group("idx"), m.group("val")
        return f"{param}({idx}) = {val}*{param}({idx});"

    return _FLH_ASSIGNMENT.sub(_sub, text)


def _with_base_fallback(text: str, param_name: str) -> str:
    """$include the full base default first (under $onMulti, since
    bb4datainc.inc's own PARAMETER header already declared this symbol) so
    every AAA has a value before the scaling assignments run - AAA the
    weather year doesn't cover simply keep the base value untouched. See
    docs/adr/0021 for why this must run before, not after, the assignments
    below (confirmed against a real `gams` $onMulti test: a value already
    assigned is kept, so loading defaults afterwards would only fill gaps,
    not let the scaling assignments read them)."""
    return (
        "$onMulti\n"
        f"$include '../../base/data/{param_name}.inc';\n"
        "$offMulti\n"
    ) + text


def copy_variant(source_dir: Path, dest_dir: Path, to_balmorel: Path) -> int:
    """Applies PASSTHROUGH_FILES/RENAME_FILES/CONCAT_FILES against every
    *.inc file in `source_dir`, plus STATIC_FILES (to_balmorel's own
    top-level *.inc files) from `to_balmorel`, writing the result into
    `dest_dir` (created if needed). Returns how many destination files were
    written. Silently skips any source file in `source_dir` that isn't
    listed anywhere above (see module docstring - e.g. the
    COP_WY_*.inc annual-average files)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    written = 0

    for filename in PASSTHROUGH_FILES:
        source_file = source_dir / filename
        if source_file.exists():
            text = _finalize(source_file.read_text(), filename)
            fallback = ALBANIA_WIND_FALLBACK.get(filename, "")
            if fallback and not text.endswith("\n"):
                text += "\n"
            text += fallback
            (dest_dir / filename).write_text(text)
            written += 1

    for source_name, dest_name in RENAME_FILES.items():
        source_file = source_dir / source_name
        if source_file.exists():
            text = source_file.read_text()
            if source_name in FILES_NEEDING_T001_DEDUP:
                text = _dedup_t001(text)
            text = _finalize(text, dest_name)
            if dest_name in FLH_BASE_FALLBACK_FILES:
                param_name = dest_name.removesuffix(".inc")
                text = _with_base_fallback(_make_flh_multiplicative(text), param_name)
            (dest_dir / dest_name).write_text(text)
            written += 1

    for dest_name, source_names in CONCAT_FILES.items():
        source_files = [source_dir / name for name in source_names]
        if all(f.exists() for f in source_files):
            text = "".join(f.read_text() for f in source_files)
            text = _finalize(text, dest_name)
            text = CONCAT_FILE_BASE_INCLUDE.get(dest_name, "") + text
            (dest_dir / dest_name).write_text(text)
            written += 1

    for source_file in sorted(to_balmorel.glob("*.inc")):
        if source_file.name in STATIC_FILE_EXCLUDE:
            continue
        text = _finalize(source_file.read_text(), source_file.name)
        (dest_dir / source_file.name).write_text(text)
        written += 1

    (dest_dir / "DH.inc").write_text(DH_INC_CONTENT)
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
        count = copy_variant(source_dir, dest_dir, to_balmorel)
        print(f"Weather year {year}: wrote {count} .inc file(s) from {source_dir} to {dest_dir}")


if __name__ == "__main__":
    main()
