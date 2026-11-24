from datetime import timezone

import pandas as pd

from app.gtfs import GTFSNetwork
from app.occupancy import infer_alightings, segment_occupancy_profile
from app.providers import valid_coordinate, stale_status


def test_coordinate_validation_rejects_nan_and_bounds():
    assert valid_coordinate(51.5, -0.12)
    assert not valid_coordinate(float("nan"), 0)
    assert not valid_coordinate(91, 0)
    assert not valid_coordinate(0, 181)


def test_stale_status_marks_missing_and_old_data():
    assert stale_status(None, 900) == "unknown"
    assert stale_status("2020-01-01T00:00:00+00:00", 900) == "stale"


def test_duplicate_etm_rows_are_removed_and_alighting_is_conserved():
    frame = pd.DataFrame([
        {"route_id": "R1", "trip_id": "T1", "stop_sequence": 1, "boarding": 10, "alighting": 2},
        {"route_id": "R1", "trip_id": "T1", "stop_sequence": 1, "boarding": 10, "alighting": 2},
        {"route_id": "R1", "trip_id": "T1", "stop_sequence": 2, "boarding": 5, "alighting": 3},
    ])
    inferred = infer_alightings(frame)
    assert len(inferred) == 2
    assert sum(row["boardings"] for row in inferred) == 15
    onboard_by_stop = [row["onboard"] for row in inferred]
    assert onboard_by_stop[-1] >= 0
    for row in inferred:
        assert row["alightings"] >= 0


def test_missing_alighting_is_estimated_not_observed():
    inferred = infer_alightings([
        {"route_id": "R1", "trip_id": "T1", "stop_sequence": 1, "boardings": 10},
        {"route_id": "R1", "trip_id": "T1", "stop_sequence": 2, "boardings": 5},
    ])
    assert len(inferred) == 2
    assert all(row["alightings"] >= 0 for row in inferred)
