import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import type { JourneyAlternative, CrowdLevel, MapStop, MapSegment } from "../types";
import { CROWD_COLORS, isValidCoordinate } from "../map";
import { developmentSegments, developmentStops, DEVELOPMENT_FIXTURE_NOTICE } from "../mapFixtures";

type Props = {
  journey?: JourneyAlternative;
  title?: string;
};

function MapCenterController({ center, zoom }: { center: [number, number]; zoom: number }) {
  try {
    const map = useMap();
    useEffect(() => {
      if (map && typeof map.setView === "function") {
        map.setView(center, zoom);
      }
    }, [center, zoom, map]);
  } catch {
    // Graceful fallback for test environments where useMap hook is mocked
  }
  return null;
}

export default function MapView({ journey, title = "Route map" }: Props) {
  const [selectedStopId, setSelectedStopId] = useState<string | null>("central");
  const [showStops, setShowStops] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);
  const [showWalking, setShowWalking] = useState(true);
  const [crowdFilter, setCrowdFilter] = useState<CrowdLevel | "all">("all");

  // Extract real geographic stops and segments if the journey contains coordinates
  const { realStops, realSegments, hasRealCoordinates, routeCenter } = useMemo(() => {
    if (!journey || !journey.segments || journey.segments.length === 0) {
      return { realStops: [] as MapStop[], realSegments: [] as MapSegment[], hasRealCoordinates: false, routeCenter: [51.515, -0.122] as [number, number] };
    }

    const stopsMap = new Map<string, MapStop>();
    const segmentsList: MapSegment[] = [];
    const validCoords: [number, number][] = [];

    journey.segments.forEach((seg, idx) => {
      const bLat = seg.boarding_lat;
      const bLng = seg.boarding_lng;
      const dLat = seg.destination_lat;
      const dLng = seg.destination_lng;

      if (bLat != null && bLng != null && isValidCoordinate(bLat, bLng)) {
        validCoords.push([bLat, bLng]);
        if (!stopsMap.has(seg.boarding_stop_id)) {
          stopsMap.set(seg.boarding_stop_id, {
            id: seg.boarding_stop_id,
            name: seg.boarding_stop_name || seg.boarding_stop_id,
            lat: bLat,
            lng: bLng,
            crowd: seg.crowdedness_tier === "high" ? "crowded" : seg.crowdedness_tier === "extreme" ? "full" : "available",
            predictedOccupancy: seg.expected_occupancy ? Math.round(seg.expected_occupancy * 100) : undefined,
            routeIds: seg.route_id ? [seg.route_id] : [],
            transfer: seg.transfer,
          });
        }
      }

      if (dLat != null && dLng != null && isValidCoordinate(dLat, dLng)) {
        validCoords.push([dLat, dLng]);
        if (!stopsMap.has(seg.destination_stop_id)) {
          stopsMap.set(seg.destination_stop_id, {
            id: seg.destination_stop_id,
            name: seg.destination_stop_name || seg.destination_stop_id,
            lat: dLat,
            lng: dLng,
            crowd: seg.crowdedness_tier === "high" ? "crowded" : seg.crowdedness_tier === "extreme" ? "full" : "available",
            predictedOccupancy: seg.expected_occupancy ? Math.round(seg.expected_occupancy * 100) : undefined,
            routeIds: seg.route_id ? [seg.route_id] : [],
            transfer: seg.transfer,
          });
        }
      }

      if (bLat != null && bLng != null && dLat != null && dLng != null &&
          isValidCoordinate(bLat, bLng) && isValidCoordinate(dLat, dLng)) {
        segmentsList.push({
          id: `seg-${idx}-${seg.mode}`,
          routeId: seg.route_id || (seg.mode === "walk" ? "walk" : "transit"),
          positions: [[bLat, bLng], [dLat, dLng]],
          crowd: seg.crowdedness_tier === "high" ? "crowded" : "available",
          walking: seg.mode === "walk",
        });
      }
    });

    const hasReal = validCoords.length > 0;
    let center: [number, number] = [51.515, -0.122];
    if (hasReal) {
      const avgLat = validCoords.reduce((sum, c) => sum + c[0], 0) / validCoords.length;
      const avgLng = validCoords.reduce((sum, c) => sum + c[1], 0) / validCoords.length;
      center = [avgLat, avgLng];
    }

    return {
      realStops: Array.from(stopsMap.values()),
      realSegments: segmentsList,
      hasRealCoordinates: hasReal,
      routeCenter: center,
    };
  }, [journey]);

  // When real journey coordinates exist, auto-select the first real stop
  useEffect(() => {
    if (hasRealCoordinates && realStops.length > 0) {
      setSelectedStopId(realStops[0].id);
    }
  }, [hasRealCoordinates, realStops]);

  // Combined stops and segments for rendering
  const activeStops = useMemo(() => {
    if (hasRealCoordinates) {
      return realStops.filter((stop) => crowdFilter === "all" || stop.crowd === crowdFilter);
    }
    return developmentStops.filter(
      (stop) => isValidCoordinate(stop.lat, stop.lng) && (crowdFilter === "all" || stop.crowd === crowdFilter)
    );
  }, [hasRealCoordinates, realStops, crowdFilter]);

  const activeSegments = useMemo(() => {
    if (hasRealCoordinates) {
      return realSegments
        .filter((segment) => crowdFilter === "all" || segment.crowd === crowdFilter)
        .filter((segment) => showWalking || !segment.walking);
    }
    return developmentSegments
      .filter((segment) => crowdFilter === "all" || segment.crowd === crowdFilter)
      .filter((segment) => showWalking || !segment.walking)
      .filter((segment) => {
        if (!journey) return !segment.walking;
        return segment.routeId === "D1" || segment.walking;
      })
      .filter((segment) => segment.positions.every(([lat, lng]) => isValidCoordinate(lat, lng)));
  }, [hasRealCoordinates, realSegments, crowdFilter, showWalking, journey]);

  const selectedStop: MapStop | undefined =
    activeStops.find((stop) => stop.id === selectedStopId) ||
    developmentStops.find((stop) => stop.id === selectedStopId) ||
    activeStops[0];

  return (
    <section className="map-section" aria-labelledby="map-heading">
      <div className="map-toolbar">
        <div>
          <p className="eyebrow">Live map</p>
          <h2 id="map-heading">{title}</h2>
        </div>
        <div className="map-controls-group">
          {hasRealCoordinates && (
            <span className="live-route-tag">
              Route Plotted ({realStops.length} stations)
            </span>
          )}
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
      </div>
      <div className="map-layout">
        <div className="map-canvas">
          <MapContainer center={routeCenter} zoom={hasRealCoordinates ? 11 : 13} scrollWheelZoom minZoom={4} maxZoom={18}>
            <MapCenterController center={routeCenter} zoom={hasRealCoordinates ? 11 : 13} />
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {showRoutes && activeSegments.map((segment) => (
              <Polyline
                key={segment.id}
                positions={segment.positions}
                pathOptions={{
                  color: segment.walking ? "#77b9d7" : CROWD_COLORS[segment.crowd] || "#45d4a1",
                  weight: segment.walking ? 5 : 7,
                  opacity: 0.92,
                  dashArray: segment.walking ? "8 10" : undefined,
                }}
              />
            ))}
            {showStops && activeStops.map((stop) => (
              <CircleMarker
                key={stop.id}
                center={[stop.lat, stop.lng]}
                radius={selectedStopId === stop.id ? 11 : 8}
                pathOptions={{
                  color: "#ffffff",
                  weight: 2,
                  fillColor: CROWD_COLORS[stop.crowd] || "#45d4a1",
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
            {selectedStop.routeIds.length > 0 && <p>Routes: {selectedStop.routeIds.join(", ")}</p>}
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
      <p className="fixture-note">{DEVELOPMENT_FIXTURE_NOTICE}</p>
    </section>
  );
}
