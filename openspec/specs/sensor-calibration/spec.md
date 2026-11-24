# sensor-calibration Specification

## Purpose
Converts low-cost sensor readings toward reference-grade values with city-specific coefficients, because sensors over- or under-estimate differently by city and humidity. Part of module ⑤.

## Requirements

### Requirement: City-specific linear calibration with humidity

The system SHALL calibrate a micro-sensor PM2.5 value as `a + b·sensor + c·RH` using coefficients fitted for the same city against co-located national stations, with RH taken from the nearest weather station, and SHALL never return a negative concentration.

#### Scenario: Kaohsiung reading

- **WHEN** a Kaohsiung sensor median of 15.0 μg/m³ is calibrated with RH 70%
- **THEN** the system applies the 高雄市 coefficients and returns a value rounded to 0.1 μg/m³
- **AND** the trace notes which city's coefficients and which humidity were used

#### Scenario: No coefficients or no humidity

- **WHEN** the city has no fitted coefficients or the humidity is missing
- **THEN** the raw reading is returned unchanged
- **AND** the result is marked as not calibrated, which lowers the answer's confidence

### Requirement: Out-of-site validation

The system SHALL evaluate calibration with leave-one-site-out cross-validation and report MAE before and after calibration for each city.

#### Scenario: Calibration report

- **WHEN** the calibration experiment runs on the frozen dataset
- **THEN** it reports, per city, the number of station-hours, MAE without calibration, with linear calibration and with linear plus humidity calibration
