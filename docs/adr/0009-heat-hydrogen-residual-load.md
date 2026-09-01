# Extend residual-load definition to heat and hydrogen

**Status**: accepted

## Context

ADR 0006 defined residual load (see [CONTEXT.md](../../CONTEXT.md)) for
electricity only: non-dispatchable demand (`EL_DEMAND_YCRST`, `EXOGENOUS` by
default) minus non-dispatchable supply (wind/solar/run-of-river,
`VRE_CERT_AS`). Extending "flexibility need" plots to heat and hydrogen
needed the same two components defined for those commodities.

`H_DEMAND_YCRAST` and `H2_DEMAND_YCRST` both exist as `MainResults` symbols,
shaped like `EL_DEMAND_YCRST`, with `Category` dimensions including
`EXOGENOUS` and `ENDO_INTRASTO`/`ENDO_INTERSTO` — so the demand side
generalizes directly.

The supply side does not. Electricity's non-dispatchable supply is fixed and
uncontrollable (wind/solar/run-of-river — weather-driven, not an
optimisation decision). Checking what actually produces heat and hydrogen in
this model (`PRO_YCRAGF` by `Commodity`):

- Heat: `BOILERS`, `CHP-BACK-PRESSURE`, `CHP-EXTRACTION`, `ELECT-TO-HEAT`,
  `ELECTROLYZER` (byproduct), heat storage, and `SOLAR-HEATING`. Only
  `SOLAR-HEATING` (`Fuel=SUN`) is structurally analogous to wind/solar — and
  it's negligible in this dataset (14 TWh vs. 6461 TWh total heat
  production, ~0.2%).
- Hydrogen: `ELECTROLYZER`, `H2-STORAGE`, `STEAMREFORMING` (`Fuel=NATGAS`,
  dispatchable). Nothing here is non-dispatchable.

An earlier proposal was to net heat/hydrogen demand against "VRE-powered
heat pump/electrolyser availability." Rejected: heat pumps and electrolysers
are themselves flexibility options (controllable, optimised dispatch), not
fixed supply, so subtracting one from the need it's meant to help meet would
be circular — equivalent to defining electricity residual load as demand
minus battery discharge.

## Decision

- **Heat residual load** = non-dispatchable heat demand only
  (`H_DEMAND_YCRAST`, `EXOGENOUS`-only by default, mirroring ADR 0006's
  `--demand-categories` pattern) — no supply netting, since `SOLAR-HEATING`
  is negligible enough to not be worth tracking for this purpose.
- **Hydrogen residual load** = non-dispatchable hydrogen demand only
  (`H2_DEMAND_YCRST`, same default) — no supply netting, since nothing on
  the hydrogen side is non-dispatchable.
- Both always exclude `ENDO_INTRASTO`/`ENDO_INTERSTO` (that commodity's own
  storage charging — now a tracked flexibility option, see
  [0008](0008-commodity-aware-signed-flexibility-options.md)) and
  technical-loss categories, matching electricity's existing exclusions.

## Consequences

- Residual load is now asymmetric across commodities by design: electricity
  nets demand against real non-dispatchable supply, heat and hydrogen don't.
  A reader expecting parallel treatment across all three should not read
  this as an oversight.
- If `SOLAR-HEATING` capacity ever grows to a non-negligible share of a
  scenario's heat production, this decision should be revisited — the 0.2%
  figure is a property of the current dataset, not a structural guarantee.
- ADR 0006's own documented `EL_DEMAND_YCRST` category list is stale against
  current data (missing `ENDO_H2`, `ENDO_CCS`, `TRANS_LOSSES`) — noted here,
  to be fixed separately when that ADR is next touched.
