# Decompose flexibility need per country before spatially summing, and keep the old aggregate figure as a labelled bound rather than replacing it

**Status**: accepted

## Context

`estimate_flexibility_needs.py`'s system- and category-level tables
(`build_system_table`, `build_category_table`, and their flex-option
counterparts) summed residual load - or a flex option's own hourly net
dispatch - **across every country first**, then ran Geis et al. (2026)'s
nonlinear Daily/Weekly/Annual decomposition (half the summed absolute
deviation, see [0006](0006-residual-load-definition-for-flexibility-needs.md),
[0017](0017-correlation-based-flexibility-provision.md)) on that one summed
series. Because the metric is built from `|deviation|`, and an aggregate
series' deviation at any hour is exactly the *signed* sum of each country's
own deviation at that hour, the triangle inequality guarantees:

```
need(sum of countries' residual load) <= sum of need(each country's own residual load)
```

always, for every timescale. Summing before decomposing therefore
implicitly assumes unconstrained, "copper-plate" redistribution between
countries within the group - crediting whatever spatial smoothing that
assumption buys for free to the aggregation step itself, rather than to any
tracked flex option. Most consequentially: "Electricity transmission"/
"Hydrogen transmission"'s own measured provision
([0019](0019-signed-net-transmission-for-flexibility-provision.md)) was
only ever asked to cover whatever gap remained *after* this free implicit
netting, understating what it actually contributes.

The opposite extreme - decomposing each country's own residual load first,
then summing the resulting needs - assumes zero cross-border redistribution
(fully islanded countries), an upper bound. Neither bound is "the" true
flexibility need; the real figure, given the model's actual transmission
topology and capacity, lies somewhere between them. `build_country_table`
already computed the disaggregated (per-country) residual-load figure, kept
as table rows only (no plot, to avoid one PNG per country) - but no
per-country equivalent existed for flex-option provision, so the same
copper-plate blind spot applied there too, with no way to derive a
disaggregated by-option view at all.

## Decision

- **Nothing is deleted.** The aggregate (copper-plate) tables/plots are
  relabelled, not replaced - they remain a legitimate, if idealised,
  reference bound, not a wrong number superseded by a right one. `group_type`
  values gain an `_aggregate` suffix: `system`→`system_aggregate`,
  `category`→`category_aggregate`, `flex_option_system`→
  `flex_option_system_aggregate`, `flex_option_category`→
  `flex_option_category_aggregate`.
- **New `flex_option_country` group_type**: each flex option's own hourly
  net dispatch decomposed per country (that country's own FlexSign, its own
  "Other" residual for additivity) - the disaggregated counterpart to
  `flex_option_system_aggregate`/`flex_option_category_aggregate`, mirroring
  `build_country_table`'s existing residual-load pattern. Table rows only,
  no dedicated per-country-per-option plot by default (same "avoid one PNG
  per country" reasoning, now also × flex option) - `plot_flexibility_needs.py`
  can plot a single named country's own breakdown on request
  (`--country`), and always derives the disaggregated system/category-by-option
  plots by summing these rows.
- **`flexibility_needs.csv` gains a `category` column** (that row's
  Combined-category membership, from the `category_map` already computed in
  `estimate_flexibility_needs.py`), populated on `country`/
  `flex_option_country` rows. This lets `plot_flexibility_needs.py` roll
  country-level rows up into category totals itself, preserving its
  deliberate zero-GDX/pybalmorel dependency
  ([0012](0012-split-flexibility-needs-compute-from-plotting.md)) rather
  than recomputing category membership (which requires a reference
  scenario's own GDX results, [0004](0004-fixed-category-membership-for-cost-aggregation.md))
  at plot time.
- **`plot_flexibility_needs.py` derives "disaggregated" plots at plot time**,
  never written back to the CSV as their own `group_type`: system-wide by
  summing `country`/`flex_option_country` rows outright, category-level by
  grouping those same rows on the new `category` column first. Every
  system/category view now has two PNGs, `..._aggregate_<commodity>.png`
  and `..._disaggregated_<commodity>.png`.
- Additivity is preserved throughout: each country's own tracked options
  plus its own "Other" sum to that country's own need (Geis Appendix A.1,
  [0017](0017-correlation-based-flexibility-provision.md), unchanged - just
  now also computed per country). Since summation is linear, the
  disaggregated system/category-by-option totals (summed flex-option
  provision across countries) sum exactly to the disaggregated
  system/category residual-load totals (summed need across countries) -
  the "Total flexibility need" dashed line on a disaggregated by-option
  plot matches its disaggregated residual-load counterpart, the same way
  the aggregate plots already matched each other.

## Consequences

- Every commodity now produces roughly double the PNGs in
  `flex_needs_plots/` (`_aggregate` and `_disaggregated` variants of each
  view, plus any `--country`-requested ones) - report figures/captions
  referencing these need to say which bound they show, since "aggregate vs.
  disaggregated" is a real methodological choice (copper-plate vs.
  islanded), not "wrong vs. fixed."
- What the *country-level* "Other" bucket actually represents (residual
  load's own deviation minus every tracked option's, including
  transmission's real net cross-border position) is not interpreted by this
  ADR - an explicit open follow-up, not resolved here.
- `estimate_flexibility_needs.py` now computes a third per-group FlexSign
  (`country_signs`, alongside the existing `system_sign`/`category_signs`)
  and a third "Other" residual per scenario/commodity - a real increase in
  compute cost (one more `flexibility_provision` call per flex option per
  country, on top of the existing system/category calls), though bounded by
  the same already-loaded hourly symbols (no new GDX reads).
- `flex_option_metrics.py` is untouched - this ADR's scope, like
  [0017](0017-correlation-based-flexibility-provision.md)/
  [0019](0019-signed-net-transmission-for-flexibility-provision.md) before
  it, is `estimate_flexibility_needs.py`/`plot_flexibility_needs.py` only.
