# Replace fixed per-option sign with Geis et al.'s correlation-based flexibility provision, and redefine residual load for exact additivity

**Status**: accepted (supersedes [0006](0006-residual-load-definition-for-flexibility-needs.md), [0011](0011-signed-flex-need-display-for-demand-side-options.md); resolves the deferred dumb-charging item in [0016](0016-split-v2g-into-ev-charging-and-v2g.md))

## Context

[0011](0011-signed-flex-need-display-for-demand-side-options.md)/[0016](0016-split-v2g-into-ev-charging-and-v2g.md)
sign a flex option's `system_by_option_*`/`category_by_option_*` bar by a
**fixed** per-option property (`"kind"`/`"direction"` in `FLEX_OPTIONS`) —
negative for `"consumption"`-kind views, positive otherwise. This has no
relationship to whether that option's dispatch, in any given period, actually
reduced or increased the system's variability — it's a chart-stacking
convenience, not a measurement. Checked against the actual figures in Geis
et al. (2026, "Managing the mismatch", *Advances in Applied Energy* 23:100284
— the paper this pipeline already cites for the Daily/Weekly/Annual
decomposition itself, see [0006](0006-residual-load-definition-for-flexibility-needs.md)),
their own flexibility-provision charts show the opposite: a technology's sign
is *data-driven*, derived from whether its own dispatch aligns with or
opposes residual load's swings in each period. Interconnectors and battery
discharge, both nominally "supply-side," go negative in some of their
scenario-years; V2G doesn't get a fixed sign at all.

Geis's Section 2.1.2 (+ Appendix A.1) defines this precisely, and proves it
**exactly additive** (technology contributions sum to total need) — something
their Appendix A.2 proves a naive "remove the technology and recompute" (or
any other tech-outside-in) attribution is *not*. Reproducing that additivity
here means every hour's residual load must equal the sum of every tracked
flex option's own signed dispatch at that hour (their eq. 6, "system
balance") — which exposed that this codebase's residual-load definition
([0006](0006-residual-load-definition-for-flexibility-needs.md)) already had
real gaps: `EL_DEMAND_YCRST`'s actual `Category` values (checked directly
against a cached `build_postprocess/.gdx_cache/EL_DEMAND_YCRST.pkl`, not
guessed) are `EXOGENOUS`, `ENDOGENOUS_ELECT2HEAT`, `ENDO_EV`, `DIST_LOSSES`,
`TRANS_LOSSES`, `ENDO_H2`, `ENDO_INTRASTO`, `ENDO_CCS`, `ENDO_BIOMETHANE` —
`DIST_LOSSES`/`TRANS_LOSSES`/`ENDO_CCS`/`ENDO_BIOMETHANE` are real, nonzero,
and were previously excluded from *both* residual load and every flex
option, uncounted anywhere ([0009](0009-heat-hydrogen-residual-load.md)
already flagged `ENDO_H2`/`ENDO_CCS`/`TRANS_LOSSES` as missing from 0006's
documented list — this ADR is the fix that was deferred there). Balmorel's
`VARIABLE_CATEGORY` set also declares `ENDO_HEATPUMP`/`ENDO_ELBOILER`/
`ENDO_FUELCELL` (a finer heat-pump/resistive-heater split, and a fuel-cell
demand tag) but none of these three carry any data in this dataset's actual
results — declared for generality, not populated here.

`FLEX_OPTIONS`' technology coverage was also checked against Balmorel's full
`GDTYPE` roster: essentially complete for electricity except `FUELCELL`
(`GNR_FC_H2_SOFCC*`, `GDTECHGROUP="FUELCELL"`, in
`scripts/Balmorel/base/data/HYDROGEN_GDATA.inc`) — investment-only, no fixed
2025 capacity, but genuinely untracked. Separately, `GDTYPE=GETOH`
(`ELECT-TO-HEAT`, today's "Heat pumps" option) bundles real heat pumps
(`HP_ELEC_*`, genuine COP values), resistive/electric boilers (`BO_ELEC_*`),
*and* industrial electric process heat (`GNR_IND-BO_*`/`GNR_IND-DF_ELEC_*`)
under one technology string — confirmed via `GDATA.inc`'s generator-ID
naming, not assumed.

## Decision

- **Sign mechanism**: for each tracked flex option, at each `h|ℓ` timescale
  pair, compute its own deviation curve (`P̄ᵢʰ(t) − P̄ᵢˡ(t)`, period-average at
  the finer resolution minus the coarser one — reusing `flex_option_hourly_net`'s
  existing `P_i(t)` series) and multiply it by the **system's own**
  `FlexSign` (the sign of *residual load's* deviation at that same `t`, `h|ℓ`
  pair — not the option's own sign), then sum and halve, exactly as Geis's
  eq. 3–4. This replaces `_is_demand_side`'s fixed `±1` entirely.
- `FlexSign` is computed **per `group_type`** (system/category/country), each
  from that group's own residual load — not one system-wide value broadcast
  to every group — so every group's stacked bars sum to that group's own
  "Total Flexibility Needs" line.
- **Residual load's non-dispatchable-demand side is no longer user-configurable.**
  [0006](0006-residual-load-definition-for-flexibility-needs.md)'s
  `--demand-categories` flag is removed: additivity requires every
  `EL_DEMAND_YCRST`/`H_DEMAND_YCRAST`/`H2_DEMAND_YCRST` category to have
  exactly one fixed home — residual load, or exactly one tracked flex option
  — never both, never neither, never a runtime choice. Residual load becomes
  `EXOGENOUS` + `DIST_LOSSES` + `TRANS_LOSSES` + `ENDO_CCS` +
  `ENDO_BIOMETHANE` (categories with no flex-option home — losses aren't
  dispatched, CCS parasitic load isn't a tracked option) + the *dumb/inflexible*
  share of `ENDO_EV` (from `EV_BEV_dumb.inc`/`EV_PHEV_dumb.inc` — extraction
  mechanics decided at implementation time). `ENDOGENOUS_ELECT2HEAT`,
  `ENDO_H2`, and `ENDO_EV`'s flexible/smart share are always excluded, since
  they're always claimed by a flex option below.
- **Electrolysers** and **EV charging/V2G**'s consumption-side `P_i(t)` now
  source directly from `EL_DEMAND_YCRST` Category=`ENDO_H2` /
  `ENDO_EV`-net-of-dumb-share, guaranteeing by construction that they exactly
  offset what residual load excludes — the same pattern
  [0016](0016-split-v2g-into-ev-charging-and-v2g.md) already established for
  `ENDO_EV`.
- **"Heat pumps" is renamed "PtH" and split three ways by
  `Area`**, not by hardware type — `Area` contains `'IND'` → "Industrial
  PtH"; contains `'IDVU'` → "Individual PtH";
  otherwise → "District PtH". Its consumption-side source
  stays `F_CONS_YCRAST` (unlike Electrolysers/EV, since `EL_DEMAND_YCRST` has
  no `Area` column to split on — confirmed via its actual columns:
  `Scenario, Year, Country, Region, Season, Time, Category, Unit, Value`), a
  choice validated empirically: summed `F_CONS_YCRAST` across all
  PtH technologies equals `EL_DEMAND_YCRST`'s
  `ENDOGENOUS_ELECT2HEAT` category exactly, so no divergence risk from using
  the Area-bearing symbol instead of the category-bearing one.
- **New flex option "Fuel cells"** (`FUELCELL`, Commodity=ELECTRICITY,
  Fuel=HYDROGEN) — electricity production side reads `PRO_YCRAGF(ST)` same as
  other production-kind options; hydrogen consumption-side sourcing (`F_CONS`
  vs. a possible `ENDO_FUELCELL` `H2_DEMAND_YCRST` category — unconfirmed,
  unlike `ENDO_H2`/`ENDO_EV` above) is left for implementation-time
  verification against live data.
- **Explicit "Other" bucket**, computed the same way as every tracked
  technology (residual load's own deviation curve minus the sum of all
  tracked options' deviation curves, still `FlexSign`-weighted) rather than
  silently omitted — a safety net for exact additivity regardless of whether
  `FLEX_OPTIONS` is a perfectly exhaustive partition (catches the `FUELCELL`
  hydrogen-side gap and anything else not yet individually enumerated).
- Applies to **all three commodities** electricity/heat/hydrogen — heat and
  hydrogen's own category composition (their own losses/CCS-equivalents in
  `H_DEMAND_YCRAST`/`H2_DEMAND_YCRST`) gets the same empirical
  cache/GDX check before implementation that electricity already got here.
- **Scope**: `estimate_flexibility_needs.py`'s Daily/Weekly/Annual bar charts
  only. `flex_option_metrics.py` keeps [0008](0008-commodity-aware-signed-flexibility-options.md)'s
  own sign convention unchanged (a different question — "does this option
  inject or withdraw" vs. "does this option reduce or increase flexibility
  need") — but since `FLEX_OPTIONS` is shared infrastructure, it inherits the
  PtH rename/split and the new Fuel cells entry too.

## Consequences

- `flexibility_needs.csv`'s `flex_need_twh` semantics change again (already
  changed once under [0011](0011-signed-flex-need-display-for-demand-side-options.md)):
  a flex option's sign is now period-dependent in origin (summed into one
  number per group/commodity/timescale), not a fixed property of its
  `"kind"`.
- `--demand-categories` is a breaking CLI change — any saved command line or
  script invoking it needs updating.
- `flex_option_metrics.py`'s plots gain the same PtH
  rename/split and Fuel cells entry as a side effect of sharing
  `FLEX_OPTIONS`, even though its own sign mechanism is untouched.
- Heat/hydrogen's exact non-dispatchable-demand category list (their
  `DIST_LOSSES`/`ENDO_CCS` equivalents, if any) is not yet verified — this
  ADR fixes electricity's list from real data but heat/hydrogen's still needs
  the same check once `H_DEMAND_YCRAST`/`H2_DEMAND_YCRST` are next read.
- If Balmorel's data ever populates `ENDO_HEATPUMP`/`ENDO_ELBOILER` (a finer
  heat-pump/resistive-heater split than `ENDOGENOUS_ELECT2HEAT` provides
  today), the PtH split could move from `Area`-based to
  hardware-based, or add a fourth axis — not attempted here since neither
  category carries data in this dataset today.
