import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app import database
from app.gtfs import GTFSNetwork, get_gtfs_network
from app.journey import plan_journey
from app.main import app
from app.repositories import (
    get_database_gtfs_counts,
    ingest_gtfs_network_to_db,
    load_network_from_db,
)


@pytest.fixture
def multimodal_network():
    path = Path("data/gtfs/india_multimodal.zip")
    assert path.exists(), "Multimodal GTFS dataset must exist"
    return GTFSNetwork(path)


def test_real_gtfs_files_exist_and_inspectable():
    for rel_path in [
        "data/gtfs/delhi_metro.zip",
        "data/gtfs/indian_railways.zip",
        "data/gtfs/india_multimodal.zip",
    ]:
        p = Path(rel_path)
        assert p.exists(), f"Expected {rel_path} to exist"
        assert p.stat().st_size > 100_000, f"Expected non-trivial file size for {rel_path}"

    net = GTFSNetwork("data/gtfs/india_multimodal.zip")
    assert net.timezone_name == "Asia/Kolkata"
    assert len(net.stops) >= 8000
    assert len(net.routes) >= 5000
    assert len(net.trips) >= 10000
    assert len(net.edges) >= 100000


def test_database_gtfs_ingestion_and_counts(tmp_path, monkeypatch, multimodal_network):
    db_file = tmp_path / "test_ingest.db"
    test_db_url = f"sqlite:///{db_file}"
    monkeypatch.setattr(database, "DATABASE_URL", test_db_url)
    monkeypatch.setattr(database, "engine", create_engine(test_db_url, future=True))
    monkeypatch.setattr(
        database,
        "SessionLocal",
        database.sessionmaker(bind=database.engine, autoflush=False, expire_on_commit=False, future=True),
    )
    database.create_tables()

    counts = ingest_gtfs_network_to_db(multimodal_network, source_uri="data/gtfs/india_multimodal.zip")
    assert counts["agencies"] >= 2
    assert counts["routes"] >= 5000
    assert counts["stops"] >= 8000
    assert counts["trips"] >= 10000
    assert counts["stop_times"] >= 100000
    assert counts["calendars"] >= 1000


@pytest.fixture
def delhi_metro_network():
    path = Path("data/gtfs/delhi_metro.zip")
    assert path.exists(), "Delhi Metro GTFS dataset must exist"
    return GTFSNetwork(path)


def test_database_idempotent_duplicate_handling(tmp_path, monkeypatch, delhi_metro_network):
    db_file = tmp_path / "test_idempotent.db"
    test_db_url = f"sqlite:///{db_file}"
    monkeypatch.setattr(database, "DATABASE_URL", test_db_url)
    monkeypatch.setattr(database, "engine", create_engine(test_db_url, future=True))
    monkeypatch.setattr(
        database,
        "SessionLocal",
        database.sessionmaker(bind=database.engine, autoflush=False, expire_on_commit=False, future=True),
    )
    database.create_tables()

    counts1 = ingest_gtfs_network_to_db(delhi_metro_network)
    counts2 = ingest_gtfs_network_to_db(delhi_metro_network)

    assert counts1["routes"] == counts2["routes"]
    assert counts1["stops"] == counts2["stops"]
    assert counts1["trips"] == counts2["trips"]
    assert counts1["stop_times"] == counts2["stop_times"]
    assert counts1["routes"] >= 30
    assert counts1["stops"] >= 250


def test_database_restart_persistence(tmp_path, monkeypatch, delhi_metro_network):
    db_file = tmp_path / "test_restart.db"
    test_db_url = f"sqlite:///{db_file}"
    monkeypatch.setattr(database, "DATABASE_URL", test_db_url)
    monkeypatch.setattr(database, "engine", create_engine(test_db_url, future=True))
    monkeypatch.setattr(
        database,
        "SessionLocal",
        database.sessionmaker(bind=database.engine, autoflush=False, expire_on_commit=False, future=True),
    )
    database.create_tables()
    ingest_gtfs_network_to_db(delhi_metro_network)

    # Simulate fresh backend restart
    restarted_engine = create_engine(test_db_url, future=True)
    monkeypatch.setattr(database, "engine", restarted_engine)
    monkeypatch.setattr(
        database,
        "SessionLocal",
        database.sessionmaker(bind=restarted_engine, autoflush=False, expire_on_commit=False, future=True),
    )

    rehydrated_net = load_network_from_db()
    assert len(rehydrated_net.stops) == len(delhi_metro_network.stops)
    assert len(rehydrated_net.routes) == len(delhi_metro_network.routes)
    assert len(rehydrated_net.trips) == len(delhi_metro_network.trips)
    assert len(rehydrated_net.edges) == len(delhi_metro_network.edges)
    assert rehydrated_net.timezone_name == "Asia/Kolkata"


def test_journey_hapur_to_noida_sector_62(multimodal_network):
    dep = datetime(2026, 11, 24, 6, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    result = plan_journey(
        multimodal_network,
        "Hapur",
        "Noida Sector 62",
        departure=dep,
    )
    assert result["status"] == "ok"
    assert result["alternatives"]
    best = result["alternatives"][0]
    assert best["stops"][0] == "HPU"
    assert best["stops"][-1] == "237"
    assert best["estimated_minutes"] > 0
    # Must include transit legs
    modes = {s["mode"] for s in best["segments"]}
    assert "transit" in modes


def test_journey_patna_to_delhi(multimodal_network):
    dep = datetime(2026, 11, 24, 6, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    result = plan_journey(
        multimodal_network,
        "Patna",
        "Delhi",
        departure=dep,
    )
    assert result["status"] == "ok"
    assert result["alternatives"]
    best = result["alternatives"][0]
    assert best["stops"][0] == "PNBE"
    assert best["stops"][-1] in ("NDLS", "DLI", "ANVT", "NZM")
    assert best["estimated_minutes"] > 0
    modes = {s["mode"] for s in best["segments"]}
    assert "transit" in modes


def test_journey_delhi_metro_intracity(multimodal_network):
    dep = datetime(2026, 11, 24, 8, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    result = plan_journey(
        multimodal_network,
        "Kashmere Gate",
        "Noida Sec-62",
        departure=dep,
    )
    assert result["status"] == "ok"
    assert result["alternatives"]
    best = result["alternatives"][0]
    assert best["stops"][0] == "8"
    assert best["stops"][-1] == "237"
    assert best["transfers"] <= 3


def test_journey_api_with_indian_multimodal(monkeypatch):
    monkeypatch.setenv("CROWDSENSE_GTFS_PATH", "data/gtfs/india_multimodal.zip")
    client = TestClient(app)
    response = client.post("/api/v1/journey/plan", json={
        "origin": "Hapur",
        "destination": "Noida Sector 62",
        "departure_time": "2026-11-24T06:00:00",
        "preference": "fastest",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["alternatives"]
    assert body["alternatives"][0]["stops"][0] == "HPU"
    assert body["alternatives"][0]["stops"][-1] == "237"


def test_unsupported_regions_and_edge_cases(multimodal_network):
    # Completely unsupported region/station
    dep = datetime(2026, 11, 24, 8, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    unsupported_origin = plan_journey(
        multimodal_network,
        "Nonexistent Terminal XYZ",
        "Delhi",
        departure=dep,
    )
    assert unsupported_origin["status"] == "invalid_origin"

    unsupported_dest = plan_journey(
        multimodal_network,
        "Delhi",
        "Nonexistent Terminal XYZ",
        departure=dep,
    )
    assert unsupported_dest["status"] == "invalid_destination"

    # Same origin and destination
    same_stop = plan_journey(
        multimodal_network,
        "Hapur",
        "Hapur",
        departure=dep,
    )
    assert same_stop["status"] == "no_route"
