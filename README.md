# CrowdSense

CrowdSense is a mobile-first journey planning interface backed by the CrowdSense APIs.

## Frontend

```sh
npm install
npm run dev
```

The UI calls `POST /api/v1/journey/plan` with `origin`, `destination`, `comfort_weight`, and
optional `departure_time`. Stop lookups and live operator schedules must be supplied by the
backend; the UI intentionally does not fabricate results or schedules.

Occupancy and arrival information is explicitly labeled by the API's `data_source`
(`live`, `predicted`, or `historical`) and is presented as an estimate rather than a guarantee.
Preferences and recent/saved journeys are stored only in browser local storage.

## Transportation map

The Leaflet/OpenStreetMap view uses clearly labeled development fixtures until stop and
route APIs provide validated coordinates. Invalid coordinates are excluded, crowdedness
uses green/yellow/red/purple segment levels, and walking links are dashed. Predicted
occupancy is shown only as an estimate and never as a guarantee.

## Operations Command Center

The desktop operations view is API-first at `GET /api/v1/occ/occupancy/corridor`.
Missing API data is marked unavailable; synthetic development fixtures are labeled estimated
and are never shown as live fleet data. Advisory actions only create a local audit entry
after authorization and confirmation; they do not publish or change transport operations.

## Tests

```sh
npm test
npm run build
npm run test:e2e
```

## Journey planning

`POST /api/v1/journey/plan` routes against GTFS data configured with
`CROWDSENSE_GTFS_PATH`. The value may be a GTFS directory or zip file. The endpoint
returns scheduled alternatives only and marks crowd data unavailable unless a separate
prediction source is connected.
