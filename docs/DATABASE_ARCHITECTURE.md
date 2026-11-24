# Database Architecture

## Technology

CrowdSense uses SQLAlchemy 2.x and supports SQLite or a SQLAlchemy-compatible relational
database. SQLite is the default so a local deployment can persist data without an external
database.

Set `CROWDSENSE_DATABASE_URL`, for example:

- SQLite: `sqlite:///./crowdsense.db`
- PostgreSQL: `postgresql+psycopg://user:password@host:5432/crowdsense`

Set `CROWDSENSE_DATA_DIR` to change the default `.crowdsense/` SQLite directory.

## Tables

- `agencies`: GTFS agency metadata
- `routes`: route identities and names
- `stops`: stop identities, names and coordinates
- `trips`: route/service/trip relationships
- `stop_times`: trip, stop, sequence and arrival/departure seconds
- `service_calendars`: weekday ranges and exceptions
- `provider_configs`: provider setup and last sync
- `gtfs_imports`: import status/history and counts
- `passenger_observations`: boarding/alighting passenger observations
- `occupancy_estimates`: observed or estimated segment occupancy
- `crowd_predictions`: model/provider predictions
- `alerts`: evidence-backed detected alerts
- `recommendations`: controller-review recommendations
- `audit_logs`: immutable append-only application audit records

## Relationships and constraints

Trips reference routes, stop times reference trips and stops, and recommendations reference
alerts. Route, stop and trip IDs are unique. Stop-time trip/sequence pairs are unique.
Indexes cover route, stop, trip, timestamp and review-state lookup fields.

The application uses transactions for repository writes and rollbacks on exceptions.

## Current persistence behavior

GTFS network objects are loaded for routing, but route/stop/trip import history and alerts,
recommendations and audit entries can also persist to SQL storage. Existing in-memory
alert/recommendation dictionaries remain compatibility state and should not be considered
the authoritative audit store.
