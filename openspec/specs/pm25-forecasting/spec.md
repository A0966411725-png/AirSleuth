# pm25-forecasting Specification

## Purpose
Estimates PM2.5 1, 3 and 6 hours ahead so that the agent can recommend a better time window. Part of module ⑤.

## Requirements

### Requirement: Leakage-free short-term forecast

The system SHALL forecast the nearest national station's PM2.5 at 1, 3 and 6 hours ahead using only observations available at the query time, and SHALL train only on targets that were already observed before the query time.

#### Scenario: Replay of a past query

- **WHEN** a forecast is requested for 2026-10-23 11:30
- **THEN** the model is trained on station data whose target hour is not later than 10:00 on that day
- **AND** the forecast for each horizon is returned with the base hour used

#### Scenario: Not enough history

- **WHEN** fewer than 50 training rows are available for a horizon
- **THEN** that horizon is omitted
- **AND** if no horizon remains the tool reports that a forecast is not possible

### Requirement: Forecast for the query location

The system SHALL translate the station forecast to the query location by adding the forecast change (forecast − current station value) to the calibrated local concentration, never returning a negative value.

#### Scenario: Better time window

- **WHEN** the local concentration is 30 μg/m³ and the station is forecast to drop by 8 μg/m³ in 3 hours
- **THEN** the 3-hour estimate for the query location is 22 μg/m³
- **AND** the recommendation may suggest waiting 3 hours

### Requirement: Benchmarking against baselines

The system SHALL compare the forecasting model against persistence (no change) on a chronological train/test split and report MAE, RMSE and the hit rate of the 2025 AQI category for each horizon.

#### Scenario: Forecast experiment

- **WHEN** the forecasting experiment runs on the frozen station dataset
- **THEN** it reports the metrics for persistence and for every candidate model at 1, 3 and 6 hours
