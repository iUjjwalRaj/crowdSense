# Crowd Data Requirements

## Supported current inputs

The occupancy module accepts CSV or Parquet ETM-style tabular data and recognizes:

- Boarding: `boardings`, `boarding`, `ons`, `on`, `passengers_in`, `entries`
- Alighting: `alightings`, `alighting`, `offs`, `off`, `passengers_out`, `exits`
- Trip: `trip_id`, `vehicle_trip_id`, `run_id`, `trip`
- Route: `route_id`, `route`, `line_id`
- Stop: `stop_id`, `stop`
- Sequence: `stop_sequence`, `sequence`, `stop_index`, `stop_order`

Caller-provided seated and total capacity are required for occupancy profiling.

## Required real-time inputs

A future crowd provider should supply or verify:

- Route ID and direction
- Trip/vehicle ID
- Boarding stop and destination/alighting stop
- Timestamp and timezone
- Boarding count
- Alighting count or a clearly documented estimate status
- Seated and total vehicle capacity
- Vehicle GPS latitude/longitude when vehicle position is relevant
- Data provider and source record ID
- Observation freshness

## Observation versus estimation

- Observed passenger counts are `OBSERVED`.
- Missing alighting counts inferred by the current decay heuristic are `ESTIMATED`.
- Historical or model-generated values are `PREDICTED`.
- Explicit test-only values are `SIMULATED`.
- Unsupported or missing values are `UNKNOWN`.

UNKNOWN is never displayed as a measured crowd level.

## Alighting behavior

If observed alighting is absent or invalid, the current heuristic distributes onboard
passengers using downstream boarding attraction and exponential distance decay. This is
not a substitute for measured alighting data. The result must remain marked `ESTIMATED`.

Passenger conservation is checked for each trip:

- onboard starts at zero
- onboard is incremented by valid boardings
- observed or estimated alightings cannot exceed onboard
- negative or non-numeric counts are removed

## Missing provider behavior

There is currently no live crowd provider and no journey-segment occupancy provider.
Journey segments therefore return `data_status: unavailable`, `data_source: unknown`,
and null occupancy/tier/confidence fields.
