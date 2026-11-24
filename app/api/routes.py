from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
import os

from app.alerts import (
    AUDIT,
    detect_alerts,
    evaluate_outcome,
    generate_recommendations,
    review_recommendation,
)
from app.gtfs import get_gtfs_network
from app.journey import plan_journey
from app.providers import GTFS_HEALTH, CROWD_HEALTH, stale_status
from app.database import database_health
from app.repositories import list_persisted_audit, record_audit


router = APIRouter(prefix="/api/v1")
_alerts: dict[str, dict] = {}
_recommendations: dict[str, dict] = {}


class ObservationRequest(BaseModel):
    observations: list[dict]


class ReviewRequest(BaseModel):
    action: str = Field(pattern="^(approve|reject|defer)$")
    controller: str = Field(min_length=1)
    rationale: str = ""


class OutcomeRequest(BaseModel):
    outcome: str = Field(min_length=1)


class JourneyPlanRequest(BaseModel):
    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    departure_time: datetime | None = None
    max_transfers: int = Field(default=3, ge=0, le=10)
    max_walking_distance: float = Field(default=1500, ge=0, le=50000)
    comfort_weight: float = Field(default=0.5, ge=0, le=1)
    preference: str = Field(default="balanced", pattern="^(fastest|balanced|comfort)$")
    origin_lat: float | None = Field(default=None, ge=-90, le=90)
    origin_lng: float | None = Field(default=None, ge=-180, le=180)
    destination_lat: float | None = Field(default=None, ge=-90, le=90)
    destination_lng: float | None = Field(default=None, ge=-180, le=180)

    def coordinate_pair_is_complete(self) -> bool:
        return (
            (self.origin_lat is None) == (self.origin_lng is None)
            and (self.destination_lat is None) == (self.destination_lng is None)
        )


@router.post("/journey/plan")
def journey_plan(payload: JourneyPlanRequest):
    if not payload.coordinate_pair_is_complete():
        raise HTTPException(status_code=422, detail="Origin and destination coordinates must be supplied as latitude/longitude pairs")
    network = get_gtfs_network()
    if network is None:
        return {
            "status": "data_unavailable",
            "origin": payload.origin,
            "destination": payload.destination,
            "departure_time": payload.departure_time.isoformat() if payload.departure_time else None,
            "alternatives": [],
            "detail": "GTFS transport data is not configured.",
        }
    departure = payload.departure_time or datetime.now()
    preference = payload.preference
    if preference == "comfort":
        preference = "comfort"
    elif preference == "fastest":
        preference = "fastest"
    else:
        preference = "balanced"
    try:
        result = plan_journey(
            network,
            payload.origin,
            payload.destination,
            departure=departure,
            preference=preference,
            max_transfers=payload.max_transfers,
            max_walking_meters=payload.max_walking_distance,
            origin_lat=payload.origin_lat,
            origin_lng=payload.origin_lng,
            destination_lat=payload.destination_lat,
            destination_lng=payload.destination_lng,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail="Invalid journey or transport data") from error
    return result


@router.post("/journeys/search")
def legacy_journey_search(payload: JourneyPlanRequest):
    """Backward-compatible alias for existing journey search clients."""
    return journey_plan(payload)


@router.get("/health/readiness")
def readiness():
    gtfs = GTFS_HEALTH.as_dict()
    gtfs["freshness_status"] = stale_status(GTFS_HEALTH.last_successful_sync, 7 * 24 * 3600)
    crowd = CROWD_HEALTH.as_dict()
    crowd["freshness_status"] = stale_status(CROWD_HEALTH.last_successful_sync, 15 * 60)
    blocking_errors = []
    if not gtfs["configured"]:
        blocking_errors.append("GTFS static provider is not configured")
    blocking_errors.extend(gtfs["blocking_errors"])
    if not crowd["configured"]:
        blocking_errors.append("Crowd/occupancy provider is not configured")
    blocking_errors.extend(crowd["blocking_errors"])
    return {
        "ready": not blocking_errors,
        "database": database_health(),
        "gtfs": gtfs,
        "crowd": crowd,
        "prediction_service": {
            "configured": False,
            "last_successful_update": None,
            "valid_observation_count": CROWD_HEALTH.valid_record_count,
            "freshness_status": crowd["freshness_status"],
            "blocking_errors": ["Prediction provider is not configured"],
        },
        "blocking_errors": blocking_errors,
    }


@router.get("/occ/occupancy/corridor")
def occupancy_corridor():
    return {
        "source": "unknown",
        "timestamp": None,
        "active_routes": None,
        "active_vehicles": None,
        "on_time_percentage": None,
        "corridors": [],
        "blocking_errors": ["OCC occupancy/corridor provider is not configured"],
    }


@router.post("/alerts/evaluate")
def evaluate_alerts(payload: ObservationRequest):
    alerts = detect_alerts(payload.observations)
    for alert in alerts:
        _alerts[alert["id"]] = alert
    recommendations = generate_recommendations(alerts)
    for recommendation in recommendations:
        _recommendations[recommendation["id"]] = recommendation
    return {"alerts": alerts, "recommendations": recommendations}


@router.get("/alerts")
def list_alerts():
    return {"alerts": list(_alerts.values())}


@router.get("/alerts/overcrowded")
def overcrowded_alerts():
    return {"alerts": [alert for alert in _alerts.values() if alert["kind"] != "underutilized_route"]}


@router.get("/recommendations")
def list_recommendations():
    return {"recommendations": list(_recommendations.values())}


@router.post("/recommendations/{recommendation_id}/review")
def review(recommendation_id: str, payload: ReviewRequest):
    recommendation = _recommendations.get(recommendation_id)
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    try:
        updated = review_recommendation(
            recommendation, payload.action, payload.controller, payload.rationale
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    _recommendations[recommendation_id] = updated
    record_audit(recommendation_id, payload.action, payload.controller, payload.rationale)
    return {"recommendation": updated}


@router.post("/recommendations/{recommendation_id}/approve")
def approve(recommendation_id: str, payload: ReviewRequest):
    payload.action = "approve"
    return review(recommendation_id, payload)


@router.post("/recommendations/{recommendation_id}/reject")
def reject(recommendation_id: str, payload: ReviewRequest):
    payload.action = "reject"
    return review(recommendation_id, payload)


@router.post("/recommendations/{recommendation_id}/defer")
def defer(recommendation_id: str, payload: ReviewRequest):
    payload.action = "defer"
    return review(recommendation_id, payload)


@router.get("/recommendations/{recommendation_id}/execution")
def execution_status(recommendation_id: str):
    recommendation = _recommendations.get(recommendation_id)
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return {
        "recommendation_id": recommendation_id,
        "execution_status": recommendation["execution_status"],
        "outcome": recommendation.get("outcome"),
        "real_changes_executed": False,
    }


@router.post("/recommendations/{recommendation_id}/outcome")
def outcome(recommendation_id: str, payload: OutcomeRequest):
    recommendation = _recommendations.get(recommendation_id)
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    updated = evaluate_outcome(recommendation, payload.outcome)
    _recommendations[recommendation_id] = updated
    return {"recommendation": updated}


@router.get("/audit")
def audit_log():
    try:
        persisted = list_persisted_audit()
        if persisted:
            return {"audit": persisted}
    except Exception:
        pass
    return {"audit": AUDIT}


@router.get("/stops/search")
def search_stops(q: str = "", limit: int = 12):
    network = get_gtfs_network()
    if not network or not network.stops:
        return {"stops": []}
    q_clean = q.strip().lower()
    if not q_clean:
        popular_aliases = [
            ("Rajiv Chowk (DMRC Blue/Yellow)", "207"),
            ("Kashmere Gate (DMRC Red/Yellow/Violet)", "8"),
            ("Noida Sector 62 (DMRC Blue)", "237"),
            ("Anand Vihar Metro (DMRC Blue/Pink)", "74"),
            ("Anand Vihar Terminal (IR)", "ANVT"),
            ("New Delhi Railway Station (IR / Airport Exp)", "NDLS"),
            ("Hapur Junction (IR)", "HPU"),
            ("Ghaziabad Junction (IR)", "GZB"),
            ("Patna Junction (IR)", "PNBE"),
        ]
        results = []
        for display_name, sid in popular_aliases:
            if sid in network.stops:
                st = network.stops[sid]
                results.append({
                    "id": sid,
                    "name": display_name,
                    "code": sid,
                    "lat": st["lat"],
                    "lng": st["lng"],
                })
        return {"stops": results}

    matches = []
    seen = set()
    for sid, st in network.stops.items():
        name = st.get("name", "")
        if not name:
            continue
        if q_clean in name.lower() or q_clean in sid.lower():
            if sid not in seen:
                seen.add(sid)
                matches.append({
                    "id": sid,
                    "name": name,
                    "code": sid,
                    "lat": st.get("lat"),
                    "lng": st.get("lng"),
                })
                if len(matches) >= limit:
                    break
    return {"stops": matches}


@router.get("/network/summary")
def network_summary():
    network = get_gtfs_network()
    if not network:
        return {
            "status": "unconfigured",
            "agencies": [],
            "stops_count": 0,
            "routes_count": 0,
            "trips_count": 0,
        }
    return {
        "status": "ready",
        "timezone": network.timezone_name,
        "stops_count": len(network.stops),
        "routes_count": len(network.routes),
        "trips_count": len(network.trips),
        "agencies": [
            {"id": a.get("agency_id"), "name": a.get("agency_name")}
            for a in getattr(network, "agencies", [])
        ],
        "coverage": "Delhi NCR (DMRC) & Indian Railways National Network",
    }
