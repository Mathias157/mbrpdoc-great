# Split V2G into EV charging (demand) and V2G (supply) flex options

**Status**: accepted

## Context

V2G was originally a single flex option (`"net_category"` kind, see
[0008](0008-commodity-aware-signed-flexibility-options.md)) reading one
already-net GAMS variable, `EL_DEMAND_YCRST`/`EL_DEMAND_YCR`
Category=`ENDO_EV` (net G2V-minus-V2G). [0011](0011-signed-flex-need-display-for-demand-side-options.md)
left it unsigned (`+1`, stacked on the supply side of the bar charts)
alongside storage/transmission, on the assumption that, like storage's
round-trip-loss-driven near-zero net, its net-period sum was too close to
zero for a fixed sign to be meaningful either way.

Investigating why V2G's Daily flexibility-need bar
(`estimate_flexibility_needs.py`) came out implausibly large (600+ TWh)
found that assumption doesn't hold: for `base_R2050`/2050, the underlying
`ENDO_EV` series nets to roughly -577 TWh/yr (demand-dominant, not
near-zero) - gross charging ~894 TWh/yr against gross discharge ~318 TWh/yr,
found by summing the raw hourly series' negative and positive parts after
country aggregation. So V2G was being drawn as a large positive/supply bar
in every chart when the option is, in net terms, this system's single
largest demand-side contributor - a real, quantified display error, not
just a naming quibble. (Two other candidate explanations were ruled out
along the way: the daily-need magnitude is mathematically invariant under a
global sign flip of the whole series, so a sign bug couldn't have produced
it either way; and a genuine `ROLLINGSEASONSNUMBER=1` rolling-window
boundary artifact at the start of every week was confirmed but found to
account for only ~4% of the Daily figure, not the bulk of it.)

There is no separate gross-charging or gross-discharge symbol to read -
`V2G_FLEX_YCR`, the dedicated V2G symbol used before 0008, was dropped for
being an "unconfirmed raw domain-fallback symbol"; nothing replaced it.
`ENDO_EV`'s underlying GAMS variable (`VEV_G2V_BEV`/`VEV_G2V_PHEV`) is
itself the only reported net quantity - dumb and smart charging share this
one variable end to end (see below), and there is no per-direction
breakdown anywhere in MainResults.

## Decision

- `FLEX_OPTIONS` splits V2G into two options, both electricity-only, both
  sourced from `ENDO_EV`, differing only in which sign of the negated net
  series they keep: **"EV charging"** (`direction: "demand"`, clips to
  net-negative) and **"V2G"** (`direction: "supply"`, clips to
  net-positive) - kind `"net_category_signed"`.
- The clip happens at raw Region-hour resolution, before any
  Country/Season/Time aggregation, in both `flex_option_metrics.py`'s
  `extract_flex_option_values` (annual scatter plots - now reads the hourly
  `EL_DEMAND_YCRST`-family symbol instead of the annual one, since the
  annual symbol has already collapsed all sign information away almost
  always: given EVs need net energy to drive, essentially every Region
  nets to charging-dominant over a full year, so annual-level splitting
  would put ~100% into "EV charging" and ~0% into "V2G") and
  `estimate_flexibility_needs.py`'s `flex_option_hourly_net` (the
  Daily/Weekly/Annual bars this investigation started from).
- This approximates true gross charge/discharge rather than recovering it
  exactly: a Region-hour with simultaneous charging and discharging that
  nets to one sign silently loses the other side, since only the net is
  ever reported. Accepted as the closest available approximation given no
  better data exists.
- Display sign (`estimate_flexibility_needs.py`'s bar-stacking logic, see
  0011) generalizes from a fixed per-`kind` lookup (`_DEMAND_SIDE_KINDS`) to
  a `_is_demand_side(spec)` check on `kind == "consumption" or
  spec.get("direction") == "demand"`, so "EV charging" stacks below zero
  and "V2G" above, alongside heat pumps/electrolysers - the near-zero
  exception from 0011 no longer covers V2G, since it isn't near-zero.
- **Deferred, not fixed here** (resolved by [0017](0017-correlation-based-flexibility-provision.md),
  which extracts this dumb-charging share into residual load): `ENDO_EV`'s charging side bundles a
  genuinely inflexible "dumb charging" fraction (`EV_BEV_dumb`/
  `EV_PHEV_dumb`, a year×region parameter setting `VEV_G2V_BEV`'s lower
  bound - IEA Global EV Outlook 2024-sourced, `base/data/EV_BEV_dumb.inc`)
  together with the flexible/smart-charging portion, indistinguishably -
  the dumb share isn't separately reported in any MainResults symbol,
  only reconstructable from the input assumption directly. For 2050 (the
  year this investigation covers) the fraction is 0.001 (0.01% under
  `RollingSeasons=yes`, which multiplies it by a further 0.1) - immaterial
  here - but it's 0.5/0.2/0.05 for 2020/2025/2030, so a future run of this
  pipeline against pre-2050 target years would need this addressed before
  trusting "EV charging"'s flex-need numbers as genuinely flexible.

## Consequences

- `flex_option_metrics.csv` and `flexibility_needs.csv` both gain a new
  `flex_option` value ("EV charging") and change what "V2G" means in them:
  previously the net G2V-minus-V2G total, now discharge-only. Any saved
  analysis referencing "V2G" from before this ADR was reading the net
  figure, not the discharge-only one now labelled the same way.
- `flex_option_metrics.py` now reads an additional hourly symbol
  (`EL_DEMAND_YCRST`-family) it didn't need before, for this one kind -
  a real cost (comparable to `PRO_YCRAGFST`, already read there for
  `"peaker"`), accepted for consistency between the two scripts' V2G
  numbers rather than letting them diverge (annual-only split in one,
  hourly split in the other).
- "EV charging"'s flex-need/flex-value numbers overstate genuine
  flexibility by the dumb-charging fraction until that's addressed - see
  Decision above.
