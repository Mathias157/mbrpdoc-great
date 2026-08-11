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
