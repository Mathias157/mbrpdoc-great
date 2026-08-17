# Decompose each flexibility option's own hourly use the same way as residual load

**Status**: accepted

## Context

`estimate_flexibility_needs.py` already decomposes hourly residual load into
Daily/Weekly/Annual flexibility need (see [0006](0006-residual-load-definition-for-flexibility-needs.md)),
system-wide and per Combined category. That tells us how much flexibility
the system needs at each timescale, but nothing about which flexibility
option (see [CONTEXT.md](../../CONTEXT.md)'s "Flexibility option" entry, and
`flex_option_metrics.py`'s `FLEX_OPTIONS`) is actually supplying it, or at
what timescale each option operates.

The same `flexibility_needs()` hierarchical decomposition can be applied
directly to an option's own hourly dispatch/use series instead of residual
load - e.g. does electricity storage cycle mostly daily, does transmission
smooth mostly weekly variation? This only works for options whose own
MainResults symbol carries an hourly Season/Time dimension:

- **Technology options** (heat pumps, electricity/heat/hydrogen storage,
  electrolysers) read `PRO_YCRAGFST`, already loaded for residual load's own
  supply side.
- **Transmission options** (electricity, hydrogen) read their own
  `X_FLOW_YCRST`/`XH2_FLOW_YCRST` - the hourly counterpart to the annual
  `X_FLOW_YCR`/`XH2_FLOW_YCR` `flex_option_metrics.py` uses for its scatter
  plots.
- **Peaker** is derived from `PRO_YCRAGFST` the same way
  `flex_option_metrics.py` does (`backup_production`).
- **V2G** (`V2G_FLEX_YCR`) and **Demand response** (`DR_FLEX_Y`) have no
  `ST` suffix - this dataset's own naming convention (see pybalmorel's
  `formatting.py`) for "already summed over Season/Time" - so neither
  symbol carries hourly resolution to decompose.

Reusing `PRO_YCRAGFST` for this is also a performance concern: it is the
single heaviest GDX read this script makes (per-technology-option and
per-country-hour), and re-running the script during development (e.g. to
tweak a plot) shouldn't re-read it, `X_FLOW_YCRST`, or `XH2_FLOW_YCRST` from
disk every time.

## Decision

- Add `HOURLY_FLEX_OPTIONS` - the subset of `flex_option_metrics.FLEX_OPTIONS`
  whose `kind` is `"technology"`, `"transmission"`, or `"peaker"`. V2G and
  Demand response are excluded outright, not attempted with an empty/partial
  result.
- For each entry, decompose its own hourly country-level use with the same
  `flexibility_needs()` function used for residual load, producing two new
  `group_type` values in `flexibility_needs.csv`: `flex_option_system`
  (`group="All"`, one row per `flex_option`) and `flex_option_category`
  (`group=<Combined category>`, one row per `flex_option`).
- Two new plots in `flex_needs_plots/`: `system_by_option.png` (same 3-panel
  Daily/Weekly/Annual layout as `system.png`, but bars/legend = flex option)
  and `category_by_option.png` (a grid: one row per Combined category, one
  column per timescale, bars/legend = flex option within each subplot).
  `system.png`/`category.png` themselves are unchanged - residual load only.
- `PRO_YCRAGFST`, `EL_DEMAND_YCRST`, `X_FLOW_YCRST`, and `XH2_FLOW_YCRST` are
  now pickle-cached to `<output-dir>/.gdx_cache/<symbol>.pkl` on first read,
  self-contained (no click context, unlike `analyse.py`'s own
  `collect_results` pickle cache) since this script isn't invoked through
  that CLI. `--overwrite-cache` forces a fresh GDX read when new HPC results
  have been synced down under the same scenario names.

## Consequences

- A reader comparing `system_by_option.png`'s per-option TWh/a to
  `system.png`'s residual-load TWh/a is comparing two different signals
  (an option's own dispatch magnitude vs. what the system needs balanced) -
  the former isn't a "coverage" or "share of need met" number, just the same
  hierarchical decomposition applied to a different hourly series.
- V2G and Demand response never appear in `system_by_option.png`/
  `category_by_option.png` - not a bug, just no hourly symbol to decompose.
- `.gdx_cache/*.pkl` can go stale if new HPC results are synced down for a
  scenario name this script has already cached - `--overwrite-cache` is the
  escape hatch, not automatic invalidation (no cheap way to detect "this GDX
  changed" without re-reading it).
