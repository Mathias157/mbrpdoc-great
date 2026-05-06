---
type: topic
related_projects: [GREAT]
key_papers: []
last_reviewed: 2026-05-06
---

# Temporal Resolution & Aggregation in Energy Systems Modelling

## Overview

Temporal resolution—the granularity at which time is discretised in model runs—is a critical parameter in energy systems modelling that directly affects solution quality, computational cost, and the adequacy metrics (ENS, LOLE) that measure system reliability. The GREAT project has conducted extensive sensitivity analyses to identify optimal trade-offs between representativeness and tractability across different model horizons (2030, 2040, 2050) and run types (investment optimisation vs. rolling-horizon operational).

See vault note: `[[GREAT Temporal Resolution]]` for the full analysis narrative, including run status, methodological choices, and the key insight that simple season-term (ST) selection with S=8 and T=24 often outperforms more sophisticated clustering methods.

## Key Findings

### Aggregation Method Comparison (S8T24 resolution)

Testing was conducted on four aggregation approaches:

- **ST (Season-Term)**: Regular, evenly-distributed seasons and terms. Simple baseline.
- **CD, MM, MD**: Clustering-based approaches (see `temporal_aggregation.md` in scenario folders for formal definitions).
- **CD/MM/MD + F1**: Variants weighted by regional flexibility metrics (sum of DE+DH+SUBTECHGROUPKPOT+HYDROGEN_DH2).
- **FTSS (Full Timeseries Scaling)**: Full timeseries with scaling; found to produce "completely wrong results" and abandoned.
- **FLH (Full Load Hours)**: Regenerated FLH aggregated to match aggregated profiles; poor performance, not pursued.

### Main Conclusions

1. **FTSS performs poorly** — full timeseries scaling in `balopt` leads to unreliable results; usedtimesteps approach is correct.
2. **F1 weighting improves over unweighted clustering** — but still underperforms simple ST selection.
3. **ST selection is robust** — the simple choice of evenly-distributed S and T consistently yields adequate system representations.
4. **Method choice varies by horizon** — while ST is generally best:
   - 2030: MDF1 approach may be worth reconsidering
   - 2040: MMF1 shows some promise
   - 2050: ST clearly dominates

### Trade-offs: Adequacy vs. Computation Time

Increasing term resolution (T) improves adequacy metrics substantially (reducing ENS and LOLE). However:
- Higher T resolution increases computation time, especially for rolling-horizon runs.
- Lower S with higher T may trade off seasons for terms but with diminishing returns.
- S8T42 and S12T42 variants were tested; S10T42 and S10T42MMF1FLH showed infeasibility or memory limits.

## Data & Analysis Artefacts

Analysis results stored in `wiki/sources/analyses/`:

- **`TemporalAggregationFinalResults.ods`** — Comprehensive comparison table (ENS and LOLE metrics across aggregation methods, model years 2030–2050, run types F and R).
- **`TemporalAggComputationTime.ods`** — Computational trade-offs: run times for various resolution choices (S8T24, S8T42, S12T42, etc.).

These spreadsheets are the source data backing the vault note analysis.

## Current State & Open Questions

- **Resolution for GREAT baseline**: S8T42 (ST) is the adopted choice, balancing adequacy and tractability.
- **Why do clustering methods underperform?** The vault note queries whether there may be issues in the pybalmorel weighting script or clustering logic.
- **Backup price caveat**: The analyses predate the discovery that backup prices were too low, warranting re-validation against updated runs with corrected pricing.

## Related

`[[GREAT]]` — parent project page
`[[GREAT Model Development History]]` — broader model evolution context
`[[pybalmorel Timeseries Aggregation]]` — aggregation methodology documentation
