# Wiki Log

Append-only chronological record of wiki operations. Most recent entries at the top.

---

## 2026-05-07

- Created concept page: `wiki/concepts/nested-git-submodules-reproducibility.md`
  - Documented nested Git submodule pattern for reproducibility (Balmorel + Balmorel_data use case)
  - Explains how `git submodule update --init --recursive` ensures all dependencies are pinned and available on HPC systems
  - Added to index under Concepts section

- Created query page: `wiki/queries/nested-submodules-hpc-setup.md`
  - Step-by-step procedure for initializing nested submodules on HPC systems
  - Includes local development setup, HPC clone sequence, and practical Snakemake execution notes
  - Linked to concept page

---

## 2026-05-06

- Created topic page: `wiki/topics/temporal-resolution.md`
  - Ingested temporal aggregation analysis from vault note `GREAT Temporal Resolution.md`
  - Integrated analysis files: `TemporalAggregationFinalResults.ods` and `TemporalAggComputationTime.ods`
  - Documented aggregation methods (ST, CD, MM, MD, F1 variants), findings, and trade-offs
  - Cross-referenced GREAT project context

- Added analysis sources: `TemporalAggregationFinalResults.ods` and `TemporalAggComputationTime.ods` to `wiki/sources/analyses/`
  - Temporal resolution sensitivity analyses from model runs
  - Tracks aggregation effects and computational cost across different time resolutions
