# Wiki Log

Append-only chronological record of wiki operations. Most recent entries at the top.

---

## 2026-05-13

**Lit-Search Workspace: Datacentre Flexibility**  
Created `wiki/queries/datacentre-flexibility/` with:
- `memory-bank.md` — 7 papers discovered (2 Tier-1, 3 Tier-2, 2 Tier-3) on datacentre demand response and workload migration
- `mind-graph.md` — 4 sub-themes: DR potential & shiftability (20–50%), inter-regional migration feasibility, cost models, energy system integration gap
- `references.bib` — BibTeX entries for all papers

**Key finding**: Zhao et al. (2021, Energies) and Zhao et al. (2021, ACCTCS) provide direct cost/penalty model suitable for Balmorel DR parameterisation. Shiftability range 20–50% (Zhao et al., 2021; Ahmed et al., 2026). Inter-regional latency 10–100ms feasible for grid response (Zhu et al., 2020; Leniston et al., 2025).

**Next steps**: (1) Deep-read Zhao et al. (2021, Energies); (2) Extend search for energy system modelling papers; (3) Draft scenario assumptions for GREAT datacentre flexibility dimension.

---

## 2026-05-08 (continued)

**Concept Page: IEA APS Scenario**  
Created `wiki/concepts/iea-aps-scenario.md` — Brief definition of Announced Pledges Scenario used as GREAT demand baseline. Updated index.

**Topic Page: GREAT Scenarios**  
Created `wiki/topics/great-scenarios.md` — Primary integration point for GREAT scenario framework:
- Documents TYNDP 2024 storylines (Distributed Energy, Global Ambition) and their narratives
- Maps 9 binary scenario dimensions to baseline vs. pessimistic variants
- Connects to vault-mirror references ([[GREAT Scenarios]], [[GREAT Storyline]], etc.)
- Cross-links to active data-acquisition query ([[great-scenario-data-sources]])
- Identifies scenario construction logic (explicit sector coupling vs. exogenous profiles) and sensitivity findings
- Flags prioritization (transmission, V2G identified as high-sensitivity flexibility sources)
- Gaps marked: data refinement for EV pessimism, HP adoption barriers, industry electrification, storage constraints, datacentre DR potential

Updated `wiki/index.md`: added [[great-scenarios]] to Topics section.

---

**Snakemake Rule: TYNDP2024 Download**  
Created `rules/download_data.smk` — template rule demonstrating the data acquisition pattern:
- Downloads demand scenarios, reference grid, and line data from ENTSOS
- Extracts .zip archives to `data/tyndp-2024/`
- Includes validation rule for sanity checks
- Generates metadata in `README.md`
- Ready for adaptation to other data sources (EV scenarios, IEA H₂, etc.)

Updated isolationism dimension in query with correct URLs for transmission investment candidates and line data.

**Wiki Housekeeping**  
Updated `wiki/index.md` and `research-state.yaml` to reflect actual wiki state:
- Total pages: 11 (topics, concepts, queries, meta docs)
- Topics: 1 (temporal-resolution)
- Concepts: 1 (nested-git-submodules-reproducibility)
- Queries: 2 (great-scenario-data-sources, nested-submodules-hpc-setup)
- Orphaned links: 6 (documented for future creation)

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
