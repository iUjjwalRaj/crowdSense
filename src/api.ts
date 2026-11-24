import type { JourneyPlanResponse, OperationsSnapshot, StationSearchResult, NetworkSummary } from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export async function searchStations(query: string = ""): Promise<StationSearchResult[]> {
  try {
    const response = await fetch(apiUrl(`/api/v1/stops/search?q=${encodeURIComponent(query)}`));
    if (!response.ok) return [];
    const data = await response.json();
    return Array.isArray(data.stops) ? data.stops : [];
  } catch {
    return [];
  }
}

export async function getNetworkSummary(): Promise<NetworkSummary | null> {
  try {
    const response = await fetch(apiUrl("/api/v1/network/summary"));
    if (!response.ok) return null;
    const data = await response.json();
    if (!data || typeof data.stops_count !== "number") return null;
    return data as NetworkSummary;
  } catch {
    return null;
  }
}

export async function planJourney(
  origin: string,
  destination: string,
  comfortWeight: number,
  departureTime: string,
  signal?: AbortSignal,
  preference: "fastest" | "balanced" | "comfort" = "balanced",
): Promise<JourneyPlanResponse> {
  const response = await fetch(apiUrl("/api/v1/journey/plan"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      origin,
      destination,
      comfort_weight: comfortWeight,
      departure_time: departureTime || undefined,
      preference,
    }),
    signal,
  });
  if (!response.ok) {
    throw new Error(`Journey planning failed (${response.status})`);
  }
  const data = (await response.json()) as JourneyPlanResponse;
  if (!Array.isArray(data.alternatives)) {
    throw new Error("Journey planning returned an invalid response");
  }
  return data;
}

export async function getOperationsSnapshot(): Promise<OperationsSnapshot> {
  const response = await fetch(apiUrl("/api/v1/occ/occupancy/corridor"));
  if (!response.ok) {
    throw new Error(`Operations snapshot unavailable (${response.status})`);
  }
  return (await response.json()) as OperationsSnapshot;
}

export async function getRecommendations(): Promise<Record<string, unknown>[]> {
  const response = await fetch(apiUrl("/api/v1/recommendations"));
  if (!response.ok) {
    throw new Error(`Recommendations unavailable (${response.status})`);
  }
  const data = (await response.json()) as { recommendations?: Record<string, unknown>[] };
  return Array.isArray(data.recommendations) ? data.recommendations : [];
}

export async function reviewRecommendation(
  recommendationId: string,
  action: "approve" | "reject" | "defer",
  controller: string,
  rationale = "",
): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl(`/api/v1/recommendations/${encodeURIComponent(recommendationId)}/${action}`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, controller, rationale }),
  });
  if (!response.ok) {
    throw new Error(`Recommendation review failed (${response.status})`);
  }
  return (await response.json()) as Record<string, unknown>;
}
