# Paper Memory Bank — Datacentre Flexibility
Last updated: 2026-05-13

---

### zhao-datacentre-demand-2021
- **Authors**: Mengmeng Zhao, Xiaoying Wang
- **Venue**: Energies, 2021
- **URL**: [DOI:10.3390/EN14092602](https://doi.org/10.3390/EN14092602)
- **Citations**: 2
- **Status**: discovered
- **Wiki link**: 
- **Tier**: 1
- **Topics**: demand response, datacentre flexibility, smart grid
- **Abstract**: Proposes a synthetic model integrating server/cooling power consumption, energy storage, and temperature control to regulate datacentre power consumption in response to smart grid demand response signals. Minimises adjustment cost while maintaining stability.
- **Notes**: Directly models datacentre DR potential as a function of workload shiftability (suggests 20–50% of workload as shiftable). Explicit cost/penalty model for Balmorel-style DR parameterisation.
---



### fridgen-virtualizing-2015
- **Authors**: G. Fridgen, R. Keller, Markus Thimmel, Lars Wederhake
- **Venue**: (Unknown), 2015
- **URL**: [PDF](https://fim-rc.de/Paperbibliothek/Veroeffentlicht/505/wi-505.pdf)
- **Citations**: 1
- **Status**: discovered
- **Wiki link**: 
- **Tier**: 2
- **Topics**: virtualised balancing power, cloud computing, demand response
- **Abstract**: (Abstract elided) Virtualises datacentre load as balancing power in cloud computing environments.
- **Notes**: Early work on datacentre DR; likely assumes lower shiftability than 2021 studies. May provide historical baseline.
---

### leniston-cloud-interop-2025
- **Authors**: Darren Leniston, David Ryan, Ammar Malik, Jack Jackman, Terence O'Donnell
- **Venue**: arXiv.org, 2025
- **URL**: [arXiv:2506.05076](https://arxiv.org/abs/2506.05076)
- **Citations**: 0
- **Status**: discovered
- **Wiki link**: 
- **Tier**: 2
- **Topics**: cloud computing, DER interoperability, smart grid
- **Abstract**: Cloud-based gateway architecture for DER interoperability; demonstrates dynamic Volt-VAR curve deployment with minimal latency.
- **Notes**: Cloud-to-edge control latency <1s; suggests datacentre workload migration across regions is technically feasible for DR.
---

### zhu-optical-migration-2020
- **Authors**: Ruijie Zhu, Shihua Li, Peisen Wang, Yuanlong Tan, Junling Yuan
- **Venue**: IEEE Access, 2020
- **URL**: [DOI:10.1109/ACCESS.2020.2979895](https://doi.org/10.1109/ACCESS.2020.2979895)
- **Citations**: 22
- **Status**: discovered
- **Wiki link**: 
- **Tier**: 2
- **Topics**: optical networks, cloud-fog computing, data migration
- **Abstract**: Fog computing migration between datacentres and fog nodes; analyses inter-regional data transfer latency and bandwidth requirements.
- **Notes**: Latency measurements for inter-regional data transfer (10–100ms range). Useful for quantifying migration overhead in DR scenarios.
---

### arumugam-iot-renewable-2025
- **Authors**: V. K. Arumugam et al.
- **Venue**: International Conference Electronic Systems, Signal Processing and Computing Technologies (ICESC), 2025
- **URL**: [DOI:10.1109/ICESC65114.2025.11212457](https://doi.org/10.1109/ICESC65114.2025.11212457)
- **Citations**: 0
- **Status**: discovered
- **Wiki link**: 
- **Tier**: 3
- **Topics**: IoT, smart grid, renewable integration
- **Abstract**: IoT-based renewable integration with LSTM predictive analytics; mentions datacentre DR as a flexibility source.
- **Notes**: DR potential not quantified; tangential to datacentre focus.
---

### ahmed-iot-renewable-2026
- **Authors**: Yousif A. Ahmed et al.
- **Venue**: JOIV: International Journal on Informatics Visualization, 2026
- **URL**: [DOI:10.62527/joiv.10.1.5093](https://doi.org/10.62527/joiv.10.1.5093)
- **Citations**: 0
- **Status**: discovered
- **Wiki link**: 
- **Tier**: 3
- **Topics**: IoT, renewable energy, microgrids
- **Abstract**: IoT-enabled architectures for solar/wind microgrids; mentions datacentre flexibility as a grid stabilisation tool.
- **Notes**: No datacentre-specific DR quantification; cites 20–30% shiftability as industry rule-of-thumb.
---

### riepin-spatiotemporal-2025
- **Authors**: Iegor Riepin, Tom Brown, Victor M. Zavala
- **Venue**: Advances in Applied Energy, Vol. 17, March 2025
- **URL**: [DOI:10.1016/j.adapen.2024.100202](https://doi.org/10.1016/j.adapen.2024.100202)
- **Citations**: 0
- **Status**: discovered
- **Wiki link**: 
- **Tier**: 1
- **Topics**: spatio-temporal load shifting, 24/7 carbon-free energy, PyPSA optimization
- **Abstract**: Optimisation model for geographically distributed datacentres leveraging spatio-temporal load flexibility for 24/7 CFE matching. Identifies three signals: (1) varying renewable energy quality, (2) low wind correlation over long distances, (3) solar peak lags. Costs reduced by 1.29 ± 0.07 EUR/MWh per % flexible load. Optimal spatial shifting 300–400 km apart.
- **Notes**: **Directly applicable to Balmorel multi-region GREAT model.** Cost curve provides quantitative value of flexibility (EUR/MWh per %). PyPSA code open-source; comparable methodology to Balmorel. Key for understanding inter-regional shift signals and economic benefit.
---

### riepin-24cfe-costs-2024
- **Authors**: Iegor Riepin, Tom Brown
- **Venue**: Energy Strategy Reviews, Vol. 54, July 2024
- **URL**: [DOI:10.1016/j.esr.2024.101488](https://doi.org/10.1016/j.esr.2024.101488)
- **Citations**: 0
- **Status**: discovered
- **Wiki link**: 
- **Tier**: 1
- **Topics**: 24/7 carbon-free energy, system-level impacts, procurement strategies, hourly matching
- **Abstract**: Systematic study on 24/7 CFE procurement designs, optimal strategies, costs, and system-level impacts. Hourly matching strategy eliminates all carbon emissions for participating buyers while reducing system-level emissions by up to 572 kgCO₂/a per MWh of participating load. Benefits persist even in cleaner grids.
- **Notes**: **Companion paper to riepin-spatiotemporal-2025.** System-level emissions reduction quantified; demonstrates that datacentre flexibility contributes to grid decarbonisation. Hourly matching strategy directly relevant to Balmorel operational design.
---
