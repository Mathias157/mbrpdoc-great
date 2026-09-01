# Split estimate_flexibility_needs.py into a compute script and a plotting script

**Status**: accepted

## Context

`estimate_flexibility_needs.py` (ADR 0006, 0007, 0008, 0011) does two very
different things in one `main()`: read `MainResults*.gdx` symbols (via
`Balmorel`/`MainResults`, cached to `<output-dir>/.gdx_cache/*.pkl`),
compute `flexibility_needs.csv`; then read that table straight back out of
memory and render `flex_needs_plots/`. The first half is the expensive
part - even with the `.gdx_cache` pickle cache, a full run reads several
large hourly symbols (`PRO_YCRAGFST` in particular) and has been observed
to climb past 13GB RAM even for a single narrow scenario, before printing
anything at all (see the session that produced ADR 0011). The plotting
half is cheap - it's pure pandas groupby/matplotlib work on an already
tidy CSV.

Bundling them means every plot-formatting tweak (bar width, legend
placement, stacking - exactly the kind of iteration ADR 0011 needed) pays
the full GDX-read cost again. An earlier attempt to work around this added
a `pd.read_csv(table_path)` shortcut gated on `--overwrite-cache` directly
inside `main()`, repurposing a flag whose help text was scoped only to the
GDX symbol cache - a code review of that change (see the session's
Standards/Spec review) flagged it as both undocumented (the flag's own
`--help` text didn't mention it) and actively risky (a rerun with a stale
pre-existing `flexibility_needs.csv` would silently skip recomputing,
making any fix to the compute logic look inert until the CSV was deleted
by hand).

## Decision

- Split into two scripts, each with its own `main()`/CLI, matching the
  module's own docstring ("Run them back to back"):
  - `estimate_flexibility_needs.py` - unchanged compute logic, minus
    plotting. `--overwrite-cache` reverts to its original single meaning
    (re-read GDX symbols instead of `.gdx_cache/*.pkl`). Writes only
    `<output-dir>/flexibility_needs.csv`.
  - `plot_flexibility_needs.py` (new) - reads
    `<output-dir>/flexibility_needs.csv` (or `--table-csv`), writes
    `<output-dir>/flex_needs_plots/`. No GDX/GAMS/`pybalmorel` import at
    all - `matplotlib`/`numpy`/`pandas`/`click` only, so it's fast and
    can't hit the HPC-only `GamsException` failure mode this session also
    ran into. Keeps its own copy of the `COMMODITIES` display-order tuple
    rather than importing it from `estimate_flexibility_needs.py`, to stay
    free of that module's import chain - three fixed strings duplicated is
    cheaper than the coupling.
  - The `pd.read_csv(table_path)`-under-`--overwrite-cache` shortcut is
    removed outright, not fixed in place - the two-script split is a
    strictly better way to get "don't re-read the GDX just to replot" than
    a caching flag ever was, since it can't go stale silently: rerunning
    `plot_flexibility_needs.py` always uses whatever `flexibility_needs.csv`
    is actually on disk, and rerunning `estimate_flexibility_needs.py`
    always recomputes.
- `rules/postprocess.smk`: `estimate_flexibility_needs` now outputs only
  `flexibility_needs.csv`; a new `plot_flexibility_needs` rule takes that
  as input and outputs `flex_needs_plots/`, following `flex_option_metrics`'s
  existing pattern of the DAG doing the input path plumbing via
  `--output-dir` (see AGENTS.md's Snakemake Discipline).

## Consequences

- Two CLI invocations instead of one for a from-scratch run
  (`pixi run postprocess` still runs both, unchanged) - iterating on a
  plot now costs one `python plot_flexibility_needs.py` call instead of a
  full GDX read, at the cost of remembering to rerun
  `estimate_flexibility_needs.py` first when the underlying data actually
  changed (no more automatic staleness masking either way - the old
  bundled script also silently used whatever was last computed if you
  forgot to pass `--overwrite-cache`).
- `flex_option_metrics.py` is not part of this split - it doesn't have the
  same two-order-of-magnitude cost asymmetry between its compute and plot
  halves (see ADR 0008's caching fix), so bundling it was left alone.
