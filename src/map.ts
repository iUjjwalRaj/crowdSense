import type { CrowdLevel } from "./types";

export const CROWD_COLORS: Record<CrowdLevel, string> = {
  available: "#39d98a",
  moderate: "#f5c84c",
  crowded: "#ff6464",
  full: "#ad72f4",
};

export function isValidCoordinate(lat: number, lng: number): boolean {
  return Number.isFinite(lat) && Number.isFinite(lng) &&
    lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
}
