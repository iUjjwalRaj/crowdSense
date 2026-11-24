export type JourneyAlternative = {
  type: "fastest" | "balanced" | "comfort";
  stops: string[];
  estimated_minutes: number;
  crowd_cost?: number;
  fare?: number;
  walking_minutes?: number;
  transfers?: number;
  comfort_score?: number;
  uncertainty?: "low" | "medium" | "high";
  data_source?: "live" | "predicted" | "historical";
  segments?: JourneySegment[];
  trade_off?: string;
};

export type JourneySegment = {
  boarding_stop_id: string;
  destination_stop_id: string;
  route_id?: string | null;
  trip_id?: string | null;
  mode: "transit" | "walk";
  departure_seconds: number;
  arrival_seconds: number;
  waiting_minutes: number;
  travel_minutes: number;
  walking_minutes: number;
  transfer: boolean;
  expected_occupancy?: number | null;
  crowdedness_tier?: string | null;
  crowdedness_index?: number | null;
  prediction_confidence?: number | null;
  data_source: "unknown" | "observed" | "estimated" | "predicted" | "simulated";
  data_status: "available" | "unavailable" | "stale";
  data_freshness?: string | null;
};

export type JourneyPlanResponse = {
  origin?: string;
  destination?: string;
  status?: "ok" | "no_route" | "invalid_origin" | "invalid_destination" | "data_unavailable";
  detail?: string;
  alternatives: JourneyAlternative[];
  data_source?: "live" | "predicted" | "historical";
};

export type JourneyPreference = "balanced" | "fastest" | "comfort";

export type CrowdLevel = "available" | "moderate" | "crowded" | "full";

export type MapStop = {
  id: string;
  name: string;
  lat: number;
  lng: number;
  crowd: CrowdLevel;
  predictedOccupancy?: number;
  routeIds: string[];
  transfer?: boolean;
};

export type MapSegment = {
  id: string;
  routeId: string;
  positions: [number, number][];
  crowd: CrowdLevel;
  walking?: boolean;
};

export type OperationsSnapshot = {
  source: "live" | "estimated";
  timestamp?: string;
  active_routes?: number;
  active_vehicles?: number;
  on_time_percentage?: number;
  corridors?: Array<{
    id: string;
    name: string;
    crowd: CrowdLevel;
    occupancy?: number;
  }>;
};

export type Advisory = {
  id: string;
  title: string;
  description: string;
  severity: "low" | "medium" | "high";
  dataSource: "live" | "estimated" | "historical";
  affectedRoute?: string;
  affectedSegment?: string;
  evidence?: Array<{ metric: string; value: number; threshold: number }>;
  confidence?: number;
  expectedBenefit?: string;
  costIfAvailable?: string;
  status?: "pending" | "approved" | "rejected" | "deferred";
  executionStatus?: string;
};
