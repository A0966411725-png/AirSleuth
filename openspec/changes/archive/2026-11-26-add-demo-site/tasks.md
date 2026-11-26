# Tasks: add-demo-site

## 1. Sample data
- [x] 1.1 `scripts/make_demo_sample.py`: extract the three recorded events into `data/sample/demo/` — test: `tests/test_demo_sample.py` (tools return the same source type on the extract as on the full store)

## 2. App
- [x] 2.1 `app/streamlit_app.py`: chat page with answer and trace
- [x] 2.2 Event-replay page with map, indicators and per-group answers
- [x] 2.3 Data page with sources, coverage and limitations
- [x] 2.4 Local check: `streamlit run app/streamlit_app.py` loads all pages without errors

## 3. Deployment
- [x] 3.1 README section "Demo" with the public URL (https://airsleuth.streamlit.app, deployed 2026-11-26; all three pages load and the Gemini planner answers) and deployment steps (owner deploys on Streamlit Community Cloud and adds `GEMINI_API_KEY` in Secrets)
