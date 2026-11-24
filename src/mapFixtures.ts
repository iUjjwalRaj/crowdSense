import type { MapSegment, MapStop } from "./types";

// Development-only geography. These coordinates are not live operational data.
export const DEVELOPMENT_FIXTURE_NOTICE =
  "Development fixture — not live transport data";

export const developmentStops: MapStop[] = [
  { id: "central", name: "Central Square", lat: 51.5074, lng: -0.1278, crowd: "available", predictedOccupancy: 42, routeIds: ["D1", "D3"], transfer: true },
  { id: "market", name: "Market Street", lat: 51.5131, lng: -0.1181, crowd: "moderate", predictedOccupancy: 68, routeIds: ["D1"] },
  { id: "museum", name: "Museum Junction", lat: 51.5192, lng: -0.1269, crowd: "crowded", predictedOccupancy: 84, routeIds: ["D1", "D2"], transfer: true },
  { id: "university", name: "University Gate", lat: 51.5256, lng: -0.1329, crowd: "available", predictedOccupancy: 38, routeIds: ["D1"] },
  { id: "riverside", name: "Riverside", lat: 51.5105, lng: -0.1046, crowd: "full", predictedOccupancy: 96, routeIds: ["D2"] },
];

export const developmentSegments: MapSegment[] = [
  { id: "d1-a", routeId: "D1", positions: [[51.5074, -0.1278], [51.5131, -0.1181]], crowd: "available" },
  { id: "d1-b", routeId: "D1", positions: [[51.5131, -0.1181], [51.5192, -0.1269]], crowd: "moderate" },
  { id: "d1-c", routeId: "D1", positions: [[51.5192, -0.1269], [51.5256, -0.1329]], crowd: "crowded" },
  { id: "d2-a", routeId: "D2", positions: [[51.5074, -0.1278], [51.5105, -0.1046]], crowd: "full" },
  { id: "walk-a", routeId: "walk", positions: [[51.5131, -0.1181], [51.5192, -0.1269]], crowd: "available", walking: true },
];
