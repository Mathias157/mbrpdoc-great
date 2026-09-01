# Standalone, cache-free illustration script for flexibility-need/provision curves

**Status**: accepted

## Context

`estimate_flexibility_needs.py`/`plot_flexibility_needs.py` ([0007](0007-flexibility-option-timescale-decomposition.md),
[0012](0012-split-flexibility-needs-compute-from-plotting.md), [0017](0017-correlation-based-flexibility-provision.md))
only ever surface the *aggregated* Daily/Weekly/Annual TWh numbers — the
underlying hourly residual-load curve and each flex option's own deviation
curve are computed in-memory and discarded. That makes "what does 4.2 TWh of
Daily flexibility need actually mean" hard to build intuition for. Checked
against Geis et al. (2026)'s own Fig. 1 (residual load vs. its period mean,
shaded above/below to show the balancing requirement) and Fig. 2 (one
technology's own hourly profile next to its FlexSign-weighted contribution) —
this pipeline has the numbers but never the picture.

## Decision

New script `scripts/postprocessing/illustrate_flexibility_needs.py`, run via
pixi task `illustrate-flex`, for one (scenario, group_type, group[,
flex_option]) at a time, selected by explicit CLI args — a diagnostic tool
run by hand while sanity-checking a scenario, not a batch/report artifact.

- Renders both a Fig.-1-style panel (residual load vs. its period mean,
  shaded need) and, when `--flex-option` is given, a Fig.-2-style pair for
  that option's own profile and its FlexSign-weighted contribution — shown
  together, since the latter's sign is derived from the former's own
  FlexCurve.
- One 3-panel figure, Daily/Weekly/Annual, with which panel(s) render
  controllable via CLI rather than hardcoded to always show all three.
- Two temporal views per panel: a full-year overview (to spot where the
  interesting variability is) and a zoomed illustrative window, picked via
  `--window`.
- Calls `estimate_flexibility_needs.py`'s existing pure functions directly
  (`country_residual_load`, `flex_sign`, `flexibility_needs`,
  `flexibility_provision`, `flex_option_hourly_net`, `_period_means`) rather
  than reimplementing any of them, so the illustration can't silently drift
  from what `flexibility_needs.csv` actually reports.
- Lives in this repo's `scripts/postprocessing/` (not
  `scripts/Balmorel/analysis/analyse.py`): it needs `FLEX_OPTIONS`, Combined
  category, and the correlation-based provision method, all GREAT-specific.
  Adding even a thin Click wrapper to `analyse.py` would make the
  `scripts/Balmorel` submodule import upward from its parent repo, inverting
  the dependency direction the submodule/top-level split exists to
  guarantee (see AGENTS.md's "Two Different Toolkits").
- A new file, not a mode of `plot_flexibility_needs.py`: that script is
  deliberately CSV-only/GDX-free per [0012](0012-split-flexibility-needs-compute-from-plotting.md);
  this one needs a live GDX read, so folding it in would undo that split.
- Not wired into `postprocess.smk`'s DAG — on-demand only.

**Never reads or writes the shared `.gdx_cache/*.pkl`** (unlike every other
script in this pipeline) — always a fresh, scenario-scoped `pybalmorel` read.
Deliberate, checked against real numbers rather than assumed:

- A single scenario *folder* (`base`, itself bundling 3 scenario names —
  INV/F2050/R2050) read fresh for all 7 needed symbols peaks around 7.4 GB
  RSS and takes ~7.5 minutes, dominated by `PRO_YCRAGFST` (17M rows, 12 GB
  `memory_usage(deep=True)` alone) and `F_CONS_YCRAST` (15M rows, 9.9 GB) —
  both driven by `pybalmorel.utils.symbol_to_df`'s per-record Python `for`
  loop over `GamsVariable`/`GamsEquation` records, not a vectorized GDX read.
  This is inherent to `pybalmorel`, not something this script controls.
- The shared cache doesn't reliably exist for the symbol that matters most
  anyway: `build_postprocess/.gdx_cache/PRO_YCRAGFST.pkl` is currently a
  truncated, unreadable pickle (`UnpicklingError: pickle data was
  truncated`) — confirmed directly, not assumed. Depending on it as a
  performance shortcut would mean depending on a file that's already broken
  for at least this symbol.
- Reading one scenario at a time and never writing back also sidesteps a
  separate, pre-existing risk: `estimate_flexibility_needs.py`'s own
  `--scenarios` flag prunes which folders get located *before*
  `collect_results()` runs, so a scenario-scoped cold-cache run would write
  a scenario-limited pickle to the same shared path a later unscoped run
  reads from — silently dropping every other scenario's data. Left
  unfixed here (cache lifecycle for the main pipeline is managed by hand,
  not something this ADR takes on) but worth knowing about if it resurfaces.

## Consequences

- Every `illustrate-flex` invocation costs ~7-8 minutes and ~7-8 GB RAM per
  scenario inspected — fine for occasional by-hand use, not for illustrating
  many scenarios in one sitting or running unattended.
- `estimate_flexibility_needs.py`'s cache-truncation risk (cold cache +
  `--scenarios`) remains live and unfixed; if it starts blocking real work
  again, it needs its own decision, not a silent patch bundled into
  unrelated work.
- If a future need arises to illustrate many scenarios in bulk, the
  no-shared-cache decision here should be revisited rather than assumed to
  still hold.
