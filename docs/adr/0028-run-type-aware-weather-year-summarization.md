# Daily/Weekly/Annual weather-year summarization is run_type-aware, like Interannual already was

**Status**: accepted

## Context

`plot_flexibility_needs.py`'s `_summarize_weather_years` collapses every `<source>_WY<year>_<F|R><year>` scenario to its source name (e.g. `base_WY1986_F2050` -> `base`) before pooling into one Daily/Weekly/Annual bar per source scenario ([0023](0023-interannual-flexibility-needs-batched-compute.md)). `flexibility_needs.csv` (`NEEDS_COLUMNS`, `estimate_flexibility_needs.py`) carries no `run_type` column of its own - only the raw `Scenario` string - so nothing stopped a source scenario's Fullyear (F) weather years and Rolling (R) weather years from being pooled into the *same* `base` bar whenever both existed for one source. Confirmed directly against `build_postprocess_oldbaseWY/flexibility_needs.csv`: `base` has weather years under both `_F2050` and `_R2050`, and prior to this change they silently averaged together into one `base` bar at the Daily/Weekly/Annual levels.

The Interannual panel already avoids this: `_pool_interannual` (added alongside 0023, formalized in [0026](0026-interannual-pooling-moved-to-plot-time.md)) reads `interannual_annual_means.csv`, which *does* carry `run_type`, and falls back to `f"{source_scenario}_WY_{run_type}"` whenever a source has more than one run_type with its own pool. This left the three timescales computed by `_summarize_weather_years` inconsistent with the fourth (Interannual) for the same source scenario: three panels showing one blended `base` bar, the fourth showing `base_WY_F` and `base_WY_R` side by side.

## Decision

- `_summarize_weather_years` now derives each row's run_type from the raw `Scenario` string itself (`_run_type`, a capturing counterpart of the existing `SCENARIO_SUFFIX_RE`), and applies the same `f"{source}_WY_{run_type}"` fallback as `_pool_interannual` whenever a source has more than one run_type among its own weather-year rows. A source with only one run_type's weather years still collapses to the plain source name, unchanged.
- This makes the Daily/Weekly/Annual and Interannual panels label-consistent for the same source scenario - `base_WY_F`/`base_WY_R` (or plain `base`) means the same split at every timescale, rather than only at Interannual.

## Considered options

- **Leave Daily/Weekly/Annual blending F and R together, document it as a known limitation.** Rejected - the user confirmed explicitly they don't want run_type mixing at these timescales; a copper-plate/disaggregated-style "this bounds something, not the true value" framing doesn't apply here, since F and R runs are different modeling choices (fullyear vs. rolling-horizon dispatch), not two ends of one bracket.
- **Add a `run_type` column to `flexibility_needs.csv` itself.** Rejected as unnecessary - `_run_type` can derive it from the existing `Scenario` string with the same regex approach already used for `_source_scenario`/`_is_weather_year`, without touching `estimate_flexibility_needs.py`'s output format or its expensive GDX read.

## Consequences

None outside this script - `interannual_annual_means.csv` and its own `_pool_interannual` are unchanged; this only changes what `_summarize_weather_years` produces from `flexibility_needs.csv`.
