# Interannual flexibility need and provision: weather-year ensemble variability, not within-year timing

**Status**: accepted

## Context

Weather-year runs (see [CONTEXT.md](../../CONTEXT.md)'s **Weather year run**) dispatch the *same fixed* investment decision against N different historical weather realizations - testing sensitivity to weather uncertainty, not the investment decision itself (that's **Target year**'s job).

Daily/Weekly/Annual flexibility need/provision ([0007](0007-flexibility-option-timescale-decomposition.md), [0017](0017-correlation-based-flexibility-provision.md)) measure timing mismatches *within* one continuous dispatch that a flex option could plausibly resolve by shifting energy in time. A weather-year run is a separate, independent dispatch from every other weather year sharing its source scenario - nothing carries energy between them.

## Decision

- Add an "Interannual" need: half the summed absolute deviation between each weather year's own annual-mean residual load and the mean of that quantity across every weather year sharing the same source scenario (weighted by hours-per-year, matching the existing hourly->daily->weekly->annual convention - see [0023](0023-interannual-flexibility-needs-batched-compute.md) for how it's actually computed). Unlike the other three levels, this isn't a within-dispatch timing mismatch any option resolves by shifting energy - it measures how exposed a *fixed* investment decision is to weather-driven uncertainty.
- Also add Interannual **provision**, not need alone - reframed around uncertainty exposure rather than energy transfer: a flex option's own annual-mean deviation, weighted by the sign of the group's own Interannual deviation (`sign(annual_mean(year) - N_year_mean)`, the same "group's own sign, not the option's own" rule as [0017](0017-correlation-based-flexibility-provision.md)). Positive when an option's operation happens to be higher exactly in the years residual load needed it more (helping absorb weather risk), negative when the opposite - not a claim that the option physically carries energy between years. Same exact-additivity-with-Other construction as ordinary Flexibility provision.
- Terms recorded in [CONTEXT.md](../../CONTEXT.md): **Interannual flexibility need**, **Interannual flexibility provision**.

## Considered options

- **Need only, no provision** - the initial instinct, on the reasoning that no flex option literally shifts energy across separate weather-year dispatch runs, so "provision" would have no mechanism behind it (would collapse entirely into "Other"). Rejected on reflection: provision at every other level is already a correlation/alignment measure, not proof of physical transfer, so the same construction is meaningful one level up - it answers "does this option's operation happen to help or hurt under weather uncertainty," a real question for a fixed investment decision, not a degenerate one.

## Consequences

`plot_flexibility_needs.py` needs a way to summarize an ensemble of weather-year scenarios (min/mean/median/max across years, default mean) rather than plotting one bar per weather year, for both need and provision views, auto-detected whenever multiple scenario names share a source scenario + target year. Kept as a plain single-statistic bar for v1 (no per-segment spread/whiskers) since per-option error bars get dense fast on an already ~18-hue stacked chart. A future distribution view (spread of a flex option's own provision across weather years) is deferred - likely small multiples (one flex option per x-position, not stacked, timescale fixed per figure) rather than extending the stacked chart.
