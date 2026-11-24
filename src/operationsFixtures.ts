import type { Advisory, OperationsSnapshot } from "./types";

// Synthetic development data only. Never present these values as live fleet data.
export const syntheticOperationsSnapshot: OperationsSnapshot = {
  source: "estimated",
  timestamp: "Development fixture",
  active_routes: 12,
  active_vehicles: 38,
  on_time_percentage: 86,
  corridors: [
    { id: "D1", name: "Central - University", crowd: "moderate", occupancy: 68 },
    { id: "D2", name: "Central - Riverside", crowd: "full", occupancy: 96 },
  ],
};

export const syntheticAdvisories: Advisory[] = [
  {
    id: "DEV-1",
    title: "Review Riverside crowding",
    description: "Synthetic occupancy estimate exceeds the fixture crush threshold.",
    severity: "high",
    dataSource: "estimated",
  },
];
