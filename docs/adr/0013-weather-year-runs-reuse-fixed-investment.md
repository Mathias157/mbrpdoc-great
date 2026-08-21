# Weather year runs dispatch a fixed investment decision, never re-invest

**Status**: accepted

## Context

We want to know how sensitive a scenario's operation is to inter-annual
weather variability (VRE production, demand, hydro inflow, heat-pump COP),
not just the single realized weather year each investment run currently
happens to be solved against. `pybalmorel`'s `WEATHERYEAR` module (used via
`weatheryear_inputs/` in the sibling `pybalmorel` repo) can produce
Balmorel-ready `.inc` files for any of 39 historical years (1982-2020).

The obvious-sounding "just rerun the whole three-step pipeline per weather
year" would mean 39 fresh **Investment run**s per scenario studied - each
already a multi-hour-to-multi-day MIP solve (see
[0001](0001-warm-start-fullyear-timeout.md)). That answers a different
question (how does the optimal *capacity mix* change across weather
realizations) than the one being asked here (how does a *given* capacity
mix's *operation* vary across weather realizations) - and at ~39x the
compute cost of every scenario already run.

## Decision

A **Weather year run** ([CONTEXT.md](../../CONTEXT.md)) is always
**Fullyear run** → **Rolling run** only, dispatched against one existing
**Source scenario**'s already-completed **Investment run** (read from that
scenario's `simex_INV/` at run time - see
[0014](0014-weather-year-pipeline-architecture.md)). No weather year run
ever triggers a fresh investment optimisation. The capacity mix is held
fixed; only the weather realization it's dispatched against varies.

## Consequences

- Weather year runs can only ever answer "how does this specific,
  already-decided capacity mix perform under different weather" - not "what
  capacity mix would be optimal for weather year X". Studying the latter
  would mean a genuinely different (and far more expensive) pipeline, not
  an extension of this one.
- Every weather year run for a given source scenario shares one investment
  decision, so cross-weather-year comparisons (e.g. the deferred
  flexibility-need distribution plot) are directly comparable to each other
  - they differ in exactly one thing (the weather), not in both weather and
    capacity.
