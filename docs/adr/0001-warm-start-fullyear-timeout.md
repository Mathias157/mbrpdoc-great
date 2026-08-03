# Warm-start the fullyear run across wall-time-limited resubmissions

**Status**: accepted

## Context

Some fullyear scenarios are certain to exceed the 72h LSF wall-time ceiling (the maximum we can request). Today, `RESLIM` (GAMS/CPLEX's own solver time limit) is set far longer than any job's wall-time, so it never triggers — LSF just SIGKILLs the process when wall-time expires, and nothing is recoverable. The active CPLEX config (`cplex.op2`, selected via `--USEOPTIONFILE=2` in the job scripts) also uses `LPmethod 4` (barrier) with `advind 0`, which explicitly discards any previous solution even if one were available.

## Decision

- Set `RESLIM` below each job's wall-time (with a safety margin for data read/write), passed per job type via a `--RESLIM=` command-line override rather than the shared `balgams.opt` constant, so CPLEX yields control to GAMS before LSF's hard kill.
- For this scenario's fullyear run, switch from barrier (`LPmethod 4`) to dual simplex (`LPmethod 2`) with `advind 1`, via a new CPLEX option file (the existing `op2`/`op4`/`op6` are marked "predefined, do not change"). Barrier does not produce a basis a later solve can resume from; simplex does. This trades away some cold-start solve speed for real warm-startability.
- Detect a graceful timeout (as opposed to a genuine failure) by checking `logerror/logfile.out` for `SOLVESTAT EQ 3` ("Resource limit reached"), separately from `functions.sh`'s existing optimal-count check against the BSUB stdout log.
- On a detected timeout, auto-resubmit the job; the new run adds `execute_loadpoint` on the previous run's `OPTION Savepoint=1` GDX immediately before its `SOLVE`, seeding levels and basis from where the last attempt stopped.
- Cap auto-chained resubmissions at 3 hops (~9 extra days beyond the initial 72h). If still unconverged, fail loudly, same as any other pipeline failure today.

## Consequences

- This scenario's fullyear run uses a different LPmethod than the rest of the pipeline (barrier elsewhere) — intentional, not an oversight.
- `RESLIM` is no longer a shared constant across job types; each job script is responsible for passing a value appropriate to its own wall-time.
- A scenario that still hasn't converged after 3 warm-started hops will fail loudly rather than chain indefinitely, bounding HPC allocation spent on a possibly-infeasible-in-practice configuration.
