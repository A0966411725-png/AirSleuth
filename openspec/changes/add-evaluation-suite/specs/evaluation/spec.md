## ADDED Requirements

### Requirement: Reproducible experiments

The system SHALL run each experiment from a single command on the frozen dataset and SHALL write its tables and figures to `experiments/results/`, so that rerunning the command reproduces the reported numbers.

#### Scenario: Rerunning an experiment

- **WHEN** a developer runs `python -m experiments.e1_forecast` twice on the same data
- **THEN** both runs write identical metric tables (fixed random seeds)

### Requirement: Forecast comparison

The system SHALL compare persistence, multiple linear regression and at least one tuned tree ensemble at 1, 3 and 6 hours ahead using MAE, RMSE and the AQI-category hit rate, with hyper-parameters tuned only on the training period.

#### Scenario: Tuning without test leakage

- **WHEN** Optuna tunes a tree ensemble
- **THEN** its objective uses a validation split taken from the training period
- **AND** the test period is evaluated once with the selected parameters

### Requirement: Ground-truth evaluation of source attribution

The system SHALL evaluate the source-type classifier on semi-synthetic cases with known labels and SHALL report a confusion matrix, per-class recall and macro-F1 for AirSleuth and for each baseline.

#### Scenario: Injected local plume

- **WHEN** a plume of +15 μg/m³ is added to the sensors within 1.5 km of a chosen point on a clean background hour
- **THEN** the expected label is `local`
- **AND** the case counts toward the `local` recall of every method

#### Scenario: Injected faulty sensor

- **WHEN** a single sensor is raised by +40 μg/m³ and no neighbour changes
- **THEN** the expected label is `suspected_sensor_fault`

### Requirement: End-to-end agent comparison

The system SHALL score every agent configuration on the same 40 questions for number traceability, hallucinated numbers, agreement of the first-ranked action with the expected behaviour, correct clarification, and correct refusal of unsupported places, and SHALL report the model name and version used.

#### Scenario: LLM without tools

- **WHEN** the no-tool baseline answers a question about a specific time and place
- **THEN** every concentration it states is checked against the recorded data
- **AND** concentrations that do not match the data count as hallucinated numbers
