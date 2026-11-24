# Design: add-llm-planner

## Context
- Tools and their JSON schema already exist (`src/agent/tools.py`, `src/agent/schema.py`) and are covered by offline tests.
- The user chose the Gemini API free tier (DECISIONS D-09). On 2026-11-24 `gemini-3.5-flash-lite` answered a function-calling probe correctly in 1.6 s, while the larger Flash models returned HTTP 503 (high demand) and `gemini-4-*` returned HTTP 429 (not in the free tier).

## Decisions
1. **REST instead of an SDK.** The client calls `generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` with `requests`, which the project already uses. The key goes in the `x-goog-api-key` header, never in the URL, so it cannot leak into logs.
2. **Model list with fallback.** Default order: `gemini-3.5-flash-lite`, `gemini-3.8-flash`, `gemini-3.5-flash` (same question on 2026-11-24: 7.6 s vs. 238 s, both correct). Timeouts and connection errors also move to the next model. It can be overridden with `GEMINI_MODELS`. Experiments pin one model and record `modelVersion` for reproducibility.
3. **Planner-facing tools differ from data tools.** The LLM never handles raw DataFrames. Planner tools are coarse and JSON-safe:
   - `resolve_place(text)`: district name or coordinates to city and coordinates (67 districts of 臺中市 and 高雄市)
   - `analyze_air_quality(city, lat, lon, place, group, activity, hours)`: runs Algorithm 1 steps 5–19 deterministically at the query time and returns the structured facts (concentration, source type, indicators, station, weather, forecast, ranked actions, confidence) plus the deterministic reference answer
   - `retrieve_knowledge(group, activity, src_type)`: domain rules with source IDs, for "why" questions

   This keeps every number deterministic and limits the LLM's role to understanding, planning and wording. The eight data tools of the prototype run inside `analyze_air_quality` and remain in its trace.
4. **Traceability check.** A regex extracts numbers followed by units from the final text. Each must match a numeric value in the tool results, after rounding to 0 or 1 decimal. Percentages also match ratios (0.38 ↔ 38%).
5. **Time.** The planner gets the query time in the system prompt. In demo replay mode this is the event time; in live mode it is the current Taiwan time.

## Risks
- Free-tier quota or overload during the demo: the deterministic fallback keeps the site usable.
- LLM wording may soften warnings: the system prompt forbids changing the ranking or the risk level, and the first-ranked action text is checked against the deterministic result.
