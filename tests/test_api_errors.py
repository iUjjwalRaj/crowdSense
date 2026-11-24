from fastapi.testclient import TestClient
import pytest

import app.api.routes as routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_alert_evaluate_and_review_contract():
    response = client.post("/api/v1/alerts/evaluate", json={"observations": [
        {"route_id": "R1", "segment_id": "S1", "occupancy_ratio": 1.2, "timestamp": "2026-11-24T03:01:00Z"},
        {"route_id": "R1", "segment_id": "S1", "occupancy_ratio": 1.3, "timestamp": "2026-11-24T03:02:00Z"},
        {"route_id": "R1", "segment_id": "S1", "occupancy_ratio": 1.4, "timestamp": "2026-11-24T03:03:00Z"},
    ]})
    assert response.status_code == 200
    body = response.json()
    assert body["alerts"]
    assert body["recommendations"]
    recommendation_id = body["recommendations"][0]["id"]
    reviewed = client.post(
        f"/api/v1/recommendations/{recommendation_id}/approve",
        json={"action": "approve", "controller": "Duty Controller", "rationale": "Evidence reviewed"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["recommendation"]["controller_approval"] == "approved"
    execution = client.get(f"/api/v1/recommendations/{recommendation_id}/execution")
    assert execution.status_code == 200
    assert execution.json()["real_changes_executed"] is False


def test_patna_delhi_missing_gtfs(monkeypatch):
    monkeypatch.delenv("CROWDSENSE_GTFS_PATH", raising=False)
    response = client.post("/api/v1/journey/plan", json={
        "origin": "Patna",
        "destination": "Delhi",
        "departure_time": "2026-11-24T12:30",
        "preference": "fastest",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "data_unavailable"
    assert body["alternatives"] == []
    assert "not configured" in body["detail"]


def test_missing_origin_and_destination_are_validation_errors():
    missing_origin = client.post("/api/v1/journey/plan", json={
        "origin": "",
        "destination": "Delhi",
        "preference": "fastest",
    })
    invalid_time = client.post("/api/v1/journey/plan", json={
        "origin": "Patna",
        "destination": "Delhi",
        "departure_time": "not-a-datetime",
        "preference": "fastest",
    })
    assert missing_origin.status_code == 422
    assert invalid_time.status_code == 422


def test_empty_transport_network(monkeypatch):
    class EmptyNetwork:
        timezone = None
    monkeypatch.setattr(routes, "get_gtfs_network", lambda: EmptyNetwork())
    response = client.post("/api/v1/journey/plan", json={
        "origin": "Patna",
        "destination": "Delhi",
        "departure_time": "2026-11-24T12:30",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "invalid_timezone"


def test_unknown_stops(monkeypatch, tmp_path):
    import zipfile
    path = tmp_path / "fixture.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("agency.txt", "agency_id,agency_name,agency_url,agency_timezone\nA,Fixture,http://example.invalid,America/New_York\n")
        archive.writestr("stops.txt", "stop_id,stop_name,stop_lat,stop_lon\nA,Alpha,51.5074,-0.1278\n")
        archive.writestr("routes.txt", "route_id,route_short_name,route_long_name,route_type\nR1,1,Fixture,3\n")
        archive.writestr("trips.txt", "route_id,service_id,trip_id,trip_headsign\nR1,WEEK,T1,Alpha\n")
        archive.writestr("stop_times.txt", "trip_id,arrival_time,departure_time,stop_id,stop_sequence\nT1,09:00:00,09:00:00,A,1\n")
        archive.writestr("calendar.txt", "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nWEEK,1,1,1,1,1,1,1,20200101,20300101\n")
    monkeypatch.setenv("CROWDSENSE_GTFS_PATH", str(path))
    response = client.post("/api/v1/journey/plan", json={
        "origin": "Unknown Origin",
        "destination": "Unknown Destination",
        "departure_time": "2026-11-24T12:30",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "invalid_origin"


def test_database_unavailable_is_safe_service_unavailable(monkeypatch):
    monkeypatch.setattr(routes, "get_gtfs_network", lambda: (_ for _ in ()).throw(ConnectionError("database unavailable")))
    response = client.post("/api/v1/journey/plan", json={
        "origin": "Patna",
        "destination": "Delhi",
        "departure_time": "2026-11-24T12:30",
    })
    assert response.status_code == 503
    assert response.json()["status"] == "service_unavailable"
    assert "database" not in str(response.json()).lower()


def test_unexpected_exception_returns_safe_internal_error(monkeypatch):
    monkeypatch.setattr(routes, "get_gtfs_network", lambda: (_ for _ in ()).throw(RuntimeError("sensitive internal detail")))
    response = client.post("/api/v1/journey/plan", json={
        "origin": "Patna",
        "destination": "Delhi",
        "departure_time": "2026-11-24T12:30",
    })
    assert response.status_code == 500
    assert response.json()["status"] == "internal_error"
    assert "sensitive" not in str(response.json()).lower()
