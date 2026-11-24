from app.alerts import (
    AUDIT,
    detect_alerts,
    evaluate_outcome,
    generate_recommendations,
    review_recommendation,
)


def observation(route="R1", segment="S1", ratio=1.0, historical=None, minute=0):
    return {
        "route_id": route,
        "segment_id": segment,
        "occupancy_ratio": ratio,
        "historical_ratio": historical,
        "timestamp": f"2026-11-24T03:{minute:02d}:00Z",
    }


def test_repeated_and_persistent_crowding_detection():
    observations = [
        observation(ratio=1.2, minute=1),
        observation(ratio=1.3, minute=2),
        observation(ratio=1.4, minute=3),
    ]
    alerts = detect_alerts(observations)
    kinds = {alert["kind"] for alert in alerts}
    assert "repeated_crowding" in kinds
    assert "persistent_load" in kinds


def test_sudden_crowding_detection():
    alerts = detect_alerts([observation(ratio=0.4, minute=1), observation(ratio=1.0, minute=2)])
    assert any(alert["kind"] == "sudden_crowding" for alert in alerts)


def test_underutilized_route_detection():
    alerts = detect_alerts([observation(ratio=0.20), observation(ratio=0.25, minute=1), observation(ratio=0.18, minute=2)])
    assert any(alert["kind"] == "underutilized_route" for alert in alerts)


def test_historical_profile_deviation_detection():
    alerts = detect_alerts([observation(ratio=1.20, historical=0.70, minute=1)])
    assert any(alert["kind"] == "historical_deviation" for alert in alerts)


def test_recommendations_require_evidence_and_scope():
    alerts = detect_alerts([observation(ratio=1.2), observation(ratio=1.3, minute=1), observation(ratio=1.4, minute=2)])
    recommendations = generate_recommendations(alerts)
    assert recommendations
    for recommendation in recommendations:
        assert recommendation["affected_route"] == "R1"
        assert recommendation["affected_segment"] == "S1"
        assert recommendation["evidence"]
        assert recommendation["severity"] in ("low", "medium", "high", "critical")
        assert 0 <= recommendation["confidence"] <= 1
        assert recommendation["expected_benefit"]
        assert recommendation["controller_approval"] == "pending"
        assert recommendation["execution_status"] == "not_executable"
        assert "reserve-bus" in recommendation["description"].lower() or recommendation["recommendation_type"] != "deployment"


def test_controller_review_audit_and_outcome_workflow():
    AUDIT.clear()
    recommendation = generate_recommendations(detect_alerts([
        observation(ratio=1.2), observation(ratio=1.3, minute=1), observation(ratio=1.4, minute=2)
    ]))[0]
    approved = review_recommendation(recommendation, "approve", "Duty Controller", "Validated evidence")
    assert approved["controller_approval"] == "approved"
    assert approved["execution_status"] == "manual_review_required"
    assert AUDIT[-1]["controller"] == "Duty Controller"
    evaluated = evaluate_outcome(approved, "Peak occupancy decreased 8 percent")
    assert evaluated["outcome"] == "Peak occupancy decreased 8 percent"
    assert evaluated["execution_status"] == "evaluated"


def test_invalid_rows_are_cleaned_and_empty_result_is_safe():
    assert detect_alerts([{"route_id": "R1"}, None, {"route_id": "R1", "segment_id": "S1", "occupancy_ratio": -1}]) == []
