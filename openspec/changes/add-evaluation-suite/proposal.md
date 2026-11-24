# Proposal: add-evaluation-suite

## Why
The final deliverable requires experiments with datasets, metrics, results and comparisons, and the conference draft must report them. The Proposal defined the evaluation plan (forecast, calibration, source attribution, end-to-end agent with baselines and ablation); this change makes each experiment reproducible from one command and writes the results to versioned files.

## What changes
- `experiments/` with one script per experiment and a shared output folder `experiments/results/`:
  - **E1 forecasting:** persistence, multiple linear regression and tree ensembles (hyper-parameters tuned with Optuna on the training period only), horizons 1/3/6 h, chronological split, both cities.
  - **E2 calibration:** leave-one-site-out cross-validation on the frozen micro-sensor period (10/19–11/18), raw vs. linear vs. linear + RH.
  - **E3 source attribution:** semi-synthetic injection on real background fields with known ground truth (local plume, subregional cluster, regional rise, single faulty sensor, no event), compared with two baselines (AQI-only threshold, nearest-sensor excess), plus the two recorded real events.
  - **E4 agent:** a 40-question test set (Traditional Chinese) with expected behaviour labels, comparing (a) AQI-only rules, (b) LLM without tools, (c) LLM with tools but without domain knowledge and quality checks, (d) full AirSleuth.
- Each script prints a summary table and writes CSV/JSON plus figures used by the paper and the slides.

## Capabilities
- New: `evaluation`

## Impact
- Code: `experiments/*.py`, `src/analytics/forecast.py` (new candidate models)
- Docs: results feed `DESIGN.md` (Results), the paper and the final slides
