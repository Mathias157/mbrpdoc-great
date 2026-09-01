# Sign transmission's flexibility provision by net import/export, not gross unsigned flow

**Status**: accepted

## Context

`estimate_flexibility_needs.py`'s `flex_option_hourly_net()` computed the
"Electricity transmission"/"Hydrogen transmission" options' hourly signal as
`abs(X_FLOW_YCRST/XH2_FLOW_YCRST)`, grouped by `Country` and treated entirely
as `"supply"` (`_net_hourly(supply, _EMPTY_HOURLY)`), inherited unchanged from
`flex_option_metrics.py`'s own `"transmission"` handling
([0008](0008-commodity-aware-signed-flexibility-options.md), which explicitly
scopes transmission as an unsigned utilisation magnitude for that script's
capacity/use ranking view — a deliberate, still-correct decision *there*).

Checked directly against `MainResults_base_R2050.gdx` (not assumed): `X_FLOW_YCR(ST)`
and `XH2_FLOW_YCR(ST)` are never negative (0 of 615,067 hourly rows checked),
so the `abs()` was a no-op, not a real safeguard. More importantly, `Country`
on this symbol is always the *exporting* region's country (checked against
all 200 annual rows) — a separate row exists for the reverse direction of any
bidirectional link, keyed by the other country. Grouping by `Country` and
summing therefore only ever captured a country's own **exports**, mislabelled
as `"supply"` (positive/injecting) — imports never appeared under that
country's own rows at all. `[0017](0017-correlation-based-flexibility-provision.md)`'s
correlation-based `flexibility_provision()` needs each option's true net
signed dispatch as input (`P_i(t)`) to correctly attribute whether that
option's operation aligned with or opposed the system's own need at each
hour — an export-only, always-non-negative signal cannot do that.

## Decision

`flex_option_hourly_net()`'s `"transmission"` branch now computes a genuine
net position per country-hour: import minus export, via the existing
`_net_hourly(supply, demand)` helper — the same pattern already used for
`"storage"`. Import is `Value` grouped by `To` (mapped to its country via the
`region_to_country` param already threaded through this function for
`"peaker"`); export is the existing `Country`-groupby (unchanged). Intra-country
flow (e.g. `NO1→NO2`) nets to zero at the country level automatically, which
is physically correct — only cross-border flow should move a country's own
residual-load balance.

This diverges from `flex_option_metrics.py`'s own `"transmission"` handling,
which stays exactly as [0008](0008-commodity-aware-signed-flexibility-options.md)
left it (unsigned gross utilisation, for a genuinely different question — "how
much was this link used" vs. "did this link's flow reduce or increase
flexibility need"). The two scripts implement `"kind"=="transmission"`
independently (not shared code, only a shared spec-dict vocabulary), so this
change is self-contained to `estimate_flexibility_needs.py`.

## Consequences

- `flexibility_needs.csv`'s "Electricity transmission"/"Hydrogen transmission"
  rows change in both magnitude and sign going forward — a country that's a
  net exporter in a period now shows negative provision there instead of a
  positive (and export-only) number.
- `flex_option_metrics.py`'s own transmission capacity/use plots are
  unaffected — they keep [0008](0008-commodity-aware-signed-flexibility-options.md)'s
  unsigned convention, so the same option now reads differently on the two
  scripts' outputs by design, not by oversight; a reader comparing them needs
  to know which question each one answers.
