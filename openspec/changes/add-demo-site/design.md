# Design: add-demo-site

## Decisions
1. **Streamlit**, as taught in the course (L7B, L15C), deployed on Streamlit Community Cloud from `main`.
2. **Sample extracts, not raw data.** `scripts/make_demo_sample.py` cuts each recorded event to the sensors within 15 km and the 7 hours before the event time, plus the station and weather files the tools need. This is enough for every tool, because the tools only read point-in-time windows.
3. **Same tools, different data root.** The tools already take a `root` argument, so the app passes the sample folder as the data root. The analysis code is the same in the demo and in the experiments.
4. **Map.** `st.map` or `pydeck` scatter layer coloured by PM2.5; no external map key.
5. **Rate limits.** One LLM answer per question; the deterministic answer is computed first and shown if the LLM is unavailable.

## Risks
- Cold start on the free hosting tier takes tens of seconds; the README states this.
- The live micro-sensor API is down until the certificate is renewed; the live page is labelled accordingly.
