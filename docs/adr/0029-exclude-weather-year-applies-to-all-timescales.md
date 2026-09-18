# `--exclude-weather-year` now applies to Daily/Weekly/Annual, not just Interannual

**Status**: accepted

## Context

`--exclude-weather-year` was added in [0026](0026-interannual-pooling-moved-to-plot-time.md) to drop a weather year found to be erroneous. Its implementation (`_apply_weather_year_exclusions`) only ever touched `interannual_annual_means.csv` before `_pool_interannual`, since that was the table `main()` had exclusions plumbed into at the time - `_summarize_weather_years` (the function that pools `flexibility_needs.csv`'s raw per-weather-year `Scenario` rows into the Daily/Weekly/Annual bars) never received the exclusion set at all.

The user excluded weather years 2008/2009 expecting them gone from the plot and found the Daily/Weekly/Annual bars unchanged - confirmed directly: `flexibility_needs.csv` has no `source_scenario`/`weather_year`/`run_type` columns of its own (only the raw `Scenario` string, e.g. `base_WY2008_R2050`), so nothing in `_summarize_weather_years` could have matched against an exclusion tuple even if it had received one. The Interannual panel alone honored the flag; the other three silently kept pooling excluded years in their mean/min/median/max.

## Decision

- New `_weather_year()` (paired with the existing `_run_type()`, see [0028](0028-run-type-aware-weather-year-summarization.md)) derives a raw `Scenario` string's weather year, the same way `_source_scenario`/`_is_weather_year` already derive source/run_type from it.
- New `_apply_weather_year_exclusions_to_needs()` applies the same `(source, year)`/`(source, year, run_type)` matching as the existing `_apply_weather_year_exclusions`, but against `tidy` (raw `flexibility_needs.csv` rows), deriving the match keys from `Scenario` instead of reading them from real columns.
- `main()` now parses `--exclude-weather-year` once and applies it twice: to `tidy` before `_summarize_weather_years` (Daily/Weekly/Annual), and to `annual_means` before `_pool_interannual` (Interannual) - same exclusion set, same CLI flag, both code paths.

## Consequences

None outside this script. A user who already used `--exclude-weather-year` expecting it to only affect the Interannual panel will now see it drop the excluded year from Daily/Weekly/Annual too - this is the fix, not a regression; there was never a reason to want partial exclusion across timescales.
