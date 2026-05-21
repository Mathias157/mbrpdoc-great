---
created: 2026-05-08
last_reviewed: 2026-05-08
page_type: query
---

# GREAT Scenario Data Sources & Acquisition Rules

**Purpose**: Map the data dependencies for GREAT's 9 scenario dimensions, document known sources, flag assumptions, and establish rules for download & integration.

**Reference**: [[GREAT Scenarios]] (vault-mirror)

---

## Scenario Dimensions Summary

The GREAT project builds a 9×9 scenario matrix (81 combinations + operational runs across 40 weather years). Each dimension is a binary toggle:

| Dimension | Baseline | Pessimistic Variant | Data Need |
|-----------|----------|---------------------|-----------|
| 1. EV Electrification | 230 mio. vehicles (Möring et al. 2025) | 179 mio. vehicles (pessimistic) | EV fleet projections (Consensus.app) |
| 2. V2G Adoption | Smart bidirectional charging (V2G) | Dumb uni-directional charging | Exogenous charging profile (German highway data) |
| 3. Heat-Pump Penetration | High adoption (no restriction) | Historic trend-based rollout | Regional HP penetration rates |
| 4. Heat Efficiency | High energy efficiency scenario | Frozen efficiency (Johannsen et al. 2023) | Industrial/residential efficiency scenarios |
| 5. Isolationism (Electricity) | Unconstrained transmission | TYNDP2024 ref. grid + candidates ≤2039 | TYNDP2024 transmission caps |
| 6. Isolationism (Hydrogen) | Unconstrained H₂ infrastructure | TYNDP2024 "low infrastructure" (ref. + 2030) | TYNDP2024 H₂ network constraints |
| 7. Hydrogen Demand | Kountouris et al. 2024 baseline | TYNDP2024 demand | H₂ demand projections (IEA/TYNDP) |
| 8. Electrolyser Flexibility | Flexible operation + storage | Inflexible (constant transport profile) | H₂ transport demand profile |
| 9. Large-Scale Storage | Optimal sizing (baseline restrictions) | 50% reduction (hydrogen, heat, combined) | LCA/space constraints |
| 10. Datacentre Flexibility | Flat demand + 31–100% DSM capacity | Flat demand only (0% DSM) | Datacentre DR potential (TYNDP2024) |

---

## Data Sources by Dimension

### 1. EV Electrification (Pessimistic Scenario)

**Current Status**: ✅ One URL found  
**URL**: [Consensus.app — European EV Fleet 2050 Scenarios](https://consensus.app/search/european-ev-fleet-scenarios-2050/aFJ2qHbIRXiLrbCrvLBqpQ/)

**Action Items**:
- [ ] Extract EV stock projections (million vehicles) by country/region for 2050 (pessimistic case)
- [ ] Compare to your current baseline assumptions in the model
- [ ] Quantify the difference: % reduction in EV penetration for pessimistic scenario
- [ ] Source file: store in `data/ev-fleet-scenarios/` and reference in model config

**Assumptions if Source Unclear**:
- Pessimistic case = no further EV growth beyond 2040; fleet remains ice-dominated
- Or: EV stock grows to 60% by 2050 (vs. baseline 80%+)
- Document the chosen assumption in `wiki/queries/great-scenario-data-sources.md` under "Assumptions Log"

**Notes**: Consensus.app returns citations; you may need to read the linked papers for raw data.

---

### 2. V2G Adoption

**Current Status**: ⚠️ Needs definition  
**Data Required**: Exogenous V2G capacity profile (dumb charging alternative)

**Action Items**:
- [ ] Define baseline: assume current V2G model (smart 2-way charging profile from GREAT)
- [ ] Define pessimistic: remove V2G; revert to dumb uni-directional charging
- [ ] Exogenous profile: either (a) repeat EV charging profile without V2G constraints, or (b) use a reference dataset (e.g., German highway charging profile from PhD-RQII notes)
- [ ] Check `[[2026-02-05 GREAT Storyline]]` vault-mirror note for charging profile assumptions

**Assumptions if No Source Found**:
- V2G dumb charging = EV demand profile flattened (lower peaks, higher troughs) to approximate grid-neutral timing
- Or: use scaled version of baseline profile (e.g., 70% of flexibility)
- Document in assumptions log

**Related Notes**: 
- See `How detailed cross-sector modelling changes electricity-system results` (vault-mirror) for explicit vs. exogenous profile comparisons

---

### 3. Heat-Pump Penetration (Residential)

**Current Status**: ✅ Updated 2026-05-21
**Data Required**: Regional residential HP penetration rates; historic trend data

**Action Items**:
- [x] Use historic trend-based rollout for pessimistic scenario (per [[GREAT Scenarios]] vault-mirror)
- [ ] Cross-check with Heatmap Europe v5 for pessimistic adoption scenarios
- [ ] Quantify: high adoption (baseline) vs. historic trend (pessimistic)

**Assumptions**:
- Pessimistic = historic trend (social/retrofit barriers)
- Baseline = high adoption (no restrictions)
- Document in assumptions log

**Suggested Sources** (if available):
- IEA Technology Roadmap: Heat Pumps
- AGORA Energiewende building retrofit scenarios
- Fraunhofer ISE heat pump deployment studies

---

### 4. Isolationism / Transmission Constraints

**Current Status**: ✅ Updated 2026-05-21
**Finding**: Balmorel investments exceed TYNDP2024 ref. + candidates (e.g., 5 GW vs. 2.4 GW Belgium–UK).

**Decision (2026-05-21)**:
- **Electricity baseline**: Unconstrained
- **Electricity pessimistic**: TYNDP2024 ref. grid + candidates ≤2039
- **Hydrogen baseline**: Unconstrained
- **Hydrogen pessimistic**: TYNDP2024 "low infrastructure" (ref. + 2030 only)

**Action Items**:
- [x] Download TYNDP2024 files → `data/tyndp-2024/`
- [x] Create `grids.py::electricity_transmission()` (XMAXINV.inc)
- [x] Create `grids.py::hydrogen_transmission()` (H₂ constraints)
- [x] Exclude non-existing connections (GAMS `$` condition)
- [ ] Cross-check with Theo's analysis

**Implementation Notes**: 
- `grids.py::electricity_transmission()` produces `XMAXINV.inc` constraining transmission to TYNDP ref. + candidates before 2040.
- Next: `grids.py::hydrogen_transmission()` will extract hydrogen network constraints from TYNDP "low infrastructure" scenario (2030 candidates only; reference grid + no 2040 expansion for H₂).

**Notes**: TYNDP is authoritative source for isolationism boundary conditions; Balmorel produces higher investment levels in unrestricted optimisation.

---

### 5. Industry Electrification

**Current Status**: ❌ No source identified  
**Data Required**: Industry electrification scenarios (H₂ vs. e-fuels vs. CCS); PtX adoption by sector

**Action Items**:
- [ ] Search: "Industry electrification 2050 Europe" or "Industrial heat decarbonization scenarios"
- [ ] Find: sector-specific PtX penetration rates (steel, chemicals, food, etc.)
- [ ] Quantify: reduction in industrial power-to-heat vs. baseline
- [ ] If not found: use assumption (see below)

**Assumptions if Source Not Found**:
- Pessimistic industrial electrification = reduce all industrial PtX (PtH + PtH₂) by 30% vs. baseline
- Rationale: industry continues with fossil fuels + CCS rather than electrification
- Or: pessimistic = only 40% of industrial heat demand via electrification (vs. baseline 60%)
- Document in assumptions log

**Suggested Sources** (if available):
- IEA Industrial Decarbonization Roadmap
- IRENA Industrial Demand for Renewable Electricity
- McKinsey / BCG Deep Decarbonization studies for Europe

---

### 6. Hydrogen Demand

**Current Status**: ✅ Updated 2026-05-21
**Sources**:
- Baseline: Kountouris et al. 2024
- Pessimistic: TYNDP2024 (current GREAT implementation)

**Action Items**:
- [x] Use TYNDP2024 demand for pessimistic case
- [ ] Cross-check with IEA Global Hydrogen Review for validation
- [ ] Document baseline vs. pessimistic demand by application

**Related Dimensions**: Links to Industry Electrification (#5) and Isolationism (#4) — more CCS in isolated system may reduce H₂ demand.

---

### 7. Electrolyser Flexibility

**Current Status**: ⚠️ Assumption-driven  
**Data Required**: Transport H₂ demand profile; operating constraints for electrolysers

**Action Items**:
- [ ] Define "fixed electrolyser": assume constant transport H₂ demand profile (no storage / flexibility)
- [ ] Check if this profile exists in model or literature
- [ ] Define baseline (flexible): current model electrolyser behavior
- [ ] Document difference in operational constraints

**Assumptions** (reasonable):
- Pessimistic electrolyser flexibility = constant load profile (e.g., 100 kg H₂/hr for transport)
- Rationale: electrolysers achieve high capacity factors to minimize CAPEX recovery time (private economics)
- No hydrogen storage / buffer capacity for electrolyser
- Baseline = flexible electrolyser following system needs (optimal scheduling)

**Related Sources**:
- See vault-mirror: `How detailed cross-sector modelling changes electricity-system results` — discusses PtX detailed vs. simplified models

---

### 8. Large-Scale Energy Storage (Pessimistic Scenario)

**Current Status**: ✅ Updated 2026-05-21
**Data Required**: Storage constraints (LCA/space/policy)

**Action Items**:
- [x] Split into 3 dimensions: hydrogen, heat, combined storage
- [x] Pessimistic: 50% reduction vs. optimal sizing (baseline)
- [ ] Validate with LCA/space-usage studies

**Assumptions**:
- Pessimistic = 50% reduction (hydrogen, heat, combined)
- Baseline = optimal sizing (current restrictions)

**Suggested Sources** (if available):
- IEA Energy Storage Technology Roadmap
- NREL / MIT energy storage scenarios
- National resource availability studies (lithium, nickel, REE)

---

### 9. Datacentre Flexibility

**Current Status**: ✅ Source identified  
**URL**: [TYNDP2024 Demand Scenarios (datacentre component)](https://2024-data.entsos-tyndp-scenarios.eu/files/scenarios-inputs/Demand_Scenarios_TYNDP_2024_After_Public_Consultation.xlsb.zip)

**Data Included**: Projected datacentre electricity demand by region; baseline growth rate

**Action Items**:
- [ ] Extract datacentre demand profile from TYNDP2024 → `data/tyndp-2024/`
- [ ] Define "baseline datacentre flexibility": flat demand + X% demand response capability
- [ ] Define "pessimistic": flat demand only (no demand response)
- [ ] Quantify: what fraction of datacentre load can be shifted? (suggest 20–50% based on workload characteristics)
- [ ] If not found in literature: use assumption

**Assumptions if Demand Response Potential Unclear**:
- Baseline DC demand response = 30% of peak capacity (cooling-flexible workloads can shift 0–2 hours)
- Pessimistic DC = 0% demand response (load follows fixed schedule)
- Or: baseline = 40%, pessimistic = 10% (minimal only)
- Document in assumptions log

**Related Sources**:
- IEA Electricity 2024 (datacentre demand projections)
- IMEC / TU Delft demand-response potential studies
- TYNDP scenarios themselves provide context

---

## Assumptions Log

**Structured place to document any assumptions made when source data is unavailable.**

| Dimension | Assumption | Rationale | Source | Status |
|-----------|-----------|-----------|--------|--------|
| EV Electrification | 179 mio. vehicles (pessimistic) | Möring et al. 2025 | [[EV Scenarios in Balmorel]] | ✅ |
| V2G Adoption | Dumb charging (pessimistic) | Social/technical barriers | Vault-mirror [[GREAT Scenarios]] | ✅ |
| Heat-Pump Penetration | Historic trend (pessimistic) | Retrofit/social barriers | Vault-mirror [[GREAT Scenarios]] | ✅ |
| Heat Efficiency | Frozen efficiency (pessimistic) | Johannsen et al. 2023 | [[@johannsenExploringPathways1002023]] | ✅ |
| Isolationism (Electricity) | TYNDP2024 ref. + candidates ≤2039 | Political constraints | TYNDP2024 | ✅ |
| Isolationism (Hydrogen) | TYNDP2024 "low infrastructure" | Political constraints | TYNDP2024 | ✅ |
| Hydrogen Demand | TYNDP2024 demand (pessimistic) | Kountouris et al. 2024 (baseline) | TYNDP2024 | ✅ |
| Electrolyser Flexibility | Inflexible (constant profile) | High capacity factor targets | Vault-mirror [[GREAT Scenarios]] | ✅ |
| Large-Scale Storage | 50% reduction (hydrogen/heat/combined) | LCA/space constraints | Vault-mirror [[GREAT Scenarios]] | ✅ |
| Datacentre Flexibility | 0% DSM (pessimistic) | No flexible workloads | Vault-mirror [[GREAT Scenarios]] | ✅ |

---

## Data Organization & Snakemake Integration

Data files belong in `data/` organized by source. Snakemake rules in `rules/` orchestrate downloads, extraction, and integration into model input files.

**File structure**:
```
data/
├── tyndp-2024/               # TYNDP2024 source files
├── ev-fleet-scenarios/       # EV stock projections
├── hydrogen-demand/          # IEA H₂ scenarios
├── industrial-electrification/ # Industry decarbonization data
├── datacentre-demand/        # Datacentre load projections
└── assumptions-log.yaml      # Central registry of all assumptions
```

**Snakemake workflow**: `rules/` contains rules for each data source. Example: `rules/download_data.smk` downloads demand scenarios, reference grid, and line data into `data/tyndp-2024/`. Run with `snakemake download_tyndp2024`.

**Metadata**: Every downloaded dataset should have a `README.md` in its directory documenting source URL, access date, license, format, units, and preprocessing steps.

---

## Status Summary & Next Steps

### Completed ✅
- Isolationism / TYNDP2024: source identified, download link confirmed
- Datacentre flexibility: TYNDP2024 covers demand; need to define DR potential
- EV electrification: Consensus.app link found; need to extract raw numbers

### In Progress 🔄
- All dimensions: need to cross-check against Kountouris / Theo's baseline assumptions (ask them)
- Assumptions log: populate with specific values and revisit triggers

### To Do ⏳
- [ ] Cross-check industrial demands: Balmorel vs. Johannsen et al. [[@johannsenExploringPathways1002023]] (due 2026-05-22)
- [ ] Compare datacentre demand: Riepin et al. vs. TYNDP2024+AF25 [[@riepinSpatiotemporalLoadShifting2025]] (due 2026-05-25)
- [ ] Check Heatmap Europe v5 for HP pessimistic scenarios (due 2026-05-26)
- [ ] Populate `data/assumptions-log.yaml` with specific numbers

---

## Cross-References

From vault-mirror:
- [[GREAT Scenarios]] — scenario brainstorm & task list
- [[GREAT Model Development History]] — baseline model assumptions
- [[GREAT Analysis Dogmas]] — model constraints & design choices
- [[How detailed cross-sector modelling changes electricity-system results]] — explicit vs. exogenous sector modelling (relevant for V2G, HP, electrolyser)
- [[GREAT Storyline]] — broader storyline context (may inform pessimistic scenarios)

Related wiki pages (once created):
- [[Topics/GREAT Scenarios Data]] — evolving summary
- [[Concepts/Scenario Design]] — methodological notes
- [[Queries/TYNDP2024 Integration]] — TYNDP-specific guidance

---

**Created**: 2026-05-08  
**Last updated**: 2026-05-08  
**Status**: DRAFT — awaiting data collection and assumption finalization

**See also**: `rules/download_data.smk` — template Snakemake rule for data acquisition

