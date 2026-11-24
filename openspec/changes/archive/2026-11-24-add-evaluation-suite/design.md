# Design: add-evaluation-suite

## Data
- Micro-sensors: 2026-10-19 11:00 to 11-18 15:35 (528 hours with data), 臺中市 1,191 and 高雄市 1,369 sensors.
- National stations: 2026-08-20 to 11-24, 6 + 12 stations.
- Details: `docs/analysis/T-25_期末實驗資料集.md`.

## E1 forecasting
- Split per station: first 70% of hours for training (the last 15% of it for validation and tuning), the remaining 30% for testing.
- Models: persistence, MLR (existing), random forest and gradient boosting (scikit-learn); Optuna with 40 trials each and a fixed seed.

## E2 calibration
- Existing `src/analytics/calibration.py`, frozen period, 1 km co-location radius, leave-one-site-out.

## E3 source attribution
- Background fields: real hours whose city-wide coherence is low (no rising event), sampled with a fixed seed.
- Injection types and labels:
  - local plume (+10 to +30 μg/m³ within 1.5 km) → `local`
  - subregional cluster (most sensors within 6 km, ring untouched) → `subregional`
  - regional rise (all sensors ×1.6 to ×2.5) → `regional`
  - single sensor +40 → `suspected_sensor_fault`
  - no change → `no_clear_event`
- The rising rule compares each sensor with its own previous 6 hours, so an injection is applied to the last hour only.
- Baselines:
  - **AQI-only:** labels `regional` when the local value exceeds the AQI "普通" upper bound, else `no_clear_event`. This mimics a color-only reading.
  - **Nearest-sensor excess:** labels `local` when the nearest sensor exceeds the regional median by 10 μg/m³, else `regional` when the median rises 50%, else `no_clear_event`.

## E4 agent
- 40 questions × 4 configurations; expected behaviour per question: first-ranked action category, whether to clarify, whether to refuse.
- Configurations (a) and (d) are deterministic or tool-grounded; (b) and (c) use the same Gemini model as (d).
- Free-tier quota: the runner caches responses on disk and resumes, so the run can be spread over several days.
