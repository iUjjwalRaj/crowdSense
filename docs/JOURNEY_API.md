# Journey Planning API

## Endpoint

`POST /api/v1/journey/plan`

```json
{
  "origin": "Stop name or stop_id",
  "destination": "Stop name or stop_id",
  "departure_time": "2026-11-24T08:30:00",
  "preference": "balanced",
  "comfort_weight": 0.5,
  "max_transfers": 3,
  "max_walking_distance": 1500,
  "origin_lat": 51.5074,
  "origin_lng": -0.1278,
  "destination_lat": 51.5192,
  "destination_lng": -0.1269
}
```

`origin` and `destination` may also be `"latitude,longitude"` strings. Coordinates only
resolve to a GTFS stop within `max_walking_distance`.

## Response

The response includes `status`, origin/destination resolution, and multiple alternatives
when the configured GTFS network contains a valid path. Each segment identifies the
boarding/destination stops and, for transit segments, the GTFS route and trip.

Crowd fields are explicit. In the absence of a connected crowd-prediction source,
`data_status` is `unavailable`, `data_source` is `unknown`, and occupancy/tier fields
are `null`. The API never converts missing data into a crowd estimate.

When GTFS is not configured, the response is:

```json
{
  "status": "data_unavailable",
  "alternatives": [],
  "detail": "GTFS transport data is not configured."
}
```

`POST /api/v1/journeys/search` remains as a backward-compatible alias.

## GTFS assumptions

- `stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`, and calendar files are read
  from a directory or zip.
- Scheduled connections use GTFS arrival/departure times and service calendars.
- Walking connections are created only between stops with valid coordinates within the
  requested walking limit.
- Fares are not invented.
- A no-route result means no scheduled or valid walking path was found.
