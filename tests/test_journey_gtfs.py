import os
import zipfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.gtfs import GTFSNetwork
from app.journey import plan_journey
from app.main import app
from app.gtfs import _time_seconds


def write_gtfs_fixture(path):
    files = {
        "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\nA,CrowdSense Fixture,http://example.invalid,America/New_York\n",
        "stops.txt": (
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "A,Alpha,51.5074,-0.1278\n"
            "B,Beta,51.5131,-0.1181\n"
            "C,Gamma,51.5192,-0.1269\n"
        ),
        "routes.txt": "route_id,route_short_name,route_long_name,route_type\nR1,1,Alpha Line,3\n",
        "trips.txt": "route_id,service_id,trip_id,trip_headsign\nR1,WEEK,T1,Beta\nR1,WEEK,T2,Gamma\n",
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,09:00:00,09:00:00,A,1\n"
            "T1,09:30:00,09:30:00,B,2\n"
            "T1,10:00:00,10:00:00,C,3\n"
            "T2,09:15:00,09:15:00,A,1\n"
            "T2,09:45:00,09:45:00,B,2\n"
            "T2,10:15:00,10:15:00,C,3\n"
        ),
        "calendar.txt": (
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            "WEEK,1,1,1,1,1,1,1,20200101,20300101\n"
        ),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


@pytest.fixture
def gtfs_zip(tmp_path):
    path = tmp_path / "fixture_gtfs.zip"
    write_gtfs_fixture(path)
    return path


def write_overnight_gtfs_fixture(path):
    files = {
        "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\nA,CrowdSense Fixture,http://example.invalid,America/New_York\n",
        "stops.txt": (
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "N,North,40.7128,-74.0060\n"
            "M,Midnight,40.7200,-73.9900\n"
            "S,South,40.7300,-73.9800\n"
        ),
        "routes.txt": "route_id,route_short_name,route_long_name,route_type\nN1,1,Overnight Fixture,3\n",
        "trips.txt": "route_id,service_id,trip_id,trip_headsign\nN1,WEEK,OV1,South\n",
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "OV1,23:30:00,23:30:00,N,1\n"
            "OV1,25:15:00,25:15:00,M,2\n"
            "OV1,26:00:00,26:00:00,S,3\n"
        ),
        "calendar.txt": (
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            "WEEK,1,1,1,1,1,1,1,20200101,20300101\n"
        ),
        "calendar_dates.txt": (
            "service_id,date,exception_type\n"
            "WEEK,20261125,2\n"
            "WEEK,20261126,1\n"
        ),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def test_gtfs_extended_hour_parser():
    assert _time_seconds("23:30:00") == 84600
    assert _time_seconds("25:15:00") == 90900
    with pytest.raises(ValueError):
        _time_seconds("25:61:00")


@pytest.fixture
def overnight_gtfs_zip(tmp_path):
    path = tmp_path / "overnight_gtfs.zip"
    write_overnight_gtfs_fixture(path)
    return path


def test_overnight_trip_crosses_midnight_in_agency_timezone(overnight_gtfs_zip):
    network = GTFSNetwork(overnight_gtfs_zip)
    assert network.timezone_name == "America/New_York"
    departure = datetime(2026, 11, 24, 23, 0, tzinfo=ZoneInfo("America/New_York"))
    result = plan_journey(network, "North", "South", departure=departure)
    assert result["status"] == "ok"
    segment = result["alternatives"][0]["segments"][0]
    assert segment["departure_seconds"] < segment["arrival_seconds"]
    assert segment["arrival_seconds"] - segment["departure_seconds"] == 6300
    assert segment["service_day"] == "2026-11-24"


def test_arrival_25_15_is_the_next_service_day(overnight_gtfs_zip):
    network = GTFSNetwork(overnight_gtfs_zip)
    edge = network.edges[0]
    service_midnight = datetime(2026, 11, 24, tzinfo=network.timezone)
    arrival = service_midnight + timedelta(seconds=edge["arrival"])
    assert arrival.astimezone(ZoneInfo("America/New_York")).hour == 1
    assert arrival.date().isoformat() == "2026-11-25"


def test_calendar_exception_removes_tuesday_service(overnight_gtfs_zip):
    network = GTFSNetwork(overnight_gtfs_zip)
    assert not network.active_service("WEEK", datetime(2026, 11, 25).date())
    assert network.active_service("WEEK", datetime(2026, 11, 26).date())


def test_missing_timezone_is_explicit(overnight_gtfs_zip):
    network = GTFSNetwork(overnight_gtfs_zip)
    network.timezone = None
    network.timezone_name = None
    result = plan_journey(network, "North", "South", departure=datetime(2026, 11, 24, 23))
    assert result["status"] == "invalid_timezone"


def test_previous_service_day_trip_is_available_after_midnight(overnight_gtfs_zip):
    network = GTFSNetwork(overnight_gtfs_zip)
    departure = datetime(2026, 11, 25, 0, 30, tzinfo=ZoneInfo("America/New_York"))
    result = plan_journey(network, "Midnight", "South", departure=departure)
    assert result["status"] == "ok"


def test_gtfs_direct_route_and_time_dependent_departure(gtfs_zip):
    network = GTFSNetwork(gtfs_zip)
    result = plan_journey(
        network,
        "Alpha",
        "Gamma",
        departure=datetime(2026, 11, 24, 8, 30),
    )
    assert result["status"] == "ok"
    assert result["alternatives"]
    segment = result["alternatives"][0]["segments"][0]
    assert segment["mode"] == "transit"
    assert segment["route_id"] == "R1"
    assert segment["trip_id"] in ("T1", "T2")
    assert segment["data_status"] == "unavailable"
    assert segment["crowdedness_tier"] is None


def test_invalid_origin_and_destination(gtfs_zip):
    network = GTFSNetwork(gtfs_zip)
    invalid_origin = plan_journey(network, "Missing", "Gamma", departure=datetime(2026, 11, 24, 8))
    invalid_destination = plan_journey(network, "Alpha", "Missing", departure=datetime(2026, 11, 24, 8))
    assert invalid_origin["status"] == "invalid_origin"
    assert invalid_destination["status"] == "invalid_destination"


def test_location_coordinates_resolve_to_nearest_gtfs_stop(gtfs_zip):
    network = GTFSNetwork(gtfs_zip)
    result = plan_journey(
        network,
        "51.5075,-0.1277",
        "51.5191,-0.1270",
        departure=datetime(2026, 11, 24, 8),
        max_walking_meters=1000,
    )
    assert result["status"] == "ok"


def test_no_route_for_disconnected_request(gtfs_zip):
    network = GTFSNetwork(gtfs_zip)
    result = plan_journey(network, "Alpha", "Alpha", departure=datetime(2026, 11, 24, 8))
    assert result["status"] == "no_route"


def test_journey_api_missing_gtfs_data(monkeypatch):
    monkeypatch.delenv("CROWDSENSE_GTFS_PATH", raising=False)
    client = TestClient(app)
    response = client.post("/api/v1/journey/plan", json={
        "origin": "Alpha",
        "destination": "Gamma",
        "departure_time": "2026-11-24T08:30:00",
        "preference": "balanced",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "data_unavailable"
    assert response.json()["alternatives"] == []


def test_journey_api_uses_gtfs_fixture(monkeypatch, gtfs_zip):
    monkeypatch.setenv("CROWDSENSE_GTFS_PATH", str(gtfs_zip))
    client = TestClient(app)
    response = client.post("/api/v1/journey/plan", json={
        "origin": "Alpha",
        "destination": "Gamma",
        "departure_time": "2026-11-24T08:30:00",
        "preference": "fastest",
        "max_transfers": 1,
        "max_walking_distance": 1000,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["alternatives"]
    assert body["alternatives"][0]["segments"][0]["data_status"] == "unavailable"


def test_legacy_journey_search_alias(monkeypatch, gtfs_zip):
    monkeypatch.setenv("CROWDSENSE_GTFS_PATH", str(gtfs_zip))
    client = TestClient(app)
    response = client.post("/api/v1/journeys/search", json={
        "origin": "Alpha",
        "destination": "Gamma",
        "departure_time": "2026-11-24T08:30:00",
    })
    assert response.status_code == 200


def test_coordinate_pair_validation():
    client = TestClient(app)
    response = client.post("/api/v1/journey/plan", json={
        "origin": "Alpha",
        "destination": "Gamma",
        "origin_lat": 51.5074,
    })
    assert response.status_code == 422


def test_invalid_free_form_coordinates_do_not_resolve(gtfs_zip):
    network = GTFSNetwork(gtfs_zip)
    result = plan_journey(
        network,
        "NaN,-0.1278",
        "Gamma",
        departure=datetime(2026, 11, 24, 8),
    )
    assert result["status"] == "invalid_origin"


def test_readiness_reports_unconfigured_providers():
    client = TestClient(app)
    response = client.get("/api/v1/health/readiness")
    assert response.status_code == 200
    body = response.json()
    assert "gtfs" in body
    assert "crowd" in body
    assert body["crowd"]["configured"] is False
    assert body["prediction_service"]["configured"] is False


def test_occupancy_corridor_is_explicitly_unknown():
    client = TestClient(app)
    response = client.get("/api/v1/occ/occupancy/corridor")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "unknown"
    assert body["corridors"] == []
