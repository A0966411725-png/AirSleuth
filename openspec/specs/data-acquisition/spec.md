# data-acquisition Specification

## Purpose
Keeps a local, reproducible store of micro-sensor, national-station and weather observations for the cities AirSleuth serves, so that every analysis can be replayed for any past query time. Corresponds to architecture module ④.

## Requirements

### Requirement: Scheduled hourly collection

The system SHALL collect micro-sensor, national-station and weather observations for each configured city every hour and append them to daily files under `data/raw/<source>/<city>/YYYY-MM-DD.csv.gz`, merging duplicate keys instead of creating duplicate rows.

#### Scenario: Normal hourly run

- **WHEN** the scheduled collector runs for 臺中市 and 高雄市
- **THEN** each source writes or updates the daily file for the observation date in Taiwan time
- **AND** a row with the same sensor or station key and timestamp appears only once

#### Scenario: One source fails

- **WHEN** one source raises an error during a run
- **THEN** the error is logged with the source and city
- **AND** the remaining sources are still collected in the same run

### Requirement: Verified TLS and secret hygiene

The system SHALL connect to government hosts with full TLS certificate verification and SHALL keep API keys out of logs and version control.

#### Scenario: Server certificate is invalid

- **WHEN** a host presents an expired or untrusted certificate
- **THEN** the request fails and the failure is logged
- **AND** no data is fetched from that host by disabling verification

#### Scenario: Error message contains a key

- **WHEN** a failed request URL contains `api_key=` or `Authorization=`
- **THEN** the logged message shows `***` in place of the key value

### Requirement: Station history backfill

The system SHALL be able to backfill national-station hourly values for a requested number of past days, because the station dataset can be queried retrospectively while the micro-sensor API keeps only the last few hours.

#### Scenario: Filling a collection gap

- **WHEN** an operator runs `python -m scripts.backfill_moenv --days 8`
- **THEN** station hours missing from the local store for those days are added
- **AND** existing rows are not duplicated

### Requirement: Point-in-time reads

The system SHALL let analysis tools read only observations that existed at or before a given query time.

#### Scenario: Replaying a past event

- **WHEN** a tool is asked about 2026-10-23 11:30 Taiwan time
- **THEN** it reads micro-sensor data up to 11:30 only
- **AND** it uses the national-station value of the last complete hour (10:00 for an 11:30 query)
