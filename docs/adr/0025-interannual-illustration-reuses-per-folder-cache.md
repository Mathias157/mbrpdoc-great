# Interannual illustration: separate script, reads the per-folder .gdx_cache rather than fresh GDX

**Status**: accepted

## Context

[0018](0018-standalone-flexibility-illustration-script.md)'s `illustrate_flexibility_needs.py` renders one scenario's residual-load curve (and, optionally, one flex option's own profile) against its own Daily/Weekly/Annual means - deliberately a fresh, uncached, single-scenario-folder GDX read every time, since that's cheap enough not to need caching (see 0018's own measured-cost rationale).

An Interannual illustration (see [0023](0023-interannual-flexibility-needs-batched-compute.md)/[0024](0024-interannual-flexibility-need-provision-concept.md)) needs the same per-year annual mean across *every* weather year in an ensemble, not one scenario - up to several dozen scenario folders. A fresh, uncached read of that many folders is a many-minutes operation (confirmed directly: 3 folders alone took ~5-6 minutes in this environment), not 0018's few-seconds one.

## Decision

- New script `scripts/postprocessing/illustrate_interannual_flexibility_needs.py`, run via pixi task `illustrate-flex-interannual`, for one (source_scenario, run_type, group_type, group[, flex_option]) at a time - a separate script from `illustrate_flexibility_needs.py`, not a mode of it, for the same reason 0018 itself is separate from `plot_flexibility_needs.py`/`estimate_flexibility_needs.py`: genuinely different data-access shape (one folder vs. many).
- **Reads from `estimate_flexibility_needs.py`'s own per-folder `.gdx_cache/<symbol>/<folder>.pkl`** (see 0023) rather than doing a fresh GDX read - a deliberate break from 0018's no-cache philosophy, justified because that philosophy's own cost argument doesn't hold once dozens of folders are involved, and `estimate_flexibility_needs.py` has almost always already built this cache by the time anyone wants to illustrate its interannual output. Never writes to the cache itself - if a requested folder isn't cached, it raises a clear error naming exactly which folders are missing and pointing at `estimate_flexibility_needs.py` (with `--overwrite-cache` if the underlying GDX changed since it last ran), rather than silently reading GDX itself or failing with a bare `FileNotFoundError`.
- Requires `--run-type` (F or R) explicit, never auto-picked - mirrors 0023's own fix for the bug that motivated splitting the accumulator by run type in the first place (mixing Fullyear and Rolling weather years produced a ~150x-too-large Interannual number, confirmed against real data). Illustrating an ensemble that was never a valid pool in `interannual_flexibility_needs.csv` would defeat the point of the illustration.
- Reuses `illustrate_flexibility_needs.py`'s own `_plot_deviation`/`_plot_contribution` (already generic over what `x`/`finer`/`coarser`/`contribution` mean, not hardcoded to hourly/daily/weekly) rather than reimplementing the plotting - same Fig.-1/Fig.-2 visual language, `x` = the weather year itself (an actual calendar year) rather than an hour index, one panel per figure (no zoomed-window pane - there's no finer structure within "across weather years" to zoom into, the same reason 0018's own Annual row already disables its zoom pane).

## Consequences

If `estimate_flexibility_needs.py` is re-run with new/different weather years after this illustration was last generated, the illustration is stale until re-run itself - no automatic invalidation, same as any other cache consumer in this pipeline.
