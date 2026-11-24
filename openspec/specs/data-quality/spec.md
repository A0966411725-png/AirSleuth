# data-quality Specification

## Purpose
Flags unreliable micro-sensor readings before any spatial analysis, so that faulty or implausible values cannot drive a conclusion. Corresponds to the quality-check step of module ④.

## Requirements

### Requirement: Row-level quality flags

The system SHALL assign each micro-sensor row exactly one quality flag, choosing the first matching rule in this order: `pm25_missing`, `pm25_negative`, `pm25_extreme`, `stuck`, `rh_invalid`, otherwise `ok`.

#### Scenario: Negative concentration

- **WHEN** a row reports PM2.5 below 0 μg/m³
- **THEN** the row is flagged `pm25_negative` and excluded from spatial analysis

#### Scenario: Frozen sensor

- **WHEN** a sensor reports the same PM2.5 value for a long consecutive run
- **THEN** those rows are flagged `stuck` and excluded from spatial analysis

#### Scenario: Invalid humidity only

- **WHEN** a row has a valid PM2.5 value but relative humidity outside (0, 100]
- **THEN** the row is flagged `rh_invalid`
- **AND** its PM2.5 value is still used, while humidity for calibration comes from the nearest weather station

### Requirement: Quality summary for the agent

The system SHALL report the usable ratio, the invalid-humidity ratio and the excluded ratio of the data used for an answer, so that the answer can state how trustworthy the evidence is.

#### Scenario: Quality summary in the tool trace

- **WHEN** the agent runs the quality check on the micro-sensor data around a query location
- **THEN** the trace records `usable_ratio`, `rh_invalid_ratio` and `excluded_ratio` rounded to three decimals
