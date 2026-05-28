# Wiki Index

## Topics

- [[great-scenarios]] — GREAT's 9×9 scenario matrix for evaluating flexibility value; grounded in TYNDP 2024 narratives (Distributed Energy, Global Ambition); operationalized through 9 binary dimensions
- [[nuclear-investment-options]] — Nuclear investment options added to GREAT scenarios based on IEA eTech Brief Update: Nuclear Power in TIMES Modelling (2026)
- [[temporal-resolution]] — Temporal aggregation strategy for BALMOREL: S=8 seasons, T=24 time-steps often outperforms advanced clustering (related vault-mirror note: `GREAT Temporal Resolution`)
- [[debugging-max-electricity-transmission]] — Root cause and fix for infeasible transmission constraints (`VXKNACCUMNET.UP < 0`). **Root cause**: `XKFX` (exogenous capacity) was inflated with the sum of TYNDP2024 reference grid + all candidates, leaving no room for endogenous investment. **Fix**: Rebuilt `XKFX` using TYNDP2024 reference grid only, ensuring asymmetrical capacities (e.g., `DE4-S,AT,800` and `AT,DE4-S,7500`).

## Concepts

- [[iea-aps-scenario]] — IEA's Announced Pledges Scenario: baseline demand (APS) reflects stated government climate pledges; GREAT flexes tech adoption around this target
- [[nested-git-submodules-reproducibility]] — Using nested Git submodules to pin large dependencies (model code + data) and ensure reproducibility across local development and HPC environments

## Groups

*No group pages yet.*

## Syntheses

*No synthesis pages yet.*

## Entities

*No deep-read entity pages yet.*

## Queries

- [[great-scenario-data-sources]] — Data acquisition rules, sources, and assumptions for 9×9 GREAT scenario matrix; TYNDP2024 download template in `rules/download_data.smk`
- [[datacentre-flexibility]] — Lit-search workspace on datacentre demand response potential & inter-regional workload migration; 7 papers, shiftability 20–50%, inter-regional latency 10–100ms
- [[nested-submodules-hpc-setup]] — Step-by-step procedure for initializing nested submodules on HPC systems after cloning a repository

## Research Evaluations

*No research evaluations yet. Brainstorm a direction with the LLM (it triggers the research-companion skill), then save the verdict to `wiki/research-evaluations/YYYY-MM-DD-<topic-slug>.md`.*

---

## Meta & Infrastructure

- `wiki/meta/principles/academic-writing.md` — 30 prose-quality principles for research writing
- `wiki/meta/principles/research-strategy.md` — 8 strategy principles (Carlini-derived) for research ideation and triage
- `wiki/meta/docs/PATTERN.md` — Wiki content patterns and structural conventions
- `wiki/meta/docs/architecture.md` — Wiki and repo architecture overview
- `wiki/wiki.schema.md` — Page type definitions and schemas
- `wiki/AGENTS.md` — Agent protocol for wiki operations
