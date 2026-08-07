# Add SLURM job scripts for a second HPC cluster, alongside the existing LSF ones

**Status**: accepted

## Context

The GREAT pipeline has so far run exclusively on DTU's LSF cluster
(`scripts/Balmorel/jobs/*.sh`, submitted via `bsub`). We're now also using a
second HPC cluster that schedules via SLURM (`sbatch`) instead. Both clusters
stay in active use, so the LSF scripts can't simply be replaced — SLURM
versions need to exist alongside them.

Two different scenario-folder conventions were live in `jobs/` at the time of
this migration:

- An older "O-year" convention (`fullyear_2030.sh`, `fullyear_2040.sh`,
  `rolling_2030.sh`, `rolling_2040.sh`, `scenario_choice.sh`,
  `submit_year_runs.sh`, `submit_backupsens_year_runs.sh`): submitted from the
  Balmorel repo root, writing results into `O2030`/`O2040`-style subfolders.
  Unmodified for months.
- A newer per-scenario convention (`investment.sh`, `fullyear_2050.sh`,
  `rolling_2050.sh`): submitted from inside a scenario folder (e.g. `EVN/`),
  using a per-scenario `config.sh` instead of the shared
  `jobs/scenario_choice.sh`. This is where
  [ADR 0001](0001-warm-start-fullyear-timeout.md)'s warm-start/RESLIM/
  auto-resubmit logic lives, and the only convention still being actively
  extended.

Carrying both conventions forward into a second scheduler would double the
inconsistency for no benefit.

## Decision

- SLURM scripts unify on the newer per-scenario/`config.sh` convention only.
  The O-year convention is deprecated and its scripts
  (`fullyear_2030.sh`, `fullyear_2040.sh`, `rolling_2030.sh`,
  `rolling_2040.sh`) are deleted outright, along with
  `submit_year_runs.sh` (already dead — its call site in `investment.sh` was
  commented out in favour of directly submitting `fullyear_2050.sh`) and
  `submit_backupsens_year_runs.sh` (structurally tied to the `O*` folders).
  `jobs/scenario_choice.sh` is kept — it's still used by the convention-
  agnostic utility scripts (`analyse.sh`, `tempaggregation.sh`,
  `get_adequacies.sh`) and carries no O-year-specific logic itself.
- SLURM scripts live in a new `jobs/slurm/` subdirectory, mirroring the
  filenames under `jobs/`, rather than suffixed siblings in the same
  directory. `fullyear_2030.sh`/`fullyear_2040.sh` get SLURM siblings too
  (generalized onto the new convention, without ADR 0001's warm-start
  machinery — that's specific to the ALLN/VGN 2050 long-pole case).
- Resource requests translate LSF's per-core `-n`/`span[hosts=1]` model onto
  SLURM's `--cpus-per-task`/`--nodes=1`, keeping each job's existing core
  count rather than requesting a whole node (`--exclusive`). GAMS/CPLEX is
  single-node multi-threaded, not MPI, so whole-node allocation would just
  leave most cores idle while blocking other jobs from sharing the node.
  LSF's per-core `rusage[mem=X]` has no SLURM equivalent here: `sinfo -N -p
  rome` shows every node in the partition reporting `RealMemory=1` (1MB,
  clearly untracked rather than real), so any `--mem`/`--mem-per-cpu` request
  above that is unsatisfiable on every node and `sbatch` rejects it outright
  ("Memory specification can not be satisfied"). Memory requests are dropped
  from all `jobs/slurm/*.sh` scripts; jobs are scheduled by CPU count alone
  on this partition.
- Partition `rome`, no `--account`/`--qos`.
- GAMS is located via the same `.env`-based `GAMS_SYSTEM_DIR` →
  `PATH`/`LD_LIBRARY_PATH` pattern as the LSF scripts (`jobs/slurm/
  functions.sh`), not a `module load` — this cluster needs no module system
  for GAMS, just a `.env` pointing `GAMS_SYSTEM_DIR` at
  `/groups/INP/gams/gams46.5_linux_x64_64_sfx`. `pixi` is not yet installed on
  this cluster, so `pixi run ...` calls are left in place in the ported
  scripts (unchanged from their LSF originals) rather than stripped out; the
  affected lines get commented out by hand until `pixi` is available there.
- This cluster's `rome` partition was initially assumed to have a generous
  multi-day wall-time ceiling; `scontrol show partition rome` later showed
  `MaxTime=2-00:00:00` — 48h, actually *tighter* than LSF's 72h cap that
  motivated ADR 0001's warm-start chain in the first place. That chain stays
  (ALLN/VGN still get the dual-simplex warm-start path — a tighter ceiling
  makes hitting it more likely, not less), with `jobs/slurm/fullyear_2050.sh`
  and `jobs/slurm/rolling_2050.sh` requesting the partition's actual 48h
  maximum (`--time=2-00:00:00`) and RESLIM set just below that. The 3-hop cap
  from ADR 0001 is unchanged, which shrinks the total warm-started budget for
  a non-converging scenario from ~12 days (4 × 72h on LSF) to ~8 days (4 ×
  48h here) — worth revisiting if a scenario actually exhausts it.

- Unlike LSF's `bsub`, this cluster's `sbatch` does not reliably start the job
  in the directory it was submitted from — every per-scenario script
  (`investment.sh`, `fullyear_*.sh`, `rolling_*.sh`) and repo-root utility
  script (`analyse.sh`, `tempaggregation.sh`, `get_adequacies.sh`) opens with
  an explicit `cd "$SLURM_SUBMIT_DIR"` (the directory `sbatch` was invoked
  from, always exported into the job's environment) before doing anything
  relative-path dependent, rather than assuming the scheduler's default cwd
  matches the submission directory.
- Even with cwd fixed, bash's `source`/`.` only searches `$PATH` for a bare
  filename (one with no `/` in it) — it does not fall back to cwd. The
  per-scenario scripts' `source config.sh` therefore failed non-interactively
  (this cluster's batch-job `$PATH` doesn't include `.`) even though it
  worked when run interactively (where the submitting shell's `$PATH`
  apparently does). Changed to `source ./config.sh` in `investment.sh` and
  every `fullyear_*.sh`/`rolling_*.sh` — the explicit `./` bypasses `$PATH`
  lookup entirely. The other `source jobs/...` targets in the repo-root
  utility scripts were already unaffected, since they contain a `/`.
- The pre-existing `not [ -d/-f ... ]` idiom (valid in `zsh`, not in `sh`/
  `bash`) and an unguarded `$LD_LIBRARY_PATH` reference under `set -u` were
  both latent bugs in the original LSF scripts that happened to never
  surface there (LSF's submitting shell already exported a — possibly empty —
  `LD_LIBRARY_PATH`, and the scripts were presumably tested from `zsh`). They
  do surface on this cluster's `sbatch` environment, so the SLURM copies
  (`jobs/slurm/functions.sh`, `investment.sh`, `tempaggregation.sh`) fix both;
  the `jobs/` LSF originals are untouched and still carry the same bugs.

## Consequences

- `jobs/` (LSF) and `jobs/slurm/` (SLURM) now both need updating for any
  future pipeline change that touches job submission — there is no shared
  script between the two schedulers beyond scenario-local files like
  `config.sh`.
- The O-year convention and its scripts are gone entirely, including from the
  LSF side. Any in-flight work relying on `O2030`/`O2040`-style scenario
  folders needs to move onto the per-scenario/`config.sh` convention first.
- `fullyear_2030.sh`/`fullyear_2040.sh` (both clusters, going forward) no
  longer accept a `--SCNAME=$scenario` GAMS argument the way the deleted
  O-year scripts did — scenario selection now comes entirely from the
  per-scenario folder + `config.sh`, matching how `fullyear_2050.sh` already
  worked.
- The `CONTEXT.md` "Wall-time" glossary entry, previously defined strictly as
  LSF's `#BSUB -W`, is broadened to also cover SLURM's `--time` now that two
  schedulers are in play.
