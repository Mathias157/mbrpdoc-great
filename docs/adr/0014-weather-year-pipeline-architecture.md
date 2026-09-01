# Weather year pipeline: parallel job scripts, source-scenario simex, shared staging, DAG-external prep

**Status**: accepted

## Context

Making [0013](0013-weather-year-runs-reuse-fixed-investment.md)'s decision
operational required working out where each new piece lives, given three
existing constraints this repo already has:

- `jobs/` (LSF) and `jobs/slurm/` (SLURM) job scripts assume `cwd` is a
  scenario folder and everything they need is reachable via `../` from
  there (see [0002](0002-slurm-migration.md)) - `../base/data/...`,
  `../jobs/slurm/...`.
- Only `scripts/Balmorel/` gets `rsync`'d to the SLURM HPC cluster today
  (`pixi.toml`'s `sync-up`/`sync-down`) - the top-level `data/` folder is
  never synced.
- `postprocess.smk` is deliberately kept out of the main Snakemake DAG
  (see [0003](0003-postprocessing-snakemake-flow.md)) when a step is
  expensive/manual rather than "every `pixi run snakemake` should redo
  this".

## Decision

- **New parallel job scripts**, not branches of the existing ones:
  `jobs/slurm/fullyear_2050_wy.sh`/`rolling_2050_wy.sh`, mirroring
  [0002](0002-slurm-migration.md)'s own precedent (new files for new
  scheduler-shaped behaviour, rather than conditionals inside the
  originals). The ordinary per-scenario scripts stay completely
  weather-year-unaware - in particular they never delete `Balmorel.lst`,
  which stays useful for debugging non-WY runs.
- Both scripts derive `year` and `source_scenario` from their own folder
  name (`run_name="$(basename $PWD)"`, split on `_WY` - see
  [CONTEXT.md](../../CONTEXT.md)'s **WY folder**), rather than taking them
  as parameters - the folder *is* the single source of truth for which
  weather year and which source scenario a run belongs to.
- `fullyear_2050_wy.sh` reads `simex_INV` from `../${source_scenario}/`,
  **not** from its own folder - a WY folder never has its own
  `simex_INV` (there's no investment run to produce one, per
  [0013](0013-weather-year-runs-reuse-fixed-investment.md)). The
  orchestrator that creates WY folders doesn't pre-populate `simex` either;
  the job script pulls it directly at run time.
- Weather data (two variants, from **weatheryeardata**) is staged
  **once**, shared, at `scripts/Balmorel/weatheryeardata/`, not duplicated
  per WY folder - both because duplicating this much data across every WY
  folder for every source scenario studied would multiply fast, and
  because it needs to live inside `scripts/Balmorel/` to travel with the
  existing sync (a separate top-level-`data/` sync path was considered and
  rejected for exactly that reason). Each `_wy.sh` script swaps the
  relevant variant into its own `data/` at the start of its step, the same
  way `Y_full.inc`/`Y_roll.inc` already are.
- Script B keeps only `CapDev/raw` (-> `data_raw`, feeds rolling runs) and
  `CapDev/scaled_full_year` (-> `data_scaled`, feeds fullyear runs) from
  `WEATHERYEAR`'s output - confirmed with the user (2026-08-21) that
  `HourlyDispatch/{raw,scaled_long_term}` and `CapDev/scaled_long_term`
  aren't needed at all, so they're neither copied nor synced. (An earlier
  version of this decision kept all five `WEATHERYEAR` variants including
  `HourlyDispatch`, on the reasoning that it was cheap to keep and might
  serve a future weather-year-aware investment run - superseded by this
  correction.)
- The two new preprocessing scripts that produce `weatheryeardata`
  (looping `pybalmorel.WEATHERYEAR` over 1982-2020, then trimming the
  output down to just `CapDev/{raw,scaled_full_year}`) live in
  their own `rules/weatheryear.smk`, run manually
  (`pixi run snakemake --snakefile rules/weatheryear.smk`), kept out of
  the main `Snakefile` DAG - same reasoning as
  [0003](0003-postprocessing-snakemake-flow.md): 39 years of `WEATHERYEAR`
  calls is expensive, manually-triggered work, not something every
  `pixi run snakemake` should redo. Still gets Snakemake's own
  incremental/skip-if-done behaviour, just not on the default path.
- The scenario-folder orchestrator itself
  (`scripts/preprocessing/create_weather_year_scenarios.py`) and the
  submitter script are plain Python/shell, no Snakemake involvement -
  their output is meant to be `rsync`'d and run via `sbatch`, never read
  back as Snakemake output. The orchestrator is exposed as a pixi task
  (matching `sync-mainresults` and friends), not just a bare
  `pixi run python ...` invocation.
- `WEATHERYEAR`'s raw model-output inputs (`weatheryear_inputs_folder`)
  live at `data/weatheryear_inputs/` in *this* repo, not in the sibling
  `pybalmorel` repo - it's a manually-downloaded dataset (e.g. from DTU
  Data), same category as `data/tyndp-2024`/`data/af25`/
  `data/balanza2026`, not something either repo generates. `data/` is
  already fully gitignored, so this needs no new `.gitignore` entry.
- The orchestrator's WY folder skeleton is deliberately minimal: `data/`,
  `model/`, `simex/` (empty - populated at run time, see above), and
  `config.sh` copied from the source scenario. No `logerror/` or
  `output/{economic,inputout,printout,temp}` - nothing in the WY pipeline
  writes to them, unlike ordinary scenario folders.
- `model/` gets exactly the static files the WY job scripts actually call:
  `Balmorel.gms`, `cplex.op2`, `cplex.op4`, `balopt_full.opt`,
  `balopt_roll.opt` - not `balopt_inv.opt` (no investment step, per
  [0013](0013-weather-year-runs-reuse-fixed-investment.md)) and not
  `cplex.op3` (the ALLN/VGN warm-start option file - the WY fullyear
  script doesn't implement [0001](0001-warm-start-fullyear-timeout.md)'s
  warm-start branch, so nothing references it). Generated artifacts
  (`Balmorel.lst`, `*.gdx`, etc.) are never copied - GAMS produces them
  fresh each run.

## Consequences

- A WY folder's `simex/` is only ever correct while its source scenario's
  `simex_INV/` still exists and is untouched - deleting or re-running the
  source scenario's investment run silently invalidates every weather year
  run still reading from it.
- `weatheryeardata/` is a new, gitignored addition to `scripts/Balmorel/`
  (smaller than an earlier version of this decision that also kept
  `HourlyDispatch`, now dropped - see above) - every `sync-up`/`sync-down`
  still moves it too, even for work that doesn't touch weather years at all.
- Two more scripts (`jobs/slurm/*_wy.sh`) now need updating in lockstep
  with the ordinary ones for any future shared change (e.g. a new solver
  option) - the same maintenance cost [0002](0002-slurm-migration.md)
  already accepted for LSF vs. SLURM now also applies to WY vs. ordinary
  scripts.
- No warm-start/resubmit support for WY fullyear runs: if an
  ALLN/VGN-sourced weather year run ever hits wall-time without
  converging, `fullyear_2050_wy.sh` just hard-fails rather than
  resubmitting a warm-started continuation the way the ordinary
  `fullyear_2050.sh` does for those two scenarios. Worth revisiting if
  that combination is actually studied and turns out to need it.
