# CrowdSense Data Quality Report

## Implemented checks

- GTFS required relationship IDs are filtered before edge creation.
- Invalid stop coordinates are rejected and excluded from coordinate/walking routing.
- Free-form and numeric coordinates are checked by geographic bounds and finiteness.
- Coordinate origin/destination fields must be supplied as complete pairs.
- Duplicate ETM rows are removed.
- Negative/non-numeric boarding values are cleaned.
- Alighting cannot exceed onboard passengers.
- Missing alightings are labeled estimated rather than observed.
- Calendar start/end dates are enforced.
- Calendar-date exceptions override weekly calendars.
- Provider health exposes configuration, record count, sync time and blocking errors.
- Readiness distinguishes GTFS, crowd and prediction providers.
- Stale status is available for timestamped provider data.
- Journey missing-crowd fields remain unavailable/unknown.

## Remaining quality gaps

- Agency timezone and service-day rollover are not implemented.
- GTFS frequency-based trips and shape/route geometry are not implemented.
- Passenger count fields do not yet have a provider-backed journey integration.
- Vehicle GPS, real-time ETA and real-time occupancy providers are not connected.
- Duplicate trip/stop sequences and inconsistent stop-time ordering need stronger import
  rejection/reporting.
- Stale thresholds are not configured by an authority-specific policy.
- The current project has no database or persistent audit provider.

## Security and trust boundary

The health endpoint reports configuration and freshness only. Synthetic UI fixtures are
development-only and must not be represented as provider output.
