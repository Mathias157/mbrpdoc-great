# Mind Graph — Datacentre Flexibility
Last updated: 2026-05-13

---

### Demand Response Potential & Shiftability
- **Description**: Quantification of datacentre workload fraction that can be shifted in time or space (inter-regional migration) in response to grid signals.
- **Related sub-themes**: Workload characterisation, latency constraints, cost models
- **Key papers**:
  - [zhao-datacentre-demand-2021] Zhao et al. (Energies 2021) — virtual datacentre model
- **Other relevant papers**:
  - [ahmed-iot-renewable-2026] Ahmed et al. (JOIV 2026) — article looking more generally into 'internet of things' devices contribution to grids
  - [fridgen-virtualizing-2015] Fridgen et al. (2015) — historical baseline; likely lower shiftability

---

### Inter-Regional Workload Migration
- **Description**: Feasibility and overhead of migrating datacentre workloads across regions to exploit spatial flexibility (e.g., low-cost electricity in region A vs. high-cost in region B).
- **Related sub-themes**: Latency constraints, optical network capacity, cloud-to-edge control, renewable energy correlation
- **Key papers**:
  - [riepin-spatiotemporal-2025] Riepin, Brown, Zavala (Advances in Applied Energy 2025) — **Optimal spacing 300–400 km; cost reduction 1.29 ± 0.07 EUR/MWh per % flexible load; three spatio-temporal signals identified**
  - [leniston-cloud-interop-2025] Leniston et al. (arXiv 2025) — cloud-to-edge control latency <1s; demonstrates technical feasibility
  - [zhu-optical-migration-2020] Zhu et al. (IEEE Access 2020) — inter-regional data transfer latency (10–100ms); bandwidth requirements
- **Other relevant papers**:
  - [arumugam-iot-renewable-2025] Arumugam et al. (ICESC 2025) — IoT-based predictive analytics for migration timing

---

### Cost & Penalty Models
- **Description**: Operational cost models for datacentre DR participation (e.g., cooling energy, server wear-and-tear, SLA penalties) and system-level cost impacts of 24/7 CFE procurement.
- **Related sub-themes**: Synthetic cost models, Balmorel parameterisation, emissions reduction value
- **Key papers**:
  - [zhao-datacentre-demand-2021] Zhao et al. (Energies 2021) — explicit cost/penalty model for DR participation; directly applicable to Balmorel
  - [riepin-24cfe-costs-2024] Riepin & Brown (Energy Strategy Reviews 2024) — system-level emissions reduction 572 kgCO₂/a per MWh participating load; hourly matching strategy
- **Other relevant papers**:
  - [riepin-spatiotemporal-2025] Riepin et al. (Advances in Applied Energy 2025) — cost curve 1.29 ± 0.07 EUR/MWh per % flexible load

---

### Energy System Modelling Integration
- **Description**: How datacentre DR is represented in energy system models (e.g., Balmorel, PyPSA).
- **Related sub-themes**: Exogenous vs. endogenous modelling, sector coupling
- **Key papers**:
  - (None yet; this sub-theme is a gap)
- **Other relevant papers**:
  - [How detailed cross-sector modelling changes electricity-system results] (vault-mirror) — general sector coupling modelling principles; applicable to datacentres
