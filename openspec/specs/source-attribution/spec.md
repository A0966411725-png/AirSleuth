# source-attribution Specification

## Purpose
Classifies the spatial pattern of a PM2.5 rise around a location (Algorithm 2), so that the agent can tell whether moving elsewhere would help or whether the whole region is affected. Corresponds to the core innovation in module ⑤.

## Requirements

### Requirement: Spatial indicators at the query time

The system SHALL compute, at the latest time not after the query time, the regional background B (median of usable sensors within 15 km), the local level L (median within the local radius, default 2 km), the local excess E = L − B, and the coherence C (share of regional sensors that are rising), plus C_sub within 8 km and C_ring in the 8–15 km ring.

#### Scenario: Indicators are reported with the answer

- **WHEN** source attribution runs for a query point with enough sensors
- **THEN** the result contains B, L, E, C, C_sub, C_ring, the number of local sensors and the timestamp used

### Requirement: Definition of a rising sensor

The system SHALL count a sensor as rising only when its current value is more than 50% above its own median of the previous 6 hours AND at least 5 μg/m³ above that median.

#### Scenario: Clean-air fluctuation

- **WHEN** a sensor's baseline is 4 μg/m³ and its current value is 7 μg/m³
- **THEN** the sensor is not counted as rising, because the rise is below 5 μg/m³

### Requirement: Source type classification

The system SHALL return exactly one of `regional`, `subregional`, `local`, `mixed`, `suspected_sensor_fault`, `no_clear_event` or `insufficient_data`, checking the regional, subregional, local, and mixed rules in that order and returning `no_clear_event` when none applies.

#### Scenario: Region-wide rise

- **WHEN** C ≥ 0.6 and E < max(5, 0.3·B)
- **THEN** the type is `regional`

#### Scenario: Cluster within 8 km

- **WHEN** at least 5 sensors lie within 8 km, C < 0.6, C_sub ≥ 0.3 and C_ring < 0.3
- **THEN** the type is `subregional`

#### Scenario: Local source confirmed by neighbours

- **WHEN** E ≥ max(10, 0.5·B), C < 0.3 and at least 2 nearby sensors are also elevated
- **THEN** the type is `local`

#### Scenario: Single outlier sensor

- **WHEN** E ≥ max(10, 0.5·B) and C < 0.3 but fewer than 2 nearby sensors are elevated
- **THEN** the type is `suspected_sensor_fault`, not `local`

#### Scenario: Regional rise with a local source on top

- **WHEN** C ≥ 0.6 and E ≥ max(10, 0.5·B)
- **THEN** the type is `mixed`

#### Scenario: Missing data

- **WHEN** B or C cannot be computed
- **THEN** the type is `insufficient_data`

### Requirement: Adaptive local radius

The system SHALL double the local radius (2 → 4 → 8 km, at most twice) when fewer than 5 usable sensors lie within it, and SHALL record the radius actually used.

#### Scenario: Sparse suburban area

- **WHEN** only 3 usable sensors lie within 2 km but 7 lie within 4 km
- **THEN** source attribution is computed with a 4 km local radius
- **AND** the answer reports "4 km" as the local radius
