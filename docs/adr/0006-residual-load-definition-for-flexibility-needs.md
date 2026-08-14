# Define residual load's demand/supply components for flexibility-need estimation

**Status**: accepted

## Context

We're adding `estimate_flexibility_needs.py`, which implements Geis et al.
(2026)'s Daily/Weekly/Annual flexibility-need metric (see
[CONTEXT.md](../../CONTEXT.md)'s Flexibility need entry) on top of hourly
**residual load** = non-dispatchable demand minus non-dispatchable supply.
Neither side of that subtraction is a single existing Balmorel symbol, so
both needed a concrete definition against this model's own data:

- `EL_DEMAND_YCRST` carries a `Category` dimension (`EXOGENOUS`,
  `ENDOGENOUS_ELECT2HEAT`, `ENDO_EV`, `ENDO_INTRASTO`, `ENDO_INTERSTO`,
  `DIST_LOSSES`) rather than being a single inelastic figure.
  `ENDOGENOUS_ELECT2HEAT` (heat pumps and resistive heaters share one
  technology group, `IGETOH` - this model has no separate resistive-heater
  label) and `ENDO_EV` (EV charging, already net of V2G discharge) are
  exactly the kind of demand the paper calls inelastic ("the inflexible
  component driven by heat demand outweighs the available flexibility from
  building thermal inertia"), but whether that holds in *this* model's
  parameterisation is a modelling judgement call, not a settled fact -
  unlike `EXOGENOUS` (pure household/industry/agriculture/datacentre load),
  which is unambiguously inelastic.
- Non-dispatchable supply has a precedent already in this codebase:
  `VRE_CERT_AS.inc` groups wind, solar, and run-of-river hydro (`GHYRR`) as
  "full-certainty" resources for ancillary-service purposes.

## Decision

- **Non-dispatchable demand**: `EL_DEMAND_YCRST` summed over a
  *configurable* set of categories, via `--demand-categories`
  (default: `EXOGENOUS` only). `ENDOGENOUS_ELECT2HEAT` and `ENDO_EV` can be
  added in, but default off. `ENDO_INTRASTO`/`ENDO_INTERSTO` (storage
  charging) and `DIST_LOSSES` are never selectable - storage charging is
  itself a flexibility option (see CONTEXT.md), and losses are a technical
  quantity, not demand needing balancing.
- **Non-dispatchable supply**: wind + solar + run-of-river hydro production,
  fixed (not configurable) - reusing this model's own `VRE_CERT_AS`
  grouping rather than introducing a second, script-local definition.

## Consequences

- `estimate_flexibility_needs.py`'s notion of "demand" is not automatically
  the same as `categorize_countries.py`'s - that script sums `EL_DEMAND_YCR`
  with no `Category` filter (all categories, including storage and losses)
  for its own High/Low labelling purpose. A reader diffing demand totals
  between the two scripts should expect divergence and should not treat it
  as a bug.
- Changing `--demand-categories` from run to run changes every downstream
  flexibility-need number, including for scenarios already computed with a
  different setting - outputs from different `--demand-categories` values
  are not comparable and should be labelled accordingly (the CSV should
  record which categories were used).
- If this model ever adds a distinct resistive-heater technology (currently
  merged into `IGETOH`/`ELECT-TO-HEAT` with heat pumps), `ENDOGENOUS_ELECT2HEAT`
  would stop being separable into its two components without a model-side
  change first.
