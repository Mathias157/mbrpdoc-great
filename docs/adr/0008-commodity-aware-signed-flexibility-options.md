# Make flexibility options commodity-aware and signed

**Status**: accepted

## Context

`flex_option_metrics.py`'s `FLEX_OPTIONS` (see [CONTEXT.md](../../CONTEXT.md)'s
"Flexibility option" entry) originally reported one unsigned magnitude per
option, mixing commodities wherever an option touches more than one: heat
pumps and electrolysers read `PRO_YCRAGF`/`G_CAP_YCRAF` with no `Commodity`
filter, so electrolysers silently summed hydrogen output together with its
waste-heat byproduct, on both the capacity and use axes. Heat pumps didn't
actually mix commodities (only `Commodity=HEAT` rows exist for
`ELECT-TO-HEAT`), but measured heat *output*, not the electricity *input*
that actually determines how much electricity-system flexibility a heat pump
provides — heat output overstates that by roughly the COP factor.
`estimate_flexibility_needs.py` (ADR 0007) imports the same `FLEX_OPTIONS`
for its own per-option decomposition, so both scripts inherited these
problems.

## Decision

- `FLEX_OPTIONS` becomes commodity-aware: options are evaluated and plotted
  separately per commodity (electricity / heat / hydrogen), not combined
  into one cross-commodity ranking. The same option can appear on more than
  one commodity's plot.
- Within a commodity's plot, an option's flex value is signed: positive when
  it injects into that commodity's balance, negative when it withdraws —
  see CONTEXT.md's "Commodity-signed flex value".
- Heat pumps and electrolysers: negative on the electricity plot, sourced
  from `F_CONS_YCRA(ST)` (`Fuel=ELECTRIC`, Technology-filtered — the actual
  electricity consumed); positive on each of their native output plots
  (`PRO_YCRAGF(ST)`, `Commodity`-filtered — heat pumps → heat only;
  electrolysers → both hydrogen and heat, each on its own commodity's
  plot).
- Storage (electricity/heat/hydrogen, uniformly): negative = charging, read
  from that commodity's own non-dispatchable-demand symbol's
  `ENDO_INTRASTO`/`ENDO_INTERSTO` category (already present in
  `EL_DEMAND_YCRST`, `H_DEMAND_YCRAST`, and `H2_DEMAND_YCRST` alike);
  positive = discharging, from `PRO_YCRAGF(ST)` as before.
- V2G: one already-net series, `EL_DEMAND_YCRST` Category=`ENDO_EV`
  (net G2V-minus-V2G), used directly instead of the previously-used
  `V2G_FLEX_YCR` (an unconfirmed "raw domain-fallback symbol"). Electricity
  plot only.
- Demand response is left unsigned and unchanged (`DR_FLEX_Y`) — no
  equivalent net-signed source exists for it.
- Capacity is never shown on a negative/demand-side row, even for storage
  (whose charge and discharge share one physical `G_CAP_YCRAF` rating) — a
  negative-signed number next to a capacity value would read as "negative
  capacity," which is more confusing than simply omitting it.

## Consequences

- `flex_option_metrics.py`'s and `estimate_flexibility_needs.py`'s CSV
  outputs both change shape: rows gain a `Commodity` dimension, and
  `flex_value`/`flex_need_twh` can now be negative.
- Cross-commodity weighting (e.g. "electricity flexibility matters more than
  heat because of its stricter balancing requirement") is explicitly out of
  scope here — there's no longer a single merged number to weight. That
  question is deferred to a not-yet-built priority/ranking pass, if one is
  ever built.
- A reader comparing electricity-plot and heat-plot numbers for the same
  option (e.g. a heat pump) is comparing genuinely different physical
  quantities (GWh electricity consumed vs. GWh heat produced) — not a bug.
  Converting between them would need a COP assumption (which COP? seasonal
  average? design point?), a real modelling choice this redesign
  deliberately avoids making silently.
