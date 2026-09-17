# Interannual need/provision divided by weather-year count to get a genuine TWh/a rate

**Status**: accepted

## Context

The Interannual formula ([0023](0023-interannual-flexibility-needs-batched-compute.md)/[0024](0024-interannual-flexibility-need-provision-concept.md)) was built by direct analogy to the existing Daily/Weekly/Annual levels: `0.5 * HOURS_PER_WEATHER_YEAR * sum_y(|deviation_y|) * mwh_to_twh`. Running this against real data (post the run_type-mixing fix in 0023) still produced implausible numbers - confirmed directly, on the order of total annual electricity demand rather than a figure comparable to the Annual level's own ~20-27 TWh/a.

The root cause: Daily/Weekly/Annual's own population is exactly one year's worth of hours (8736), so summing over it already yields a per-year (TWh/a) rate with no further normalization needed - that's *why* those formulas never divide by anything beyond the hourly→TWh unit conversion. Interannual's population, by the same "each coarser value held constant across every finer unit it covers" construction, spans the *whole N-year ensemble* (each weather year's own deviation held constant across all 8736 of its own hours) - so the un-normalized sum is a **total over N years**, not an annualized rate. Confirmed with real numbers: a 4-weather-year test case that returned 125.63 "TWh/a" dropped to a plausible 31.4 TWh/a once divided by 4.

## Decision

- Every Interannual need and provision figure is now divided by the pool's own weather-year count (`n_years`) after the existing `HOURS_PER_WEATHER_YEAR`-weighted summation - in both `plot_flexibility_needs.py`'s `_pool_interannual` and `illustrate_interannual_flexibility_needs.py`'s `_interannual_need`/`_interannual_provision`/`_contribution_series` (which must match the pooled figure exactly, per its own no-drift guarantee - see 0025).
- **The divisor is always the residual load's own weather-year count for that group**, looked up via the same `sign_key` already used for FlexSign, never a flex option's own (possibly smaller) count - a flex option can be missing some weather years entirely (e.g. zero dispatch that year), and dividing by its own count instead of the group's shared one would break additivity (tracked options + Other == need) in the normalized TWh/a domain even though it still held in the un-normalized, pre-division domain.
- `_contribution_series` (the per-weather-year bars in the illustration script) gained the same `HOURS_PER_WEATHER_YEAR`/`n_years` scaling it was previously missing entirely - it now sums (after the usual MWh→TWh conversion) to exactly `_interannual_provision`'s own figure, matching how the original hourly script's own per-period contribution bars already sum to `flexibility_provision()`'s figure.

## Consequences

`CONTEXT.md`'s **Interannual flexibility need**/**provision** entries updated to describe the normalization directly, since it's part of the concept's own correct definition, not an implementation detail.
