---
type: topic
created: 2026-05-08
last_reviewed: 2026-05-08
related_projects: [great]
key_papers: [TYNDP 2024]
---

# GREAT Scenarios

## Overview

GREAT's scenario framework evaluates the value of flexibility in future European energy systems by creating a 9×9 scenario matrix (81 investment combinations). Rather than model-centric scenarios, the framework builds on **storylines**—coherent narratives about future uncertainty in technology adoption, trade patterns, and policy choices—and then parametrizes each storyline through a set of 9 binary dimensions.

**Reference vault-mirror notes**: [[GREAT Scenarios]], [[GREAT Storyline]]

---

## Key Scenarios: TYNDP 2024 Storylines

### Distributed Energy (DE)

This scenario pictures a pathway achieving EU27 carbon neutrality target by
2050 with higher European Economy. The scenario is driven by a willingness of
the society to achieve high levels of independence in terms of energy supply
and goods of strategic importance (e. g., industrial and agricultural produce).
It translates into both a behavioural shift and strong decentralised drive
towards decarbonisation through local initiatives by citizens, communities and
businesses, supported by authorities

**Source**: TYNDP 2024 Scenarios Storyline Report

---

### Global Ambition (GA)

This scenario pictures a pathway to achieving carbon neutrality by 2050, driven
by a fast and global move towards the Paris Agreement targets. It translates
into development of a very wide range of technologies (many being centralised)
and the use of global energy trade as a tool to accelerate decarbonisation.

**Source**: TYNDP 2024 Scenarios Storyline Report

---

## Scenario Dimensions in GREAT

GREAT operationalizes these narratives through 9 binary dimensions, each representing an uncertainty in technology adoption or infrastructure investment:

| Dimension | Baseline | Pessimistic Variant | Connection to Narratives |
|-----------|----------|---------------------|---------------------------|
| EV Electrification | High adoption (e.g., 80%+ by 2050) | Pessimistic (e.g., 60% by 2050) | DE: high adoption; GA: moderate adoption |
| V2G Adoption | Smart 2-way charging | Dumb uni-directional only | DE: V2G enabled; GA: variable |
| Heat-Pump Penetration | 70% residential by 2050 | 40% (retrofit cost / social barriers) | DE: high HP; GA: mixed (CCS alternative) |
| Isolationism | Reference grid + investment candidates | Reference grid only (no transmission expansion) | DE: reduced transmission; GA: high transmission |
| Industry Electrification | High PtX penetration | Reduced (continued fossil + CCS) | DE: high electrification; GA: mixed (CCS + trade) |
| Hydrogen Demand | Baseline (e.g., 200 PJ/yr) | Pessimistic 30% reduction | GA: high H₂; DE: lower H₂ (more local electrification) |
| Electrolyser Flexibility | Flexible scheduling + storage | Fixed transport profile (high capacity factor) | GA: flexible; DE: constrained |
| Large-Scale Storage | Optimal sizing | 50% capacity reduction (LCA / space constraints) | GA: high storage; DE: lower storage (local alternatives) |
| Datacentre Flexibility | Flat demand + 30% DR capability | Flat demand only (no demand response) | GA: high DR; DE: limited DR |

**Full reference**: [[great-scenario-data-sources]]

---

## Current State & Debates

### Scenario Construction Logic

Per vault-mirror notes ([[GREAT Scenarios]]), two schools of thought:

1. **Explicit sector coupling** (Baseline): Full endogenous representation of V2G, heat pumps, electrolysers. High model fidelity but computationally expensive (81 × 40 weather years = 3,240 operational runs).
2. **Exogenous profiles** (Pessimistic alternative): Replace endogenous sectors with fixed profiles (e.g., dumb charging for V2G, constant H₂ transport demand). Lower computational cost; requires careful assumption calibration.

GREAT is exploring both; see [[How detailed cross-sector modelling changes electricity-system results]] (vault-mirror) for methodological context.

### Prioritization

Early analysis from Theo (vault-mirror [[GREAT Scenarios]]) identifies **transmission capacity** and **V2G** as particularly sensitive flexibility sources. This suggests the "isolationism" and "V2G adoption" dimensions merit priority in the 3,240 runs, with other dimensions potentially run as "diagonals" (one varied at a time) initially.

---

## Gaps & Opportunities

### Data Collection

Nine dimensions require data validation or assumption refinement:

- **EV pessimistic scenario**: Extract from Consensus.app European EV fleet studies
- **HP adoption barriers**: Find regional retrofit-cost studies or assume 40% baseline
- **Industry electrification**: IEA or McKinsey decarbonization scenarios
- **Large-scale storage constraints**: LCA / resource availability studies
- **Datacentre demand-response potential**: Define % of workload shiftable (suggest 20–50%)

See [[great-scenario-data-sources]] for detailed action items and assumption log.

### Scenario Narrative Depth

Current mapping of TYNDP narratives → GREAT dimensions is rough. Refinement opportunities:

- How do DE's distributed focus and GA's global-trade focus map to storage sizing, transmission investment, and electrolyser location?
- Can other TYNDP narratives (e.g., "Slow Progress") be added as additional dimensions or scenario bundles?
- How do behavioral assumptions (e.g., reluctance to retrofit) translate to model parameters?

---

## Related

**Vault-mirror notes** (read-only reference):
- [[GREAT Scenarios]] — scenario brainstorm, Theo's flexibility findings, prioritization discussion
- [[GREAT Storyline]] — broader GREAT project narrative and context
- [[GREAT Analysis Dogmas]] — model constraints that inform scenario design
- [[How detailed cross-sector modelling changes electricity-system results]] — explicit vs. exogenous sector modelling trade-offs
- [[Literature Review on the Value of Flexibility from Sector Coupling]] — research gap motivating scenarios

**Wiki concepts**:
- [[nested-git-submodules-reproducibility]] — reproducible data lineage for scenario inputs
- [[Concepts/Scenario Design]] (to be created) — methodological patterns for scenario construction

**Wiki queries**:
- [[great-scenario-data-sources]] — active data acquisition task list and assumptions log
- [[TYNDP2024 Integration]] (to be created) — TYNDP-specific download & extraction workflow

---

**Created**: 2026-05-08  
**Last reviewed**: 2026-05-08  
**Status**: ACTIVE — awaiting scenario data collection and dimension refinement
