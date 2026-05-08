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
| 1. EV Electrification | Current assumptions | Pessimistic 2050 EV fleet scenario | Quantified fleet growth rate / stock data |
| 2. V2G Adoption | Smart bidirectional charging | Dumb uni-directional charging | Exogenous V2G capacity profile |
| 3. Heat-Pump Penetration | Current assumptions | Reduced residential HP adoption | HP penetration % by region; LCA/cost barriers data |
| 4. Isolationism | TYNDP2024 reference grid | Reduced transmission investment | TYNDP transmission constraints; investment caps |
| 5. Industry Electrification | Current assumptions | Reduced PtX in industry | Industry electrification scenarios; PtX adoption % |
| 6. Hydrogen Demand | Baseline H₂ demand | IEA pessimistic H₂ scenario | IEA projections; Kountouris baseline assumptions |
| 7. Electrolyser Flexibility | Flexible operation + storage | Fixed transport H₂ profile | Assumed constant H₂ transport demand profile |
| 8. Large-Scale Storage | Optimal sizing | Pessimistic availability | LCA / space-usage / policy constraints |
| 9. Datacentre Flexibility | Flat demand + flexible response | Flat demand only | TYNDP2024 datacentre demand; DR potential definition |

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

**Current Status**: ❌ No source identified  
**Data Required**: Regional residential HP penetration rates; barriers to adoption (cost, retrofit difficulty)

**Action Items**:
- [ ] Search: "Heat pump adoption barriers Europe 2050" (IEA, IRENA, AGORA)
- [ ] Find: regional penetration projections (% of buildings with heat pumps) for pessimistic scenario
- [ ] Quantify: reduction vs. baseline (e.g., baseline 70% → pessimistic 40%)
- [ ] If not found: use assumption (see below)

**Assumptions if Source Not Found**:
- Pessimistic residential HP penetration = 40% by 2050 (vs. baseline 70%)
- Heat pump adoption bottleneck = retrofit costs + social acceptance + distribution grid constraints
- Reduce power-to-heat flexibility capacity in individual heating areas by 40%
- Document source and reasoning in assumptions log

**Suggested Sources** (if available):
- IEA Technology Roadmap: Heat Pumps
- AGORA Energiewende building retrofit scenarios
- Fraunhofer ISE heat pump deployment studies

---

### 4. Isolationism / Transmission Constraints

**Current Status**: ✅ Source identified  
**URLs**: 
- [TYNDP2024 Reference Grid & Investment Candidates](https://2024-data.entsos-tyndp-scenarios.eu/files/scenarios-inputs/20231103-Electricity-and-Hydrogen-Reference-Grid-Investment-Candidates.xlsx.zip)
- [TYNDP2024 Line Data](https://2024-data.entsos-tyndp-scenarios.eu/files/scenarios-inputs/Line-data.zip)

**Data Included**: Reference grid topology, transmission investment candidates, line-level data

**Action Items**:
- [ ] Download both TYNDP2024 files → `data/tyndp-2024/`
- [ ] Extract transmission capacity data (reference grid scenario)
- [ ] Define "isolationism": use reference grid only; no investment candidates enabled
- [ ] Calculate transmission limits for grid model
- [ ] Cross-check with Theo's prior analysis (vault-mirror notes mention transmission sensitivity)
- [ ] Verify against GREAT current assumptions for baseline transmission

**Assumptions if Data Unclear**:
- Isolationism scenario = reference grid only; investment candidates (AC/DC lines) disabled
- Baseline scenario = reference grid + selected investment candidates
- Document choice and reasoning

**Notes**: TYNDP is authoritative source; this dimension is well-supported.

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

**Current Status**: ⚠️ Partial source  
**Sources Mentioned**:
- IEA pessimistic H₂ demand case
- Kountouris baseline assumptions (in model or Theo's work)

**Action Items**:
- [ ] Find IEA H₂ demand scenarios (pessimistic case): [IEA Global Hydrogen Review](https://www.iea.org/reports/global-hydrogen-review)
- [ ] Extract 2050 hydrogen demand (EU / Nordic focus) for pessimistic vs. baseline
- [ ] Cross-check against current GREAT model assumptions (ask Theo/Kountouris)
- [ ] Document: baseline H₂ demand (PJ/yr) vs. pessimistic (PJ/yr) by application (transport, industry, etc.)

**Assumptions if Source Not Found**:
- Pessimistic H₂ = 30% reduction vs. baseline (e.g., baseline 200 PJ → pessimistic 140 PJ by 2050)
- Rationale: continued fossil fuels, slower CCS deployment, competition with biofuels
- Document source and reasoning

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

**Current Status**: ❌ No source identified  
**Data Required**: Storage constraints from LCA / space availability / policy; reduced storage capacity

**Action Items**:
- [ ] Search: "Energy storage LCA constraints" or "Grid energy storage availability scenarios"
- [ ] Find: regional storage potential limits (MWh capacity) for pessimistic case
- [ ] Or: find multi-energy storage trade-offs (battery vs. hydrogen vs. heat storage)
- [ ] If not found: use assumption (see below)

**Assumptions if Source Not Found**:
- Pessimistic storage = 50% reduction in large-scale capacity vs. baseline
- Rationale: LCA constraints (lithium/rare earths), space limitations, policy barriers
- Or: assume only hydrogen storage available (no battery storage > 1 day)
- Document in assumptions log

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
| EV Electrification | TBD | Pending consensus.app review | Pending | ⏳ |
| V2G Adoption | TBD | Needs definition | Vault notes | ⏳ |
| Heat-Pump Penetration | 40% residential by 2050 (vs. baseline 70%) | Retrofit cost barriers | Assumption | ⏳ |
| Isolationism | 50% reduction in transmission investment | Reference grid only | TYNDP2024 | ⏳ |
| Industry Electrification | 30% reduction in industrial PtX | Continued fossil + CCS | Assumption | ⏳ |
| Hydrogen Demand | 30% reduction vs. baseline | Slower H₂ adoption | IEA (TBD) | ⏳ |
| Electrolyser Flexibility | Constant transport profile | High capacity factor targets | Assumption | ⏳ |
| Large-Scale Storage | 50% capacity reduction | LCA + space constraints | Assumption | ⏳ |
| Datacentre Flexibility | 0% demand response (pessimistic) | No flexible workload shifting | Assumption | ⏳ |

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

**Snakemake workflow**: `rules/` contains rules for each data source. Example: `rules/download_tyndp2024.smk` downloads demand scenarios, reference grid, and line data into `data/tyndp-2024/`.

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
- [ ] Download TYNDP2024 data (use Snakemake rule in `rules/download_tyndp2024.smk`)
- [ ] Extract & quantify EV pessimistic scenario from Consensus papers
- [ ] Find or assume HP adoption barriers study
- [ ] Find or assume industry electrification scenario
- [ ] Find IEA H₂ demand pessimistic case
- [ ] Define electrolyser constant profile (or get from literature)
- [ ] Define large-scale storage constraints
- [ ] Finalize datacentre demand response potential
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

