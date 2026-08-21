# Reconcile weather-year .inc filenames/formats with Balmorel's override mechanism

**Status**: accepted

## Context

Simply copying `WEATHERYEAR` module output into a WY folder's `data/` isn't
enough for Balmorel to actually use it. `base/model/bb4datainc.inc` (and
the `seasonalCOP` addon's own `seasonalCOP_pardefine.inc`) implement a
per-parameter override: `$if EXIST '../data/<NAME>.inc' $include it; else
$include '../../base/data/<NAME>.inc'`. A weather-year file only takes
effect if its *filename* matches exactly what that check looks for -
several of WEATHERYEAR's output files don't.

Two GAMS data formats are in play, and confusing them is the actual risk
here (not a missing filename, which just silently falls back to base data
- a wrong format can silently load *zero* data, or worse, silently
overwrite data another file just loaded, neither of which errors):

- **Direct assignment**: `X('idx1','idx2',...) = value;`, one line per
  value. Works immediately once $included under the right name; safe to
  concatenate multiple such files together.
- **Table + reassign**: `TABLE X1(<raw index order>) ...;` followed by a
  required `X(<model index order>) = X1(<raw order>); X1(...)=0;`
  reassignment - `base/model/bb4datainc.inc`'s own pre-declaration of `X`
  is empty (`PARAMETER X(...) 'desc';`, terminated immediately since this
  codebase runs with `$setglobal semislash ";"`), so without that
  reassignment `X` just stays at zero. `WND_VAR_T`/`SOLE_VAR_T`/`DE_VAR_T`/
  `DH_VAR_T`/`COP_VAR_T` (seasonalCOP) all use this base-side.

An earlier pass through this investigation incorrectly concluded
`WND_VAR_T.inc`/`SOLE_VAR_T.inc` needed the reassignment appended - checking
the actual WEATHERYEAR output (not just its `TABLE X1(...)` header) showed
it's already there. Recorded here as the reason every file below was
verified against real generated output, not inferred from the base data's
equivalent file.

## Decision

Per-file handling, implemented in `clean_weather_year_inputs.py`'s
`PASSTHROUGH_FILES`/`RENAME_FILES`/`CONCAT_FILES`:

- **Passthrough** (`WND_VAR_T.inc`, `SOLE_VAR_T.inc`, `WNDFLH.inc`,
  `SOLEFLH.inc`, `SEASONALCOP_COP_VAR_T_WY_air_air.inc`,
  `SEASONALCOP_COP_VAR_T_WY_air_water.inc`): already the exact expected
  filename. The first two are table+reassign format but already complete
  (verified, see Context); the rest are direct-assignment format, complete
  as-is.
- **Rename** (`WTRRSVAR_S_WY.inc`, `WTRRRVAR_T_WY.inc`,
  `WTRRSFLH_WY.inc`, `WTRRRFLH_WY.inc` -> same names minus `_WY`):
  direct-assignment format already, just need the filename
  `bb4datainc.inc` is checking for. Note this drops
  `WTRRSFLH.inc`/`WTRRRFLH.inc`'s base-side fallback line (defaults an
  area with hydro capacity but no explicit FLH to Norway's value) - accepted
  as low-risk since weather-year data is expected to cover the same areas.
- **Concatenate** (`DE_VAR_T_OTHER.inc` + `DE_VAR_T_RESE.inc` ->
  `DE_VAR_T.inc`; `DH_VAR_T_RESIDENTIAL.inc` + `DH_VAR_T_RESH.inc` +
  `DH_VAR_T_TERTIARY.inc` -> `DH_VAR_T.inc`): WEATHERYEAR splits
  electricity/heat demand by DEUSER/DHUSER category; Balmorel's override
  slot expects one file. Safe because both are direct-assignment format -
  each line sets its own cell independently, so concatenation order
  doesn't matter. `INDUSTRY_DE_VAR_T`/`INDUSTRY_DH_VAR_T` are not
  weather-dependent and are deliberately left alone (base default keeps
  being used) - confirmed with the user, not assumed.
- **Not handled**: `COP_WY_air_air.inc`/`COP_WY_air_water.inc` (the
  annual-average `COP(AAA,GGG)` companion to `COP_VAR_T`) - out of scope,
  not wired into any override chain. Flagged, not silently dropped without
  mention.

Two files can't be produced by trimming WEATHERYEAR's per-year output at
all, since they're either static across every year or deliberately
year-independent - both written directly by
`create_weather_year_scenarios.py` instead, once per WY folder:

- **`data/SEASONALCOP_COP_VAR_T.inc`**: a wrapper chaining three sources -
  `base/data/SEASONALCOP_COP_VAR_T_GROUND-WTR.inc` (fixed; ground-source
  COP doesn't vary meaningfully with weather year) *first*, reassigned via
  `COP_VAR_T(IA,G,SSS,TTT) = COP_VAR_T1(SSS,TTT,IA,G); COP_VAR_T1(...)=0;`,
  then the two weather-year air-source files (already direct-assignment
  format) *after*. Order matters: reassigning ground-wtr's table+reassign
  form is unconditional over the full `(IA,G,SSS,TTT)` domain, so doing it
  *after* the air-source assignments would silently zero every cell
  `COP_VAR_T1` doesn't cover (i.e. every non-ground-wtr generator),
  wiping out the air-source data that was just set.
- **`data/INDIVUSERS_DH_VAR_T.inc`**: written empty on purpose. Weather
  year runs suppress this addon's contribution entirely rather than
  falling back to the source scenario's non-weather-year-aware data - the
  override check only cares that the file *exists*, not that it has
  content, so an empty (comment-only) file is a valid, deliberate no-op.

Separately, `WTRRSVAR_S_WY.inc`'s content itself is wrong upstream, not just
misnamed: `WTRRSVAR_S` is `(AAA,SSS)`-only (`base/data/WTRRSVAR_S.inc` has
no T index - reservoir inflow varies by season, not by hour), but
`pybalmorel`'s `WEATHERYEAR` class exports it with a spurious `'T001'` ..
`'T168'` T-dimension, repeating the same S-level value across every T
instead of writing it once (confirmed: values are identical across T for a
given area/season, unlike the genuinely T-varying `WTRRRVAR_T`). Worked
around in `clean_weather_year_inputs.py`'s `FILES_NEEDING_T001_DEDUP`
(2026-08-21) rather than fixed upstream: keep only each row's `T001` copy,
then strip the `, 'T001'` index. Remove this workaround once a `pybalmorel`
patch exports `WTRRSVAR_S` correctly.

## Consequences

- `clean_weather_year_inputs.py` now silently drops any `.inc` file not
  listed in `PASSTHROUGH_FILES`/`RENAME_FILES`/`CONCAT_FILES` - a future
  WEATHERYEAR output file (new addon, new demand split, ...) needs an
  explicit decision added here, or it just won't reach `weatheryeardata/`
  at all. No error, no warning beyond the per-variant file count printed.
- The `SEASONALCOP_COP_VAR_T.inc` wrapper's `$include` paths assume it
  lives in a WY folder's own `data/`, one level below `scripts/Balmorel/`
  (`../../base/data/...`) - moving where WY folders live (see
  [0014](0014-weather-year-pipeline-architecture.md)) would need this
  wrapper's paths updated too.
- If `base/data/SEASONALCOP_COP_VAR_T_GROUND-WTR.inc`'s own column set
  ever changes (e.g. a new resource-grade split), the wrapper's ordering
  assumption (ground-wtr's reassignment running before, not after, the
  air-source assignments) needs re-checking against whatever `COP_VAR_T1`
  domain it declares.
