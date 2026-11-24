# agent-answer Specification

## Purpose
Defines what every AirSleuth answer contains and guarantees, whether a fixed pipeline or an LLM planner produced it (Algorithm 1). Corresponds to modules ③ and ⑧.

## Requirements

### Requirement: Four-part answer

The system SHALL answer with a conclusion, the reasons with evidence, ranked actions, and a confidence level with its reasons, followed by the data sources and the query time.

#### Scenario: Regional event answer

- **WHEN** a parent asks about letting a child exercise near 前金 at 2026-10-23 11:30
- **THEN** the answer states the estimated PM2.5, the AQI category, the source type and the first-ranked action
- **AND** lists the evidence (B, L, E, C, nearest station, weather, forecast) and the confidence

### Requirement: Traceable numbers

The system SHALL take every number in an answer from a logged tool result, and SHALL keep a trace of every tool call with its arguments and outputs.

#### Scenario: Inspecting the trace

- **WHEN** a reviewer opens the trace of an answer
- **THEN** each step shows the tool name, the arguments and the returned values
- **AND** every concentration quoted in the answer can be found in one of those results

### Requirement: Confidence reflects evidence quality

The system SHALL start from high confidence and lower it one level for each of: fewer than 5 local sensors, humidity of at least 85%, an uncertain source type (`mixed`, `suspected_sensor_fault`, `insufficient_data`), and data older than 30 minutes.

#### Scenario: Humid morning with few sensors

- **WHEN** only 3 local sensors are available and RH is 90%
- **THEN** the confidence is "低"
- **AND** the answer adds a conservative advice line for sensitive groups

### Requirement: Graceful degradation

The system SHALL fall back to the nearest national station when micro-sensor data are insufficient, and SHALL say plainly that it cannot judge when neither source has data.

#### Scenario: No micro-sensor data

- **WHEN** no micro-sensor data exist around the query time
- **THEN** the answer is based on the nearest station and the confidence is "低"

#### Scenario: No data at all

- **WHEN** neither micro-sensor nor station data exist for the query time
- **THEN** the answer says that no usable air-quality data are available and suggests another time or place
