# Proposal: add-llm-planner

## Why
The Proposal-stage prototype calls the eight tools in a fixed order and fills a template. It cannot understand a free-form question, ask for missing information, or explain the result in natural language. The Proposal promised that module ③ would be an LLM planner that decides which tools to call (ReAct with function calling), while all numbers stay in deterministic tools.

## What changes
- An LLM planner (Gemini API, free tier) receives the user's question in Traditional Chinese, the tool schema from `src/agent/schema.py`, and a system prompt with the domain rules.
- The planner extracts place, time, user group, activity and duration; when the place is missing or outside the supported cities it asks or explains instead of guessing.
- The planner calls tools through function calling; each call and result is logged in the same trace format as the prototype.
- Before the answer is returned, a traceability check verifies that every number in the text appears in a tool result; a failed check triggers one rewrite, then the deterministic answer.
- Without an API key, or when every model is unavailable, the system uses the existing deterministic pipeline and says so.

## Capabilities
- New: `llm-planner`
- Modified: none (the `agent-answer` guarantees apply to both modes)

## Impact
- Code: `src/agent/llm.py` (Gemini REST client with model fallback), `src/agent/planner.py` (ReAct loop and checks), `src/agent/geo.py` (district names to coordinates)
- Config: `GEMINI_API_KEY`, optional `GEMINI_MODELS` in `.env` or the hosting platform's secrets
- Tests: offline tests with a scripted fake LLM; no test calls the real API
