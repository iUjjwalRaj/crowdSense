from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal
from uuid import uuid4


Severity = Literal["low", "medium", "high", "critical"]
AlertKind = Literal[
    "repeated_crowding",
    "sudden_crowding",
    "persistent_load",
    "underutilized_route",
    "historical_deviation",
]
RecommendationType = Literal[
    "deployment",
    "frequency",
    "scheduling",
    "alternative_route",
    "demand_redistribution",
]
ReviewState = Literal["pending", "approved", "rejected", "deferred"]


@dataclass
class Evidence:
    metric: str
    value: float
    threshold: float
    observed_at: str
    sample_count: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Recommendation:
    id: str
    alert_id: str
    affected_route: str
    affected_segment: str
    recommendation_type: RecommendationType
    description: str
    evidence: list[dict]
    severity: Severity
    confidence: float
    expected_benefit: str
    cost_if_available: str | None
    controller_approval: ReviewState
    execution_status: str
    outcome: str | None = None
    created_at: str = ""


@dataclass
class CrowdObservation:
    route_id: str
    segment_id: str
    occupancy_ratio: float
    historical_ratio: float | None
    timestamp: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _severity(ratio: float) -> Severity:
    if ratio >= 1.5:
        return "critical"
    if ratio >= 1.15:
        return "high"
    if ratio >= 0.70:
        return "medium"
    return "low"


def detect_alerts(observations: Iterable[dict]) -> list[dict]:
    """Detect crowd anomalies without assuming operational resources."""
    grouped: dict[tuple[str, str], list[CrowdObservation]] = {}
    for raw in observations:
        try:
            route_id = str(raw["route_id"])
            segment_id = str(raw["segment_id"])
            occupancy_ratio = float(raw["occupancy_ratio"])
            historical = raw.get("historical_ratio")
            historical_ratio = float(historical) if historical is not None else None
            timestamp = str(raw.get("timestamp") or _utc_now())
        except (KeyError, TypeError, ValueError):
            continue
        if occupancy_ratio < 0:
            continue
        grouped.setdefault((route_id, segment_id), []).append(
            CrowdObservation(route_id, segment_id, occupancy_ratio, historical_ratio, timestamp)
        )

    alerts: list[dict] = []
    for (route_id, segment_id), samples in grouped.items():
        samples = sorted(samples, key=lambda item: item.timestamp)
        ratios = [item.occupancy_ratio for item in samples]
        peak = max(ratios)

        if len(ratios) >= 3 and sum(ratio >= 1.15 for ratio in ratios[-3:]) >= 3:
            alerts.append({
                "id": str(uuid4()), "kind": "repeated_crowding",
                "affected_route": route_id, "affected_segment": segment_id,
                "severity": _severity(peak), "confidence": 0.9,
                "evidence": [Evidence("crowding_ratio", peak, 1.15, samples[-1].timestamp, len(ratios)).to_dict()],
            })
        if len(ratios) >= 2 and ratios[-1] - ratios[-2] >= 0.50:
            alerts.append({
                "id": str(uuid4()), "kind": "sudden_crowding",
                "affected_route": route_id, "affected_segment": segment_id,
                "severity": _severity(ratios[-1]), "confidence": 0.85,
                "evidence": [Evidence("ratio_change", ratios[-1] - ratios[-2], 0.50, samples[-1].timestamp, len(ratios)).to_dict()],
            })
        if len(ratios) >= 3 and all(ratio >= 0.70 for ratio in ratios[-3:]):
            alerts.append({
                "id": str(uuid4()), "kind": "persistent_load",
                "affected_route": route_id, "affected_segment": segment_id,
                "severity": _severity(peak), "confidence": 0.88,
                "evidence": [Evidence("persistent_crowding_ratio", sum(ratios[-3:]) / 3, 0.70, samples[-1].timestamp, 3).to_dict()],
            })
        if len(ratios) >= 3 and sum(ratios) / len(ratios) < 0.30:
            alerts.append({
                "id": str(uuid4()), "kind": "underutilized_route",
                "affected_route": route_id, "affected_segment": segment_id,
                "severity": "low", "confidence": 0.82,
                "evidence": [Evidence("mean_occupancy_ratio", sum(ratios) / len(ratios), 0.30, samples[-1].timestamp, len(ratios)).to_dict()],
            })
        historical = [item.historical_ratio for item in samples if item.historical_ratio is not None]
        if historical:
            baseline = sum(historical) / len(historical)
            deviation = abs(ratios[-1] - baseline)
            if deviation >= 0.25:
                alerts.append({
                    "id": str(uuid4()), "kind": "historical_deviation",
                    "affected_route": route_id, "affected_segment": segment_id,
                    "severity": _severity(ratios[-1]), "confidence": 0.80,
                    "evidence": [Evidence("historical_ratio_deviation", deviation, 0.25, samples[-1].timestamp, len(historical)).to_dict()],
                })
    return alerts


def generate_recommendations(alerts: Iterable[dict]) -> list[dict]:
    recommendations: list[dict] = []
    for alert in alerts:
        kind = alert["kind"]
        if kind in ("repeated_crowding", "sudden_crowding", "persistent_load"):
            recommendation_type: RecommendationType = "frequency"
            description = (
                "Review whether a controller-approved schedule or frequency change "
                "could reduce load. No reserve-bus or inter-route transfer is assumed."
            )
            benefit = "Potentially lower peak occupancy; benefit to be validated."
        elif kind == "underutilized_route":
            recommendation_type = "scheduling"
            description = "Review timetable utilization and demand redistribution options."
            benefit = "Potentially reduce low-load service waste; benefit to be validated."
        elif kind == "historical_deviation":
            recommendation_type = "alternative_route"
            description = "Review alternate-route guidance for demand redistribution."
            benefit = "Potentially shift demand and restore historical profile."
        else:
            recommendation_type = "demand_redistribution"
            description = "Review demand redistribution measures."
            benefit = "Benefit requires operational review."

        recommendation = Recommendation(
            id=str(uuid4()),
            alert_id=alert["id"],
            affected_route=alert["affected_route"],
            affected_segment=alert["affected_segment"],
            recommendation_type=recommendation_type,
            description=description,
            evidence=alert["evidence"],
            severity=alert["severity"],
            confidence=alert["confidence"],
            expected_benefit=benefit,
            cost_if_available=None,
            controller_approval="pending",
            execution_status="not_executable",
            created_at=_utc_now(),
        )
        recommendations.append(asdict(recommendation))
    return recommendations


AUDIT: list[dict] = []


def review_recommendation(
    recommendation: dict,
    action: str,
    controller: str,
    rationale: str = "",
) -> dict:
    if action not in ("approve", "reject", "defer"):
        raise ValueError("action must be approve, reject, or defer")
    controller = controller.strip()
    if not controller:
        raise ValueError("controller approval requires an identity")
    state = {"approve": "approved", "reject": "rejected", "defer": "deferred"}[action]
    updated = dict(recommendation)
    updated["controller_approval"] = state
    updated["execution_status"] = "manual_review_required" if state == "approved" else "not_executable"
    AUDIT.append({
        "timestamp": _utc_now(),
        "recommendation_id": updated["id"],
        "action": action,
        "controller": controller,
        "rationale": rationale,
    })
    return updated


def evaluate_outcome(recommendation: dict, outcome: str) -> dict:
    updated = dict(recommendation)
    outcome = outcome.strip()
    if not outcome:
        raise ValueError("outcome is required")
    updated["outcome"] = outcome
    updated["execution_status"] = "evaluated"
    return updated
