# Run the new region-categorization postprocessing as a separate Snakemake flow, outside the main DAG

**Status**: accepted

## Context

AGENTS.md documents that Balmorel executions happen on HPC outside this
repo's Snakemake DAG, and that steps 2-5 of the workflow (sync-up, the HPC
runs themselves, sync-down, and running `analyse`/`verify`) are deliberately
manual/CLI-driven — only preprocessing (step 1) and eventually report
generation (step 6) are wired into Snakemake. `.github/workflows/
reproduction.yaml` runs the DAG's `all` target on every push/PR and monthly,
with no HPC access, so no synced `MainResults*.gdx` files ever exist in that
environment.

We're adding a script that categorizes countries by Demand (High/Low) and
VRE type (High Wind/Solar/Wind+Solar/Low), reading `EL_DEMAND_YCR`,
`H_DEMAND_YCRA`, `H2_DEMAND_YCR`, and `PRO_YCRAGF` from synced-down GDX
results — and want Snakemake to drive it rather than a bare `pixi run`
script, without breaking CI.

## Decision

- New `postprocess.smk`, a second Snakemake entry point invoked manually
  (`pixi run snakemake --snakefile postprocess.smk`) once results are synced
  down, kept entirely separate from the main `Snakefile` and from
  `reproduction.yaml`'s `all` target. This keeps CI green by construction,
  rather than relying on a `checkpoint` rule to degrade gracefully when no
  GDX files exist — this repo has no `checkpoint` precedent today.
- Presence of results is determined by globbing
  `scripts/Balmorel/*/model/MainResults_*.gdx` directly at rule-eval time.
  The gitignored files on disk are the source of truth; no separate state
  file tracks what's synced.
- The categorization code lives in top-level `scripts/`, not
  `scripts/Balmorel/analysis/specific/` — a deliberate exception to the
  split AGENTS.md documents (top-level `scripts/` writes Balmorel inputs;
  the submodule's `analysis/` reads Balmorel results and is kept reusable
  across future Balmorel-based projects). This categorization logic
  (Demand/VRE labeling by mean-within-scenario-name thresholding) is
  GREAT-specific research, not intended as general-purpose Balmorel tooling.
- Outputs land in a new `build_postprocess/` at the repo root
  (`categorization.csv` + `maps/`), separate from `build/` (which CI
  populates), and are exploratory for now — not wired into `report/`.

## Consequences

- Two Snakemake entry points now exist in this repo. Anyone running the
  pipeline end-to-end needs to know postprocessing is a separate, manual
  step (`--snakefile postprocess.smk`), not part of
  `pixi run snakemake --cores 4`.
- AGENTS.md's "Two Different Toolkits" section needs a note documenting this
  one exception (top-level `scripts/` now reads results, not just writes
  inputs), so it doesn't read as inconsistent or accidental to a future
  reader.
- If a genuinely reusable Balmorel-categorization tool emerges later, it can
  graduate into `scripts/Balmorel/analysis/` the same way AGENTS.md already
  describes for `specific/` one-offs that outgrow their project-specific
  origins.
