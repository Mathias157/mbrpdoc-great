# Sign flex_need_twh by demand/supply role for flex-option bar charts, and stack rather than group them

**Status**: superseded by [0017](0017-correlation-based-flexibility-provision.md)

## Context

`flexibility_needs()` (see [0006](0006-residual-load-definition-for-flexibility-needs.md),
[0007](0007-flexibility-option-timescale-decomposition.md)) is built from half
the summed *absolute* deviation from a coarser-timescale mean, so it is
sign-invariant by construction: flipping the sign of an entire hourly series
before decomposing it produces the exact same `flex_need_twh` numbers. That's
correct for what the function measures (variability), but it means
`system_by_option_*.png`/`category_by_option_*.png` (ADR 0007's per-option
decomposition) rendered every flex option's bar as positive, including heat
pumps and electrolysers - whose own hourly net series (`flex_option_hourly_net`,
kind `"consumption"`) is already correctly negative (it flips `F_CONS_YCRAST`'s
positive electricity-draw magnitude, the same way `flex_option_metrics.py`'s
`extract_flex_option_values` does for its own plots, see
[0008](0008-commodity-aware-signed-flexibility-options.md)) - the sign was
simply erased by `flexibility_needs()`'s `abs()` before it reached the plot.
The original design vision for these commodity plots (see CONTEXT.md's
"Commodity-signed flex value") was always demand-side options appearing
negative, supply-side positive - `system_by_option_*.png`/
`category_by_option_*.png` never actually delivered that.

Separately, both these bar charts and residual load's own `system_*.png`/
`category_*.png` used grouped (side-by-side) bars, which don't read well
once bars can be positive or negative - a proper demand-below/supply-above
picture needs stacking.

## Decision

- `main()` reattaches a demand/supply sign to `flex_need_twh` after
  `flexibility_needs()` runs, for `flex_option_system`/
  `flex_option_category` rows only (residual load's own `system`/`category`
  rows are untouched, always >=0) - `-1` for `"consumption"`-kind views
  (heat pump/electrolyser electricity draw), `+1` for everything else.
- `"production"`/`"peaker"` are always supply-side, so `+1` is correct.
  `"storage"`/`"transmission"`/`"net_category"` (the last since split into
  EV charging/V2G by [0016](0016-split-v2g-into-ev-charging-and-v2g.md),
  whose net-period sum turned out not to be near-zero after all) are
  genuinely bidirectional, not a fixed demand- or supply-side role - signing
  them by their
  net-period sum was considered and rejected: storage in particular nets
  slightly *negative* over a full period from round-trip losses (charge >
  discharge), which would misleadingly stack it as "demand-side" despite
  being the closest thing this dataset has to a textbook flexibility
  provider. They're left `+1` (stacked on the supply side) instead - not
  fully accurate either, but not actively misleading the way a
  losses-driven sign flip would be.
- All four bar charts (`system_*`, `category_*`, `system_by_option_*`,
  `category_by_option_*`) now stack rather than group: each `hue_col` value
  (spatial group, or flex option) is drawn as its own `ax.bar(...,
  bottom=running_total)` call, tracking a separate running total for
  positive and negative values so demand-side bars stack downward from
  zero and supply-side bars stack upward, with a zero line drawn for
  reference (`_stack_bars`).

## Consequences

- `flexibility_needs.csv`'s `flex_need_twh` column is no longer uniformly
  >=0: `flex_option_system`/`flex_option_category` rows for
  `"consumption"`-kind views (Heat pumps/ELECTRICITY, Electrolysers/
  ELECTRICITY) are now negative. Residual load's own rows are unaffected.
  Any downstream consumer of this CSV that assumed all-positive values
  needs to take `.abs()` if it wants the pre-existing magnitude semantics.
- Storage/transmission's bars still don't distinguish their charging vs
  discharging (or import vs export) sub-components the way
  `flex_option_metrics.py`'s two-row storage view does - this ADR only
  fixes the demand-vs-supply-side cases that were unambiguous by "kind".
  V2G was in this same bucket originally, but see
  [0016](0016-split-v2g-into-ev-charging-and-v2g.md), which gives it its
  own two-row split instead.
