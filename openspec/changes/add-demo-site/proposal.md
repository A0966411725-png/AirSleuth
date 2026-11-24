# Proposal: add-demo-site

## Why
The final deliverable requires "GitHub with demo site": reviewers must be able to try the agent in a browser without installing Python or holding API keys. The micro-sensor API has been unreachable since its certificate expired on 2026-11-21, so the demo cannot depend on live micro-sensor data.

## What changes
- A Streamlit app (`app/streamlit_app.py`) with three pages:
  1. **Ask AirSleuth**: chat in Traditional Chinese; shows the four-part answer and an expandable tool trace.
  2. **Event replay**: pick a recorded event (Kaohsiung 10/23 regional, Taichung 10/19 coastal subregional, a clear day) and see the sensor map, the B/L/E/C indicators and the answer for different user groups.
  3. **About the data**: data sources, collection coverage, limitations.
- Replay data come from a small, versioned extract in `data/sample/` (only the sensors within 15 km of each event, ±7 hours), so the deployed site does not need `data/raw/`.
- Deployment on Streamlit Community Cloud from the public GitHub repo; the Gemini key is stored in the platform's Secrets by the repository owner.

## Capabilities
- New: `demo-site`

## Impact
- Code: `app/`, `scripts/make_demo_sample.py`, `requirements.txt` (streamlit, pydeck via streamlit)
- Data: `data/sample/events/*.csv.gz` (a few MB)
