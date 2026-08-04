# GREAT — Agent Instructions

You operate inside the GREAT research repo. See `README.md` for what the
project is; this file is the operational protocol.

## Repo Layout

```
.
├── Snakefile                   # The DAG: data -> preprocessing -> report + tests
├── rules/                      # Additional Snakemake rules (e.g. download_data.smk)
├── config/default.yaml         # Pipeline parameters
├── profiles/default/           # Snakemake profile
├── scripts/                    # GREAT-specific preprocessing scripts (feed Balmorel inputs)
│   └── Balmorel/               # Git submodule (Mathias157/Balmorel) — has its own
│                                #  nested submodule at base/data, and its own
│                                #  analysis/ toolkit (see below)
├── report/                     # LaTeX report (compiled to PDF via latexmk)
├── tests/                      # Pytest tests of pipeline outputs
├── data/                       # Raw input data (gitignored)
├── docs/research-strategy.md   # Carlini-derived research-direction principles
├── pixi.toml / pixi.lock       # Environment + dependency lockfile
└── .github/workflows/          # CI: reproduction.yaml, lint.yaml
```

## Critical Conventions

**LLM agents in this repo are forbidden from running `git commit` under any
circumstances.** Commits are exclusively the user's responsibility.

**Nested submodules.** `scripts/Balmorel` is a git submodule that itself
contains a submodule (`base/data`). After cloning or pulling, run:

```
git submodule update --init --recursive
```

Uninitialized submodules look like empty directories — don't assume the code
or data is missing before checking this.

## Snakemake Discipline

The DAG runs data → preprocessing → analysis → LaTeX report → tests:

1. Edit `scripts/*.py` (or add new scripts) for new analysis steps.
2. Add corresponding rules in `rules/*.smk` and `include:` them in `Snakefile`.
3. Update `config/default.yaml` with new parameters.
4. Add tests to `tests/test_*.py`, referenced as fixtures in `tests/test_runner.py`.
5. Run `pixi run snakemake --cores 4` to verify the DAG resolves and produces
   `build/main.pdf` and `build/test.success`.

`.github/workflows/reproduction.yaml` re-runs this on every push/PR and
monthly. Keep it green.

**Note:** the `run`/`plot` rules in `Snakefile` are still the template's demo
(`scripts/model.py` says so explicitly) — the DAG currently only proves
preprocessing works end-to-end, it does not run or plot Balmorel yet. Balmorel
runs themselves happen on HPC, outside the DAG (see below).

## `scripts/` vs. `scripts/Balmorel/analysis/` — Two Different Toolkits

`scripts/` (top level) and the submodule's own `analysis/` folder both exist
in this repo, but they're deliberately separate and serve different projects:

**`scripts/` (top level, in the DAG).** GREAT-specific, one-off preprocessing
that turns raw data into Balmorel inputs —
`preprocessing/{datacentres,evs,grids,industry}.py` write `.inc` files into
`scripts/Balmorel/base/data/`. Runs via `pixi run snakemake`, per the
"Snakemake Discipline" section above. This code is not meant to be reused
outside GREAT.

**`scripts/Balmorel/analysis/` (inside the submodule, NOT in the DAG).** The
general-purpose Balmorel plotting/analysis toolkit, deliberately kept inside
the `Balmorel` submodule (not this repo) so it's reusable across future
Balmorel-based projects, not just GREAT. Run directly against Balmorel
results, independent of Snakemake:

- `analyse.py` — a large Click CLI (~30 subcommands: `cap`, `production`,
  `costs`, `LCOE`, `map`, `matrix`, `storage_profile`, `adequacy`,
  `bar_chart`, `profile`, ...). Invoke via `pixi run analyse <command> [args]`
  (the pixi task already `cd`s into `scripts/Balmorel`).
- `verify.py` — sanity checks that a scenario's results aren't nonsensical.
  Invoke via `pixi run verify <sc-folder> <command>`.
- `functions/heatmap.py` — results-x-scenarios heatmap plotting (the
  `CachedResults` class here caches loaded GAMS symbols per-run to avoid
  re-reading large GDX files).
- `functions/formats.py`, `functions/pit_storage.py` — shared formatting
  helpers and storage-profile extraction.
- `specific/` — one-off analyses that don't belong in the general CLI. If a
  GREAT-only analysis grows out of `specific/`, it likely belongs in this
  repo's `scripts/` instead, not the submodule — keep project-specific code
  out of Balmorel so future projects reusing it aren't cluttered with GREAT's
  concerns.
- `plots/`, `files/` — gitignored outputs (rendered plots) and caches
  (pickled GAMS symbols). Not committed; synced instead (below).

**Why the split:** Balmorel executions require HPC (GAMS/CPLEX), so they
happen outside this repo's Snakemake DAG, on DTU's LSF cluster (see
`scripts/Balmorel/jobs/*.sh`, submitted via `bsub`). The actual workflow is:

1. Snakemake preprocessing (top-level `scripts/`) writes Balmorel inputs.
2. `pixi run sync-up` pushes the repo (incl. inputs) to HPC.
3. Balmorel investment/fullyear/rolling runs execute on HPC (see
   `scripts/Balmorel/README.md` for the three-step soft-linking procedure).
4. `pixi run sync-down` / `sync-plots` / `sync-output` / `sync-mainresults`
   pull results back.
5. `pixi run analyse <command>` / `pixi run verify` (submodule's
   `scripts/Balmorel/analysis/`) produce plots and checks from those results.
6. Plots/tables feed into `report/` (LaTeX).

Only step 1 and (eventually) step 6 are wired into the Snakemake DAG today;
steps 2-5 are manual/CLI-driven.

## Research Strategy

When evaluating whether a research direction is worth pursuing (not just
whether it's technically feasible), consult `docs/research-strategy.md` — 8
principles derived from Nicholas Carlini's "How to Win a Best Paper Award"
(e.g. "if you don't do this, how many months until someone else does?").

## Tone & Style

- Match the user's language — Danish or English, mixed is fine.
- The user is doing PhD-level research (energy systems, sector coupling,
  Balmorel modelling). Don't condense into pop-science.
- Honest assessments matter more than encouragement. If an idea or result is
  weak, say so.

## When in Doubt

1. Read `README.md` for project context.
2. Read `docs/research-strategy.md` if the question is about direction, not mechanics.
3. Ask the user one specific question, not five.
