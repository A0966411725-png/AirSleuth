# demo-site Specification

## Purpose
Lets reviewers try the agent in a browser without installing Python or holding API keys: a public Streamlit site (https://airsleuth.streamlit.app) answers questions with an expandable tool trace and replays recorded events from a versioned data extract, so it does not depend on live micro-sensor data. Corresponds to modules ① and ⑧.

## Requirements

### Requirement: Browser demo without local setup

The system SHALL provide a web demo that runs from the public repository with only the packages in `requirements.txt` and the sample data in `data/sample/`.

#### Scenario: Fresh deployment

- **WHEN** the repository is deployed without `data/raw/` and without an API key
- **THEN** the event-replay page works with the sample data
- **AND** the chat page answers structured questions with the deterministic pipeline and says the LLM is not enabled

### Requirement: Recorded event replay

The system SHALL let a visitor choose a recorded event and a user group and SHALL show the sensor map, the spatial indicators and the agent's answer for that event time.

#### Scenario: Kaohsiung regional event

- **WHEN** a visitor opens the 2026-10-23 11:30 Kaohsiung event and selects 孩童
- **THEN** the page shows the sensors within 15 km coloured by PM2.5, the source type 區域型 and the ranked actions
- **AND** the actions do not include moving to another place

### Requirement: Transparent tool trace

The system SHALL show, for every answer, the sequence of tool calls with their arguments and results.

#### Scenario: Expanding the trace

- **WHEN** a visitor expands "工具呼叫紀錄" under an answer
- **THEN** each tool call is listed in order with its arguments and returned values

### Requirement: Secret handling

The system SHALL read the Gemini key only from the environment or the hosting platform's secret store and SHALL never display it.

#### Scenario: Key configured on the platform

- **WHEN** the key is set in Streamlit Secrets
- **THEN** the chat page uses the LLM planner
- **AND** the key does not appear in the page, the trace or the logs
