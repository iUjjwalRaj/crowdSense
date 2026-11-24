import { useMemo, useState } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import type { JourneyAlternative, CrowdLevel, MapStop } from "../types";
import { CROWD_COLORS, isValidCoordinate } from "../map";
import { developmentSegments, developmentStops, DEVELOPMENT_FIXTURE_NOTICE } from "../mapFixtures";

type Props = {
  journey?: JourneyAlternative;
};

export default function MapView({ journey }: Props) {
  const [selectedStopId, setSelectedStopId] = useState<string | null>("central");
  const [showStops, setShowStops] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);
  const [showWalking, setShowWalking] = useState(true);
  const [crowdFilter, setCrowdFilter] = useState<CrowdLevel | "all">("all");

  const validStops = useMemo(
    () => developmentStops.filter((stop) => isValidCoordinate(stop.lat, stop.lng) &&
      (crowdFilter === "all" || stop.crowd === crowdFilter)),
    [crowdFilter],
  );
  const selectedStop: MapStop | undefined =
    validStops.find((stop) => stop.id === selectedStopId) ||
    developmentStops.find((stop) => stop.id === selectedStopId);

  return (
    <section className="map-section" aria-labelledby="map-heading">
      <div className="map-toolbar">
        <div><p className="eyebrow">Live map</p><h2 id="map-heading">Route map</h2></div>
        <label>Filter
          <select value={crowdFilter} onChange={(event) => setCrowdFilter(event.target.value as CrowdLevel | "all")}>
            <option value="all">All crowdedness</option>
            <option value="available">Available</option>
            <option value="moderate">Moderate</option>
            <option value="crowded">Crowded</option>
            <option value="full">Full</option>
          </select>
        </label>
      </div>
      <div className="map-layout">
        <div className="map-canvas">
          <MapContainer center={[51.515, -0.122]} zoom={13} scrollWheelZoom minZoom={11} maxZoom={18}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {showRoutes && developmentSegments
              .filter((segment) => crowdFilter === "all" || segment.crowd === crowdFilter)
              .filter((segment) => showWalking || !segment.walking)
              .filter((segment) => {
                if (!journey) return !segment.walking;
                return segment.routeId === "D1" || segment.walking;
              })
              .filter((segment) => segment.positions.every(([lat, lng]) => isValidCoordinate(lat, lng)))
              .map((segment) => (
                <Polyline
                  key={segment.id}
                  positions={segment.positions}
                  pathOptions={{
                    color: segment.walking ? "#77b9d7" : CROWD_COLORS[segment.crowd],
                    weight: segment.walking ? 5 : 7,
                    opacity: 0.92,
                    dashArray: segment.walking ? "8 10" : undefined,
                  }}
                />
              ))}
            {showStops && validStops.map((stop) => (
              <CircleMarker
                key={stop.id}
                center={[stop.lat, stop.lng]}
                radius={selectedStopId === stop.id ? 11 : 8}
                pathOptions={{
                  color: "#ffffff",
                  weight: 2,
                  fillColor: CROWD_COLORS[stop.crowd],
                  fillOpacity: 1,
                }}
                eventHandlers={{ click: () => setSelectedStopId(stop.id) }}
                pane="markerPane"
              >
                <Tooltip direction="top" offset={[0, -8]}>{stop.name}</Tooltip>
              </CircleMarker>
            ))}
          </MapContainer>
          <div className="map-layers" aria-label="Map layers">
            <label><input type="checkbox" checked={showStops} onChange={(event) => setShowStops(event.target.checked)} /> Stops</label>
            <label><input type="checkbox" checked={showRoutes} onChange={(event) => setShowRoutes(event.target.checked)} /> Routes</label>
            <label><input type="checkbox" checked={showWalking} onChange={(event) => setShowWalking(event.target.checked)} /> Walking</label>
          </div>
          <div className="map-legend" aria-label="Crowdedness legend">
            {(["available", "moderate", "crowded", "full"] as CrowdLevel[]).map((level) => (
              <span key={level}><i style={{ background: CROWD_COLORS[level] }} />{level}</span>
            ))}
          </div>
        </div>

        {selectedStop && (
          <aside className="stop-panel" aria-label="Selected stop details">
            <p className="eyebrow">Selected stop</p>
            <h3>{selectedStop.name}</h3>
            <p>Routes: {selectedStop.routeIds.join(", ")}</p>
            {selectedStop.predictedOccupancy != null
              ? <p><strong>{selectedStop.predictedOccupancy}%</strong> predicted occupancy</p>
              : <p>Predicted occupancy unavailable</p>}
            <p><strong>{selectedStop.transfer ? "Transfer available" : "No transfer marked"}</strong></p>
            {journey && (
              <p className="journey-float">
                {journey.type} · {journey.estimated_minutes} min · {journey.transfers ?? "—"} transfers
              </p>
            )}
          </aside>
        )}
      </div>
      <p className="fixture-note">{DEVELOPMENT_FIXTURE_NOTICE}. Nearby boarding locations and walking links are examples, not guaranteed services.</p>
    </section>
  );
}
