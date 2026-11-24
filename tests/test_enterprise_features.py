from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.gtfs import GTFSNetwork
import app.api.routes as routes

client = TestClient(app, raise_server_exceptions=False)


def test_stops_search_popular_and_query(monkeypatch):
    class FakeNetwork:
        timezone_name = "Asia/Kolkata"
        stops = {
            "207": {"name": "Rajiv Chowk", "lat": 28.6328, "lng": 77.2195},
            "237": {"name": "Noida Sector 62", "lat": 28.6280, "lng": 77.3649},
            "HPU": {"name": "HAPUR", "lat": 28.7305, "lng": 77.7797},
            "NDLS": {"name": "NEW DELHI", "lat": 28.6431, "lng": 77.2223},
        }
        routes = {"R1": {}}
        trips = {"T1": {}}
        agencies = [{"agency_id": "DMRC", "agency_name": "Delhi Metro"}]

    monkeypatch.setattr(routes, "get_gtfs_network", lambda: FakeNetwork())

    # Empty query returns popular stops
    popular = client.get("/api/v1/stops/search")
    assert popular.status_code == 200
    p_data = popular.json()
    assert "stops" in p_data
    assert len(p_data["stops"]) >= 3

    # Query search
    searched = client.get("/api/v1/stops/search?q=Hapur")
    assert searched.status_code == 200
    s_data = searched.json()
    assert any(s["id"] == "HPU" for s in s_data["stops"])


def test_network_summary_endpoint(monkeypatch):
    class FakeNetwork:
        timezone_name = "Asia/Kolkata"
        stops = {"A": {}, "B": {}}
        routes = {"R1": {}}
        trips = {"T1": {}, "T2": {}}
        agencies = [{"agency_id": "DMRC", "agency_name": "Delhi Metro"}]

    monkeypatch.setattr(routes, "get_gtfs_network", lambda: FakeNetwork())

    res = client.get("/api/v1/network/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ready"
    assert body["stops_count"] == 2
    assert body["routes_count"] == 1
    assert body["trips_count"] == 2
    assert body["agencies"][0]["id"] == "DMRC"
