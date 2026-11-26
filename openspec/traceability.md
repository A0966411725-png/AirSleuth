# Requirement Traceability Matrix

Research claims → OpenSpec requirements → implementation → verification. Every contribution claimed in the paper must have a row here; every row must point to a test or an experiment.

## Research questions

| Research question / claim | Requirement (spec) | Implementation | Verification |
|---|---|---|---|
| RQ1: public micro-sensor networks can classify a PM2.5 rise as local, subregional or regional in real time | source-attribution: Spatial indicators; Definition of a rising sensor; Source type classification; Adaptive local radius | `src/analytics/spatial.py`, `src/agent/tools.py::source_attribution` | `tests/test_spatial.py`; E3 semi-synthetic confusion matrix vs. two baselines; real events 2026-10-23 (Kaohsiung) and 2026-10-19 (Taichung) |
| RQ2: trustworthiness is quantified and explained instead of trusting raw readings | data-quality: Row-level quality flags; Quality summary — sensor-calibration: City-specific calibration; Out-of-site validation — agent-answer: Confidence reflects evidence quality | `src/data/quality.py`, `src/analytics/calibration.py`, `src/agent/pipeline.py::_confidence` | `tests/test_quality.py`, `tests/test_calibration.py`; E2 leave-one-site-out MAE |
| RQ3: a tool-grounded agent gives more specific, correct and traceable advice than AQI-only rules or a plain LLM | agent-answer: Four-part answer; Traceable numbers — llm-planner: Tool use; Number traceability check — health-recommendation: all | `src/agent/planner.py`, `src/knowledge/health.py` | `tests/test_agent.py`, `tests/test_llm_planner.py`; E4 40-question comparison (traceability, hallucinated numbers, action agreement) |

## Innovations and engineering claims

| Claim | Requirement (spec) | Implementation | Verification |
|---|---|---|---|
| Spatial pattern changes the advice (move away only for local or subregional events) | health-recommendation: Candidate actions depend on the spatial pattern | `src/knowledge/health.py::candidate_actions` | `tests/test_agent.py::test_shift_place_is_offered_only_for_local_or_subregional_events`; E4 |
| Sensitive groups are warned one level earlier | health-recommendation: Personal risk level; Ranking | `src/knowledge/health.py` | `tests/test_agent.py::test_sensitive_groups_are_warned_one_level_earlier`, `::test_ranking_follows_moenv_guidance` |
| Better time windows come from a leakage-free forecast | pm25-forecasting: Leakage-free short-term forecast; Forecast for the query location; Benchmarking | `src/analytics/forecast.py`, `src/agent/tools.py::forecast_trend` | `tests/test_forecast.py`; E1 (persistence, MLR, tuned tree ensembles) |
| Past events can be replayed exactly | data-acquisition: Point-in-time reads | `src/agent/tools.py` (`_read`, `get_station`) | `tests/test_agent.py::test_pipeline_end_to_end_on_synthetic_regional_event` |
| Data pipeline is secure | data-acquisition: Verified TLS and secret hygiene | `src/data/http.py`, `scripts/collect_scheduled.py::redact` | `tests/test_collect_scheduled.py` |
| The agent never invents numbers | llm-planner: Number traceability check; Deterministic fallback | `src/agent/planner.py` | `tests/test_llm_planner.py`; E4 hallucinated-number rate |
| Reviewers can try the system without setup | demo-site: all | `app/streamlit_app.py`, `data/sample/` | Local run check; public deployment at https://airsleuth.streamlit.app (2026-11-26: all three pages load and the Gemini planner answers) |

## Status

- 2026-10-27 (Proposal stage): `data-acquisition`, `data-quality`, `source-attribution`, `sensor-calibration`, `pm25-forecasting`, `health-recommendation`, `agent-answer` implemented and tested.
- 2026-11-24: `add-llm-planner` and `add-evaluation-suite` implemented, verified (52 offline tests; experiments E1–E4 in `experiments/results/`) and archived into `specs/llm-planner` and `specs/evaluation`.
- 2026-11-26: `add-demo-site` deployed to Streamlit Community Cloud (https://airsleuth.streamlit.app) and archived into `specs/demo-site`.
