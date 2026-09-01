# Use summed regional peak production as peaker "capacity" in flexibility-option scatter plots

**Status**: accepted

## Context

The flexibility-option priority scatter plots (capacity/use per option vs.
system cost, emissions, and security of supply, per scenario/year, see
[CONTEXT.md](../../CONTEXT.md)'s Flexibility option entry) need a Y-axis
value for every option's "capacity." For most options that's just the
modelled `G_CAP_YCRAF` value. Peaker units are the exception: their modelled
nameplate capacity is set heuristically large per region purely to guarantee
LP feasibility, not to reflect a real investment or engineering constraint.
Plotting it directly would show the same arbitrary constant across every
scenario, telling us nothing about how peakers actually trade off against
cost, emissions, or LOLE.

## Decision

For peaker specifically, "capacity" in this analysis means **effective
peaker capacity**: the sum, across regions, of each region's own maximum
hourly peaker production observed in that scenario/year — not the modelled
nameplate `G_CAP_YCRAF` value. Every other flexibility option uses its real
modelled capacity or production directly.

## Consequences

- Peaker "capacity" here is not comparable to `G_CAP_YCRAF` or to other
  capacity-based analyses (e.g. `analyse.py`'s `cap` command). A reader
  cross-referencing this output against a raw capacity table will see a
  mismatch and should not treat it as a bug.
- Because it's derived from production (an hourly endogenous result), peaker's
  "capacity" and "use" axes are not independent the way they are for other
  options — both move together with the underlying production series, just
  aggregated differently (max vs. sum/total).
