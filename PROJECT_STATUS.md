# CrowdSense Project Status

## Journey planning

Implemented:
- `POST /api/v1/journey/plan`
- GTFS directory/zip loading through `CROWDSENSE_GTFS_PATH`
- Real Indian public transit GTFS datasets integrated and verified:
  - Delhi Metro Rail Corporation (DMRC) official open data (Delhi NCR, Noida, Ghaziabad, Gurgaon)
  - Indian Railways national network (8,550 stations nationwide, including Bihar, Uttar Pradesh, and Delhi NCR)
  - Unified multimodal feed (`data/gtfs/india_multimodal.zip`) combining rail and metro with real walking transfers
- SQLAlchemy batch-upsert and duplicate-handling GTFS ingestion into SQLite / PostgreSQL
- Fast spatial walking edge generation and admissible A* search heuristic
- Stop-id, canonical station alias (`Hapur` -> `HPU`, `Noida Sector 62` -> `237`, `Patna` -> `PNBE`, `Delhi` -> `NDLS`), stop-name and coordinate-origin matching
- Time-dependent scheduled connections with real timetables
- Walking connections between valid-coordinate stops (e.g. Anand Vihar Terminal <-> Anand Vihar Metro ~280m)
- Transfer limits and walking-distance limits
- Fastest, balanced and comfort route alternatives
- Explicit segment-level crowd data status
- Legacy `POST /api/v1/journeys/search` alias
- Commuter loading/error/no-route/results/detail UI integration

Verified:
- 49 backend pytest tests (40 original regression + 9 Indian GTFS, persistence, duplicate handling, and real journey tests)
- Database persistence tests cover fresh schema, batch upsert, duplicate import idempotency, restart and recovery
- 11 frontend Vitest tests
- Production frontend build (`tsc -b && vite build`)
- 8 Playwright commuter/API/no-route/operations/live journey tests
- Real journey test: Hapur to Noida Sector 62 (Indian Railways train to Ghaziabad/Anand Vihar, walking transfer to Anand Vihar Metro, Blue Line to Noida Sector 62)
- Real journey test: Patna to Delhi (Indian Railways direct intercity train)

Database Records Verified in SQLite (`.crowdsense/crowdsense.db`):
- Agencies: 2 (`DMRC` Delhi Metro Rail Corporation, `IR` Indian Railways)
- Routes: 10,630
- Stops: 8,812 (including Bihar stations like PNBE, UP stations like HPU, Delhi NCR stations)
- Trips: 16,032
- Stop Times: 329,822
- Calendars: 1,999
- GTFS Imports: 57

Unsupported Regions & Remaining Limitations:
- State Road Transport Undertaking (SRTU) local buses in Bihar (BSRTC / Patna City Bus Service): No publicly available open GTFS schedule feed published by government agencies; reliance on private apps (Chalo). Patna Metro remains under construction.
- State Road Transport buses in Uttar Pradesh (UPSRTC): No official open GTFS feed released; schedules exist only in proprietary web portals/PDFs.
- Real-time GTFS-RT Vehicle Positions: Offline static GTFS schedules are imported; live dynamic crowd-prediction feeds remain unconfigured.

Synthetic fixtures are used only in automated tests and are labeled as such. No schedules, stops, fares or live occupancy values are invented in production responses.

## Final execution report

- Backend: 49 tests passed; 0 failed.
- Frontend: 11 Vitest tests passed; 0 failed.
- Frontend production build: passed.
- Playwright: 8 tests passed; 0 failed.
- GTFS production data: verified and active (`data/gtfs/india_multimodal.zip`).
- SQLite persistence: verified (8,812 stops, 10,630 routes, 16,032 trips, 329,822 stop times).
- Live crowd-prediction provider: unconfigured (fallback to synthetic test fixtures for test harness only).
