# health-recommendation Specification

## Purpose
Turns concentrations, source type and forecast into ranked, concrete actions for a specific person and activity (Algorithm 3), grounded in the Ministry of Environment's 2025 AQI guidance. Corresponds to modules ⑥ and ⑦.

## Requirements

### Requirement: Personal risk level

The system SHALL map PM2.5 to the 2025 AQI category and SHALL warn sensitive groups (children, elderly, asthma, heart disease) one category earlier than the general public.

#### Scenario: Child at a moderate level

- **WHEN** the local PM2.5 is 20 μg/m³
- **THEN** the general public is at the "普通" level
- **AND** a child is treated one level higher

### Requirement: Candidate actions depend on the spatial pattern

The system SHALL offer "move to another place" only when the source type is `local` or `subregional` and a cleaner background value is available, and SHALL never offer it for `regional` events.

#### Scenario: Regional event

- **WHEN** the source type is `regional`
- **THEN** no candidate action suggests moving to another place

#### Scenario: Subregional event

- **WHEN** the source type is `subregional` and the calibrated 15 km background is lower than the local value
- **THEN** "move more than 8 km away" is a candidate action with the background value as its expected concentration

### Requirement: Ranking by benefit minus exposure risk

The system SHALL rank candidate actions by activity benefit minus a level-dependent risk weight times inhaled dose, and SHALL return the top three.

#### Scenario: General public at a moderate level

- **WHEN** a general-public user plans to exercise at 20 μg/m³
- **THEN** "proceed as planned" ranks first

#### Scenario: Child at the same level

- **WHEN** a child plans to exercise at 20 μg/m³
- **THEN** "lower the intensity" ranks above "proceed as planned"

### Requirement: Evidence for every rule

The system SHALL attach the source IDs registered in `research/sources.md` to each domain rule it applies.

#### Scenario: Rules in the answer

- **WHEN** the agent applies the sensitive-group rule
- **THEN** the retrieved rule text includes its source IDs
