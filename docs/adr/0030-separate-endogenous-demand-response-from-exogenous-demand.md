# Separate endogenous demand response from the exogenous electricity demand profile

**Status**: accepted

## Context

`OUTPUT_SUMMARY.inc:429-439` splices demand response into `EL_DEMAND_YCRST`'s
`EXOGENOUS` category: `raw - VDR_DOWN(shed) - VDR_DOWN(shift) + VDR_UP(shift)`.
The only DR symbol that reaches MainResults is `DR_FLEX_Y` (`:497`, `:1637`) -
annual TWh, gross downward regulation, no `S/T` dimension.

That shape is deliberate, not sloppiness. `base/addons/demandresponse/bb4/dr_qeeq.inc`
enters `QEEQ` as the same bracket divided by `(1-DISLOSS_E(IR))`. Folding DR into
`EXOGENOUS` *before* `DIST_LOSSES` grosses it up (`:501-503`) makes
`EXOGENOUS + its DIST_LOSSES share = (raw - down + up)/(1-DISLOSS_E)` reproduce
`QEEQ`'s right-hand side in a single line. Any split has to carry that gross-up
too, or the reported balance stops matching the model's.

What it costs this project:

- Residual load ([0017](0017-correlation-based-flexibility-provision.md)) is
  `EXOGENOUS` + `DIST_LOSSES` + `TRANS_LOSSES` + `ENDO_CCS` + `ENDO_BIOMETHANE`
  + dumb-EV. With `EXOGENOUS` post-DR, the flexibility *need* is measured on a
  DR-flattened signal - DR shrinks the need instead of being credited with
  providing it, and every other option's provision is computed against that
  shrunken need and its FlexSign.
- [0007](0007-flexibility-option-timescale-decomposition.md)'s claim (repeated at
  `estimate_flexibility_needs.py:228-232`) that DR "passively falls into the
  'Other' catch-all" is only half-true: `Other = need - tracked`, and DR sits
  inside `need`, not outside it. It can never carry a sign, and isn't separable
  from Other's other contents.
- [0017](0017-correlation-based-flexibility-provision.md)'s own invariant - every
  `EL_DEMAND_YCRST` category has exactly one home, "never both, never neither" -
  is violated at source: DR has no category, it is spliced into one.
- `estimate_flexibility_needs.py:169-171` documents `EXOGENOUS` as "pure
  inelastic household/industry/agriculture/datacentre load". It is not.

Magnitude, measured against the real GDX rather than assumed: `DR_FLEX_Y` for
`base_F2050`/2050 is **232.9 TWh/a**, against `EXOGENOUS` 3129 TWh (7.4%) and
`ENDO_INTRASTO` 12.5 TWh - DR moves roughly 19x more energy than intraday
electricity storage charging in this system. Every scenario folder sets
`$setglobal DEMANDRESPONSE yes`, so this affects all of them.

MainResults cannot reconstruct any of it: no hourly DR symbol, no up/down or
shed/shift split, and `EXOGENOUS` is already net with no second series to
difference against. `DR_FLEX_Y` additionally exists in two incompatible vintages
in already-produced results - dimension 1 `(Y)` in `base`/`ALLN`/... and
dimension 2 `(Y,AAA)` in the newer `base_WY*` runs, while current code declares
`(Y,AAA)`.

Found while implementing, and worth recording because it changes what this
ADR alters: the hourly and annual electricity-demand symbols already disagreed.
`EL_DEMAND_YCRST`'s `EXOGENOUS` was net of DR, but `EL_DEMAND_YCR`'s is computed
straight from `DE`/`DE_VAR_T` and has always been raw - unlike `H_DEMAND_YCRA`,
which does derive from its own hourly counterpart. Electricity was the odd one
out, and this ADR makes the two agree.

`DR_SETINPUT.inc` models 15 DR technologies: four `DR_SHIFT_HH_*`, four
`DR_SHIFT_TERI_*`, five `DR_SHED_IND_*`, `DR_SHIFT_IND_MECHPULP`, and
`DR_SHIFT_DATACENTER`.

## Decision

**Model side** - `base/output/OUTPUT_SUMMARY.inc`, the single source of truth
(included by `Balmorelbb4.inc:2600` via `'../../base/output/OUTPUT_SUMMARY.inc'`;
no scenario folder carries a local copy, so one edit covers every scenario):

- `EXOGENOUS` becomes raw, pre-DR. The splice at `:429-439` is removed.
- New `DR_FLEX_YCRAST(Y,C,RRR,AAA,S,T,DR_TECH,UNITS)` - net demand response in
  MWh, `VDR_UP - VDR_DOWN`, demand-positive, all 15 technologies. `DR_TECH` sits
  *after* `S,T` so the name is literally accurate and the technology occupies the
  slot `VARIABLE_CATEGORY` occupies in `EL_DEMAND_YCRST`/`H_DEMAND_YCRAST`.
- New `VARIABLE_CATEGORY` value `ENDO_DR` - the same net quantity summed over
  `DR_TECH` - in `EL_DEMAND_YCRST`/`EL_DEMAND_YCR`, plus `DEMAND_DR` in
  `EL_BAL_TYPE` for `EL_BALANCE_YCRST`.
- `DIST_LOSSES` gains a DR term, so `EXOGENOUS + ENDO_DR + DIST_LOSSES` still
  reproduces `QEEQ`'s `/(1-DISLOSS_E)` gross-up.
- `DR_FLEX_Y(Y,AAA)` is kept **unchanged** - it already is annual gross downward
  regulation in TWh, which is exactly the companion the net hourly series needs.
- Net rather than gross up/down on the hourly symbol, for size: ~4.67M
  records/year (535 nonzero area x technology combinations x 8736 h), roughly
  +11% on a 1.29 GB `_R2050` MainResults. Gross downward stays recoverable per
  technology by clipping the negative part - near-exactly, since `DROMVCOST`
  prices `VDR_DOWN` and the LP has no reason to run up and down simultaneously
  within one (area, technology, hour).

**Analysis side:**

- One `"Demand response"` entry in `FLEX_OPTIONS`. `flexibility_needs`' metric is
  correlational - whether a series modulates in phase with residual load's
  deviation - and `kind: "storage"` already nets two directions into one series,
  so the shed-vs-shift distinction does not change what the metric measures.
- Hourly via `{"kind": "consumption", "hourly_category": "ENDO_DR"}` - no new
  `kind`, and no extra GDX read, since `EL_DEMAND_YCRST` is already loaded and
  cached. `_net_hourly`'s `supply - demand` (`:569-587`) turns demand-positive
  `ENDO_DR` into `down - up`, positive when DR reduces load, matching every other
  demand-side option. This is the first real user of `hourly_category`, which
  `estimate_flexibility_needs.py:888-897` supports but no `FLEX_OPTIONS` spec
  currently sets (so 0017's "electrolysers source directly from `ENDO_H2`" is not
  in effect today - out of scope here, but worth knowing).
- Annual "use" in `flex_option_metrics.py` sources `DR_FLEX_Y` (gross),
  deliberately diverging from the hourly net - see Consequences.
- Vintage safety: an old-vintage file is identified by the **absence of the
  `ENDO_DR` category in `EL_DEMAND_YCRST`**, not by the absence of
  `DR_FLEX_YCRAST` - equally decisive, and it costs no extra GDX read since
  `EL_DEMAND_YCRST` is already loaded (`_assert_dr_vintage`, per scenario rather
  than per batch). `estimate_flexibility_needs.py` hard-fails rather than
  warning. The per-folder cache directory is bumped `.gdx_cache` ->
  `.gdx_cache_v2` in all three scripts that share it, so a pre-0030
  `EL_DEMAND_YCRST` pickle cannot be reused for a re-run of the same folder
  name. A scenario genuinely run with `DEMANDRESPONSE=no` would also trip this
  check; none of GREAT's do.
- `"Demand response"` joins `FLEX_OPTION_COLOURS`' electricity storage/movers
  family, alongside V2G, EV charging, electricity storage and transmission -
  shifting technologies dominate it and behave like storage on the balance.
- `DR_FLEX_YCRAST` gets an entry in the pybalmorel fork's
  `balmorel_symbol_columns` - mandatory, not cosmetic, since the script filters on
  named columns. (`DR_FLEX_Y` is absent from that dict and has been running on the
  generic fallback all along.)

## Considered options

- **`ENDO_DR` category only, no standalone symbol.** Rejected - a
  `VARIABLE_CATEGORY` cannot carry `DR_TECH`, and `DR_SHIFT_DATACENTER` is
  directly relevant to this project's datacentre work.
- **Leave `EXOGENOUS` net, add the DR symbol alongside it.** Zero break for
  existing readers, but `EXOGENOUS` stays mislabelled in four places and 0017's
  one-home invariant stays violated.
- **Gross `VDR_UP`/`VDR_DOWN` hourly instead of net.** Rejected on size; clipping
  recovers gross near-exactly.
- **Separate "DR shed" / "DR shift" (and "Datacentre DR") flex options.** Rejected
  for the reason given under Decision - the semantic difference between destroyed
  and time-shifted demand is real, but it isn't what this metric measures.
- **Replace `DR_FLEX_Y` with a `DR_TECH`-resolved annual gross symbol.** Rejected -
  `DR_FLEX_Y` already reports exactly that quantity, both its consumers already
  read it, and replacing it would break `test_datacenter_dsm` for no gain.
- **Reuse `net_category_signed` (the `ENDO_EV` pattern,
  [0016](0016-split-v2g-into-ev-charging-and-v2g.md)).** Rejected - that kind
  clips a net series into demand/supply halves. DR wants one net series, like
  storage.

## Consequences

- **Every existing MainResults becomes old-vintage.** ~90 runs have `EXOGENOUS`
  net-of-DR; new ones have it raw. Files without `DR_FLEX_YCRAST` are rejected
  outright rather than silently producing a number that is wrong by ~7% of
  exogenous demand.
- Flexibility need and every option's provision change for every scenario: the
  need rises by the DR that was previously flattening it, and each tracked
  option's share is recomputed against the new residual load and FlexSign. Any
  figure produced before this ADR is not comparable to one produced after.
- `EL_DEMAND_YCRST`'s per-region totals are **unchanged** (raw `EXOGENOUS` + net
  `ENDO_DR` = old `EXOGENOUS`). `EL_DEMAND_YCR`'s are **not**: its `EXOGENOUS`
  was already raw (see Context), so adding `ENDO_DR` shifts each country's annual
  total by its net DR - negative, and bounded above in magnitude by the shed
  share of `DR_FLEX_Y`'s 232.9 TWh. `categorize_countries.py` sums that symbol
  unfiltered, so Demand High/Low labels - and with them the frozen category
  membership of
  [0004](0004-fixed-category-membership-for-cost-aggregation.md) - can move.
  Re-checking the reference scenario's labels after the first re-run is the
  cheapest way to see whether any country actually crosses.
- `ENDO_DR`'s **annual** value is near-zero for the ten shift technologies -
  `QDR_STORE_SHIFT` forces `sum(up) ~= sum(down)` per weekly cycle, differing only
  by `DRLOSS`. Annual DR volume must therefore always come from `DR_FLEX_Y`, never
  from `EL_DEMAND_YCR` Category=`ENDO_DR`. This is why `flex_option_metrics.csv`'s
  DR "use" and `flexibility_needs.csv`'s DR magnitude measure different things -
  0016 refused exactly this divergence for V2G, but there both figures were
  meaningful and consistency was the tiebreak; here the net annual is not a "use"
  number at all, it is the `DRLOSS` residual.
- The DR-driven share of `DIST_LOSSES` sits in residual load while `ENDO_DR` sits
  in the DR flex option - the same treatment P2H already gets (its losses in
  `DIST_LOSSES`, `ENDOGENOUS_ELECT2HEAT` in the PtH option), not a new
  inconsistency.
- `test_datacenter_dsm` (`tests/test_balmorel.py:170-199`) keeps working, since
  `DR_FLEX_Y` is untouched.
- Recovering DR for already-run scenarios is partially possible but deliberately
  out of scope here. `all_endofmodel.gdx` holds full hourly `VDR_UP`/`VDR_DOWN`
  per `DR_TECH` (`VDR_DOWN` = 4,673,760 records = 535 x 8736 for `base`) for 13
  main scenarios' `_R2050` runs - under `/work3/mberos/Balmorel/`, not the GREAT
  tree - and for 14 weather-year `_R2050` runs. Nothing exists for any `_F2050` or
  `_INV` run in any folder: there is one `all_endofmodel.gdx` per folder and it is
  always whichever run wrote last. A backfill would therefore leave DR present on
  R rows and absent on F rows, which
  [0028](0028-run-type-aware-weather-year-summarization.md) keeps separate anyway.
