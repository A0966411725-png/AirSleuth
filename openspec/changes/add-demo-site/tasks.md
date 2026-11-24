# Tasks: add-demo-site

## 1. Sample data
- [ ] 1.1 `scripts/make_demo_sample.py`: extract the three recorded events into `data/sample/events/` — test: `tests/test_demo_sample.py` (tools return the same source type on the extract as on the full store)

## 2. App
- [ ] 2.1 `app/streamlit_app.py`: chat page with answer and trace
- [ ] 2.2 Event-replay page with map, indicators and per-group answers
- [ ] 2.3 Data page with sources, coverage and limitations
- [ ] 2.4 Local check: `streamlit run app/streamlit_app.py` loads all pages without errors

## 3. Deployment
- [ ] 3.1 README section "Demo" with the public URL and deployment steps (owner deploys on Streamlit Community Cloud and adds `GEMINI_API_KEY` in Secrets)
