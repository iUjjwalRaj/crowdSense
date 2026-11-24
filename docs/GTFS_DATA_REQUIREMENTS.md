# GTFS Data Requirements

## Accepted sources

Set `CROWDSENSE_GTFS_PATH` to:

- a directory containing GTFS text files, or
- a `.zip` archive containing those files.

## Required files

The current loader expects these relationships:

- `stops.txt`: `stop_id`, `stop_name`, `stop_lat`, `stop_lon`
- `routes.txt`: `route_id`, `route_short_name`, optional `route_long_name`, `route_type`
- `trips.txt`: `trip_id`, `route_id`, `service_id`, optional `trip_headsign`
- `stop_times.txt`: `trip_id`, `arrival_time`, `departure_time`, `stop_id`, `stop_sequence`
- `calendar.txt` or `calendar_dates.txt`: weekday service or date exceptions

## Current support

- GTFS static directory and ZIP feeds.
- Stop IDs and unique stop names.
- Origin/destination coordinate matching to a stop within the walking limit.
- Consecutive stop-times on each trip.
- Weekly calendars with `start_date` and `end_date`.
- `calendar_dates.txt` additions/removals.
- Walking links only between stops with valid coordinates.
- Transfer limits and walking-distance limits.

## Current limitations

- No agency timezone lookup or timezone conversion is implemented.
- Feed departures are compared as local wall-clock seconds.
- GTFS times past midnight are represented numerically but service-day rollover is not
  fully modeled.
- No `agency.txt`, `frequencies.txt`, `shapes.txt`, `fare_attributes.txt`,
  `fare_rules.txt`, `transfers.txt`, `pathways.txt`, or GTFS-Realtime support.
- No database persistence or automatic feed synchronization.
- The feed is reloaded from the configured path per network construction.

## Directory structure

```text
gtfs/
├── agency.txt                 # Optional/currently not parsed
├── calendar.txt
├── calendar_dates.txt         # Optional
├── routes.txt
├── stop_times.txt
├── stops.txt
└── trips.txt
```

## Coordinate and validation rules

Stop coordinates must be finite and within latitude `-90..90` and longitude `-180..180`.
Rows with missing or invalid coordinates are retained as stop records without coordinates;
routing and walking links exclude those stops. Route and trip relationship IDs must match.
