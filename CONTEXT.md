# mbrpdoc-great

Research repo for GREAT energy-system scenarios built on the Balmorel model, including the HPC job pipeline that runs Balmorel on DTU's LSF cluster.

## Language

**Fullyear run**:
A single, monolithic LP solve of one target year's full temporal resolution (all 8760 hours, all seasons at once, `SOLVETYPE=RMIP`). Produces the exact joint-seasonal dispatch and storage result for that year. No internal checkpoints — it is one `SOLVE` statement from start to finish.
_Avoid_: Full run, year run

**Rolling run**:
A season-windowed LP solve of a target year (`RollingSeasons=yes`), run after its fullyear run. Storage state is fixed at each window boundary before moving to the next window. Approximates the fullyear result faster, but doesn't see inter-seasonal storage arbitrage beyond a window.
_Avoid_: Rolling horizon run (fine in prose, but "Rolling run" is the pipeline's own name for the job)

**Investment run**:
The MIP solve that determines capacity investment decisions across all modelled years. Runs before any fullyear/rolling run for a scenario, and its results seed them.

**Wall-time**:
The scheduler's hard job-duration limit — `#BSUB -W` on the LSF cluster, `#SBATCH --time` on the SLURM cluster (see [0002](docs/adr/0002-slurm-migration.md)). Exceeding it gets the job SIGKILLed immediately — no chance for GAMS or CPLEX to write a savepoint, close logs, or exit in a controlled way. Distinct from **RESLIM**, GAMS/CPLEX's own internal solver time limit: most jobs leave it at its shared default (far longer than any job's wall-time, so it never triggers), but the rolling 2050 jobs (both clusters) and the fullyear 2050 jobs' ALLN/VGN warm-start path override it to sit just below that cluster's wall-time, so CPLEX yields control before the scheduler kills the job outright.
_Avoid_: Timeout (ambiguous between the two)

**Graceful stop**:
CPLEX voluntarily ending a solve (by hitting its own RESLIM, set below wall-time) before LSF's wall-time kill fires — so GAMS regains control, writes its savepoint GDX, and exits with a distinguishable status instead of being SIGKILLed mid-solve with nothing recoverable.

**Warm start**:
Resuming a solve from a previous attempt's solution point (levels and basis) instead of starting cold. Only meaningful for simplex-family LP methods — CPLEX's barrier method (the model's current default) does not produce a basis a later solve can resume from.

**Scenario name**:
The single, atomic identifier of one specific `MainResults*.gdx` file — pybalmorel's own `scenario_name`, taken whole (e.g. `EVN_R2050`), never decomposed into folder/run-type/year parts. One scenario folder can hold several scenario names (different run types, target years, and — eventually — weather years, e.g. `EVN_WY2001_R2050`); whatever it encodes, it's handled as one opaque string.
_Avoid_: Result, run (for this level — "Scenario" alone always means the folder)

**Demand category**:
A High/Low label per country per scenario name: High if that country's total demand (electricity + heat + hydrogen, summed in TWh) exceeds the mean total demand across all countries in that same scenario name, Low otherwise.

**VRE category**:
A High Wind / High Solar / High Wind+Solar / Low VRE label per country per scenario name, based on whether that country's wind and/or solar production-to-demand ratio exceeds the mean of that ratio across all countries in the same scenario name.

**Combined category**:
The `{Demand category} Demand / {VRE category}` label per country per scenario name (e.g. "High Demand / High Wind") — the join of Demand category and VRE category, and the level at which cross-scenario comparisons (e.g. cost aggregation) group countries.

**Flexibility option**:
A technology or mechanism whose capacity and/or dispatch can absorb, shift, or smooth demand/supply variability across time or space, evaluated against system cost, emissions, and security of supply to build a priority ranking. Starting (deliberately extensible) list: electricity and hydrogen transmission, heat pumps, V2G, electricity/heat/hydrogen storage, demand response, peaker capacity/production, electrolysers. Most options can be plotted on either axis (capacity in GW, or production/throughput in GWh); for peaker units, whose modelled nameplate capacity is set heuristically large purely to guarantee feasibility (not a real constraint), the analysis instead uses **effective peaker capacity** — the sum, across regions, of each region's own maximum hourly peaker production — as a stand-in for a meaningful capacity figure. V2G and demand response are the exception: their capacity is an exogenous model assumption, not an endogenously optimised decision, so only production/use (GWh) is meaningful for them.

**Reference scenario**:
The single scenario name (default `base_R2050`) whose Combined category assignment is treated as authoritative and reused for every other scenario in a cross-scenario comparison, instead of recomputing Combined category per scenario. Needed because Combined category is mean-relative and can drift between scenarios as dispatch shifts — see [0004](docs/adr/0004-fixed-category-membership-for-cost-aggregation.md).

**Residual load**:
Hourly non-dispatchable demand minus non-dispatchable supply, per Country/Combined category/system. The signal Daily/Weekly/Annual flexibility need is computed from.

**Non-dispatchable demand**:
`EL_DEMAND_YCRST` summed over a configurable set of demand categories via `--demand-categories` (default: `EXOGENOUS` only — inelastic household/industry/agriculture/datacentre load). `ENDOGENOUS_ELECT2HEAT` (heat-pump/resistive-heater electricity use) and `ENDO_EV` (net G2V-minus-V2G EV charging) can be added in, since how inelastic they really are is a modelling judgement call rather than settled fact — see [0006](docs/adr/0006-residual-load-definition-for-flexibility-needs.md). Always excludes storage charging (`ENDO_INTRASTO`/`ENDO_INTERSTO`) and distribution losses (`DIST_LOSSES`), which are dispatchable or technical rather than inelastic.

**Non-dispatchable supply**:
Wind, solar and run-of-river hydro production (fixed, not configurable) — the same "full-certainty" VRE grouping this Balmorel dataset already uses internally (`VRE_CERT_AS.inc`).

**Flexibility need (Daily / Weekly / Annual)**:
Per Geis et al. (2026) — the TWh/a of residual load that must be shifted in time to remove variability at that timescale. Computed as half the summed absolute deviation between one resolution's mean and the next coarser one, chained hourly→daily→weekly→annual so no variability is double-counted across scales.
_Avoid_: Flexibility requirement, storage need (these conflate the need with any one option that could meet it)
