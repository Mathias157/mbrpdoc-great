# Weather-year individual-user heat: pull base's INDIVUSERS_DH/INDIVUSERS_DH_VAR_T into DH.inc/DH_VAR_T.inc directly, keep the addon's own override slot suppressed

**Status**: accepted

## Context

[0015](0015-weather-year-inc-file-loading.md) deliberately writes each WY
folder's `data/INDIVUSERS_DH_VAR_T.inc` empty, suppressing the `indivusers`
addon's hourly heat-demand profile entirely for weather-year runs rather
than falling back to the source scenario's non-weather-year-aware data.

That decision only suppressed the addon's *profile* override
(`data/INDIVUSERS_DH_VAR_T.inc`, read by
`base/addons/indivusers/bb4/indivusers_dh_var_tadditions.inc`'s own `$if
EXIST`), not the paired *annual demand* override
(`data/INDIVUSERS_DH.inc`, read the same way by
`indivusers_dhadditions.inc`) - no WY folder wrote either file's
counterpart, and `INDIVUSERS_DH.inc` was never suppressed. So
`indivusers_dhadditions.inc` fell through to `base/data/INDIVUSERS_DH.inc`
- real, positive annual demand (e.g. `BE_IDVU-HOTWTR` RESIDENTIAL =
10,201,458 MWh/year) - while `indivusers_dh_var_tadditions.inc` used the
WY folder's own empty override, contributing nothing.

Both `base/data/INDIVUSERS_DH.inc` and `base/data/INDIVUSERS_DH_VAR_T.inc`
assign *directly* into the main `DH(YYY,AAA,DHUSER)`/
`DH_VAR_T(AAA,DHUSER,SSS,TTT)` parameters for the individual-user
`*_IDVU-HOTWTR`/`*_IDVU-SPACEHEAT` areas (not into a separately-named
`INDIVUSERS_DH`/`INDIVUSERS_DH_VAR_T` symbol - the addon's own
`indivusers_dhadditions.inc`/`indivusers_dh_var_tadditions.inc` are just
the include wrappers around that same `DH`/`DH_VAR_T` target). So the net
effect was every individual-user heat area getting a positive annual `DH`
with a `DH_VAR_T` that summed to zero - nowhere to put the energy across
the year.

Confirmed against an actual solve: `base_WY1982`'s run (`Balmorel.lst`)
returned `MODEL STATUS 4 Infeasible` with 18,050 infeasible rows (`SUM
8.2348928E+8`, `MAX 4.2070549E+8`). CPLEX's dual simplex reported this as
`LP status (22): dual objective limit exceeded` - a red herring; GAMS's own
solve summary underneath was unambiguous about infeasibility, not
unboundedness. `errors.out` diffed against a working `base` run's own
`errors.out` showed ~116 extra "must have positive values" lines, all
`*_IDVU-HOTWTR`/`*_IDVU-SPACEHEAT` areas - matching the gap exactly.
Checked the same failure mode for individual-user *electricity* demand
(`INDIVUSERS_DE`/`INDIVUSERS_DE_VAR_T`, same addon pattern) and found no
equivalent gap: no WY folder writes either override file for those, so
both annual demand and profile fall through to base together, still
paired.

## Decision

- **`clean_weather_year_inputs.py`'s `DH_INC_CONTENT`** gets
  `$include '../../base/data/INDIVUSERS_DH.inc';` inserted right after the
  base `DH.inc` include, before the `DH_RESH`/`DH_RESIDENTIAL`/
  `DH_TERTIARY` scaling overlays:
  ```
  $include '../../base/data/DH.inc';
  $include '../../base/data/INDIVUSERS_DH.inc';
  $include '../data/DH_RESH.inc';
  $include '../data/DH_RESIDENTIAL.inc';
  $include '../data/DH_TERTIARY.inc';
  ```
- **`clean_weather_year_inputs.py`'s `CONCAT_FILE_BASE_INCLUDE["DH_VAR_T.inc"]`**
  gets a second prepended line, `$include '../../base/data/INDIVUSERS_DH_VAR_T.inc';`,
  right after the base `DH_VAR_T.inc` include and before the year-specific
  concatenated `DH_VAR_T_RESIDENTIAL`/`DH_VAR_T_RESH`/`DH_VAR_T_TERTIARY`
  assignments. Since later plain assignments always win (see
  [0021](0021-weather-year-cleaning-static-topology-and-hydro-flh-fallback.md)),
  this gives a layered fallback for IDVU areas: base's non-weather-year
  profile first (safety net for whatever the year-specific data doesn't
  cover), overlaid by genuinely weather-year-aware `DH_VAR_T` values
  wherever WEATHERYEAR's own DHUSER-split output happens to include an
  IDVU area (confirmed some do, e.g. `LT_IDVU-SPACEHEAT`/`TERTIARY`).
- **`create_weather_year_scenarios.py`** now also writes an empty
  `data/INDIVUSERS_DH.inc` alongside the existing empty
  `data/INDIVUSERS_DH_VAR_T.inc` - both stay deliberate no-ops. Since the
  real data is now pulled into `DH.inc`/`DH_VAR_T.inc` directly, these
  empty files exist purely so `indivusers_dhadditions.inc`/
  `indivusers_dh_var_tadditions.inc`'s own `$if EXIST` checks don't fall
  back to base *again* and double-apply the same data through a second
  path.

Same tradeoff [0015](0015-weather-year-inc-file-loading.md) already
accepted for `INDUSTRY_DE_VAR_T`/`INDUSTRY_DH_VAR_T`: individual-user heat
*timing* is only weather-year-aware where WEATHERYEAR happens to cover an
IDVU area; everywhere else it's base's non-weather-year-aware profile.
Annual totals were always fixed from the source investment run regardless
(see [0013](0013-weather-year-runs-reuse-fixed-investment.md)).

## Considered options

- **Make `data/INDIVUSERS_DH_VAR_T.inc` itself `$include` base's data**
  (fall back through the addon's own override slot rather than routing
  through `DH.inc`/`DH_VAR_T.inc`). Rejected: `indivusers_dhadditions.inc`
  and `indivusers_dh_var_tadditions.inc` are two independent addon hooks
  (own `$onmulti`/no-`$onmulti` handling, own DEUSER/DHUSER-group logic
  upstream in `base/data/INDIVUSERS_DH*.inc` before the final assignment)
  - re-enabling them for WY runs risks pulling in more of that addon logic
  than intended, where routing the already-resolved `DH`/`DH_VAR_T`
  assignments in via `DH.inc`/`DH_VAR_T.inc` only takes the final output.
- **Also suppress `INDIVUSERS_DH`** (zero the annual demand for WY runs
  instead of giving it a profile) - would remove indivusers heat from WY
  runs entirely rather than reintroduce a non-weather-year-aware profile.
  Not chosen: no indication indivusers heat demand should disappear from
  weather-year runs, and it would silently change what's being optimized
  rather than just fix a data-consistency bug.

## Consequences

- Verified end-to-end: applied as a manual quickfix to `base_WY2012`
  overnight, and that scenario's full solve went optimal (no longer
  infeasible).
- If individual-user heat timing needs to become weather-year-sensitive
  for the areas WEATHERYEAR doesn't currently cover, this fallback should
  be revisited.
