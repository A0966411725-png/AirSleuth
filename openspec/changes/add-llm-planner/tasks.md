# Tasks: add-llm-planner

## 1. LLM client
- [ ] 1.1 `src/agent/llm.py`: Gemini REST client, model fallback on 429/503, key from env only — test: `tests/test_llm_planner.py::test_model_fallback`
- [ ] 1.2 Fake LLM for offline tests (scripted function calls and texts)

## 2. Planner
- [ ] 2.1 `src/agent/geo.py`: district names of 臺中市 and 高雄市 to coordinates — test: `test_resolve_place`
- [ ] 2.2 `src/agent/planner.py`: ReAct loop with planner tools, 12-call limit, trace — tests: `test_tool_loop`, `test_unknown_tool_rejected`
- [ ] 2.3 Clarification when the place is missing or unsupported — tests: `test_asks_for_place`, `test_unsupported_city`
- [ ] 2.4 Number traceability check with one rewrite, then fallback — test: `test_hallucinated_number_falls_back`
- [ ] 2.5 Deterministic fallback when no key — test: `test_no_key_uses_pipeline`

## 3. Interfaces
- [ ] 3.1 CLI: `python -m src.agent.ask "問題" --time "2026-10-23 11:30"`
- [ ] 3.2 Used by the demo site (change `add-demo-site`) and the evaluation (change `add-evaluation-suite`)
