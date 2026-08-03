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
The LSF scheduler's hard job-duration limit (`#BSUB -W`). Exceeding it gets the job SIGKILLed immediately — no chance for GAMS or CPLEX to write a savepoint, close logs, or exit in a controlled way. Distinct from **RESLIM**, GAMS/CPLEX's own internal solver time limit, which today (1,209,600s ≈ 14 days) is set far longer than any job's wall-time and so never actually triggers.
_Avoid_: Timeout (ambiguous between the two)

**Graceful stop**:
CPLEX voluntarily ending a solve (by hitting its own RESLIM, set below wall-time) before LSF's wall-time kill fires — so GAMS regains control, writes its savepoint GDX, and exits with a distinguishable status instead of being SIGKILLed mid-solve with nothing recoverable.

**Warm start**:
Resuming a solve from a previous attempt's solution point (levels and basis) instead of starting cold. Only meaningful for simplex-family LP methods — CPLEX's barrier method (the model's current default) does not produce a basis a later solve can resume from.
