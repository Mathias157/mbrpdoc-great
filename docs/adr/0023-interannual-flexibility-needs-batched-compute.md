# Interannual flexibility needs: batched, per-folder-cached compute inside estimate_flexibility_needs.py

**Status**: accepted

## Context

Weather-year (WY) scenario sweeps (`base_WY<year>_F2050`, see [CONTEXT.md](../../CONTEXT.md)'s **Weather year run**/**WY folder**) currently produce Daily/Weekly/Annual flexibility need per weather year independently; nothing quantifies variability *across* years, despite that being the whole point of running a weather-year ensemble.

The preliminary F2050 WY results in `build_postprocess_WY/` happen to use a reduced 624-row/year resolution (confirmed directly: 52 weeks x 12, vs. 8736 for ordinary scenarios). The true R2050 weather-year runs, still landing, will use the full 8736-row resolution like every other scenario in this repo.

`_get_result_cached()` currently caches one pkl per symbol covering *every* located scenario folder at once (confirmed: 2.5GB for the 7 hourly symbols across 35 preliminary weather years). At full resolution this scales roughly 14x - tens of GB resident before the per-scenario loop even starts.

## Decision

- Add Interannual as a 4th level of the existing Daily/Weekly/Annual decomposition (need *and* provision, at all three existing group levels - system/category/country). See [0024](0024-interannual-flexibility-need-provision-concept.md) for the concept itself.
- Compute it inside `estimate_flexibility_needs.py`'s existing per-scenario loop, not a new script: capture each weather year's `annual_mean` (already computed inside `_period_means`, previously discarded) for residual load and for each flex option's `hourly_net`, into a small scalar accumulator (weather year x group_type x group x commodity [x flex_option] -> float) that persists across the whole run. After the loop, pool by source scenario (parsed from `<source>_WY<year>` scenario names) using a **fixed 8736-hour weight**, not row-count-implicit weighting. Writes a second output file, `interannual_flexibility_needs.csv`, alongside the unchanged `flexibility_needs.csv` (written even when empty, for non-WY output dirs, so nothing downstream breaks when pointed at a plain scenario set).
- Read scenario folders in fixed-size batches (new `--batch-size` option, default 10) when no explicit `--scenarios` is given: prune `model.scenarios` to one batch, `collect_results()` just that batch, read the 7 symbols, discard the batch's big frames before the next batch loads. `--scenarios` keeps today's single-pass behaviour unbatched - its whole purpose is already "keep this small and cheap."
- Cache each symbol **per scenario folder name** (`.gdx_cache/<symbol>/<folder>.pkl`, split via `model.scfolder_to_scname`), not per batch index - batch composition and folder-enumeration order can change freely between runs (new weather years landing, `--batch-size` retuned) without invalidating or misattributing anything already cached.
- New operating rule this depends on: a scenario folder holds at most one run of each type - one `_INV`, one `_F<year>`, one `_R<year>`, never two runs of the same type sharing a folder (e.g. two different weather years' fullyear results landing in one folder, which would make per-folder caching ambiguous). Documented in [CONTEXT.md](../../CONTEXT.md)'s **Scenario name** entry, `AGENTS.md`, and `README.md`.

## Considered options

- **Append each weather year's full hourly (Season,Time,Value) table across years and generalize `_period_means` one level up** (row-count-implicit weighting - correct under variable resolution without tracking hours-per-year explicitly). Rejected once full R2050 resolution was accounted for: holding every weather year's hourly table simultaneously reintroduces the exact memory problem batching exists to solve. This was only viable because the *preliminary* numbers happen to be coarse - not something to design the long-term architecture around.
- **A new standalone second-stage script** (`estimate_interannual_flexibility_needs.py`) re-deriving `rl`/`hourly_net` from `.gdx_cache` independently, mirroring the existing estimate/plot split. Rejected - that split exists specifically to keep the *plotting* script free of a GDX dependency; this step still needs the hourly data, just not a second read of it, and the main loop already has the exact tables needed, in memory, at exactly the right point.
- **Cache files keyed by positional batch index** (`_batch1.pkl`, `_batch2.pkl`, ...). Rejected - batch membership depends on scenario-folder enumeration order, which isn't guaranteed stable and will shift as new weather years land; per-folder keys are already stable via `scfolder_to_scname`.

## Consequences

If a future weather year's data genuinely isn't full 8736 rows (a partial or failed run), it should be excluded from the Interannual pool with a logged warning rather than silently mis-weighted by the fixed 8736 constant - not yet implemented.
