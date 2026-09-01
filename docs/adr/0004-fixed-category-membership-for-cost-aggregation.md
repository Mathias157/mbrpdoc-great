# Fix category membership from a reference scenario when aggregating cost across scenarios

**Status**: accepted

## Context

`categorize_countries.py` labels each country's Combined category (Demand ×
VRE) relative to the mean across countries *within that same scenario name*
— a mean-relative, not absolute, threshold. The flexibility-option scenarios
(`EVN`, `VGN`, `HPN`, `TPN`, `HSN`, `SSN`, `EIN`, `DCN`, `H2N`, `ALLN`, ...)
change dispatch (and slightly demand) relative to `base`, so a country's
wind/solar ratio and total demand can shift enough to change its label
between scenarios.

We're adding a script that aggregates system cost per Combined category
across these scenarios, to see which flexibility options matter most for
which system type (e.g. "did `HPN` raise costs a lot for High Demand / High
Wind countries?"). Comparing "the same" category across scenarios requires
a consistent set of countries per category — otherwise a cost change could
reflect countries silently swapping categories rather than the flexibility
option's actual effect.

## Decision

Category membership is computed once from a single **Reference scenario**
(default `base_R2050`, overridable via `--reference-scenario`), then reused
as a fixed Country → Combined category mapping when aggregating cost for
every other scenario — rather than recomputing the label per scenario as
`categorize_countries.py` itself does.

## Consequences

- The cost-aggregation script's notion of "category" is intentionally not
  identical to `categorize_countries.py`'s own per-scenario Combined
  category — it's a snapshot pinned to the Reference scenario. A reader
  diffing the two scripts' outputs for the same scenario should expect
  divergence for any country near a threshold.
- If the reference scenario's own results change (e.g. a re-run of
  `base_R2050`), the entire cost-aggregation output needs regenerating even
  though no other scenario's underlying data changed.
