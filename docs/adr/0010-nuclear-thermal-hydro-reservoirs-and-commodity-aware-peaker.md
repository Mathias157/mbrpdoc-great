# Add Nuclear, Thermal, Hydro reservoirs, and per-commodity Peaker to flexibility options

**Status**: accepted

## Context

`FLEX_OPTIONS` covered sector-coupling and storage technologies but had no
entry at all for the "ordinary" dispatchable generation fleet — condensing
thermal plants, CHP, nuclear, reservoir hydro — even though these are just
as much a part of how the system balances variability as anything already
tracked. Checking `PRO_YCRAGF` by `Commodity`:

- Electricity: `CHP-BACK-PRESSURE`, `CHP-EXTRACTION`, `CONDENSING`,
  `HYDRO-RESERVOIRS` (dispatchable, unlike `HYDRO-RUN-OF-RIVER`) were
  entirely untracked. `CONDENSING`'s `Fuel` values include `NUCLEAR`
  alongside fossil/biomass/waste fuels.
- Heat: `BOILERS` was untracked.
- Hydrogen: `STEAMREFORMING` (`Fuel=NATGAS`) was untracked.

Both `CONDENSING` and `BOILERS` also carry backup/peaker capacity, mixed in
at the `Technology` level: `Generation.str.contains("BACKUP")` rows exist
under both (confirmed via a live GDX: `ELECTRICITY` backup is entirely
`CONDENSING`, `HEAT` backup is entirely `BOILERS`) — exactly the mechanism
`backup_production()` already uses to build the existing `Peaker` option,
which hardcoded `commodity="ELECTRICITY"`, leaving heat's own backup
capacity invisible. Hydrogen has no backup rows at all — no peaker mechanism
exists there. `Fuel=='DUMMY'` was considered and rejected as the exclusion
filter: it doesn't match this dataset's actual backup fuel (natural gas),
whereas the `Generation`-string filter does, consistently with how `Peaker`
already works.

## Decision

- New options, all supply-side only (`metric_types=("capacity","use")`,
  always positive), each excluding `Generation.str.contains("BACKUP")` rows:
  - **Nuclear**: `CONDENSING`, `Fuel=NUCLEAR`. Electricity only.
  - **Thermal**: `CONDENSING` (minus nuclear) + `CHP-BACK-PRESSURE` +
    `CHP-EXTRACTION` on the electricity plot; the same two CHP
    technologies' heat co-production + `BOILERS` on the heat plot;
    `STEAMREFORMING` (no exclusion needed — confirmed no backup rows) on
    the hydrogen plot.
  - **Hydro reservoirs**: `HYDRO-RESERVOIRS`. Electricity only.
- `Peaker` becomes two entries, `Peaker (electricity)` and `Peaker (heat)`,
  each `backup_production(pro, commodity=...)` filtered to its own
  commodity — not a hardcoded pair chosen for convenience, but because the
  data confirms exactly these two commodities have a backup mechanism and
  hydrogen doesn't.

## Consequences

- `Thermal`'s heat-plot number and electricity-plot number are both driven
  in part by the same CHP technologies' dispatch, but represent different
  physical quantities (electricity vs. heat output) — same caveat as
  [0008](0008-commodity-aware-signed-flexibility-options.md)'s heat
  pump/electrolyser split.
- If a future scenario introduces hydrogen backup capacity, `Peaker` won't
  pick it up automatically — a third `Peaker (hydrogen)` entry would need
  to be added by hand, matching how the electricity/heat entries were
  added here.
