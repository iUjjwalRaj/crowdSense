from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd

from app.models import OccupancyTier, occupancy_tier


BOARDING_ALIASES = ("boardings", "boarding", "ons", "on", "passengers_in", "entries")
ALIGHTING_ALIASES = ("alightings", "alighting", "offs", "off", "passengers_out", "exits")
ORIGIN_ALIASES = ("origin", "origin_stop", "from_stop", "boarding_stop", "from")
DESTINATION_ALIASES = ("destination", "destination_stop", "to_stop", "alighting_stop", "to")
TRIP_ALIASES = ("trip_id", "vehicle_trip_id", "run_id", "trip")
ROUTE_ALIASES = ("route_id", "route", "line_id")
STOP_ALIASES = ("stop_id", "stop", "stop_sequence")
SEQUENCE_ALIASES = ("stop_sequence", "sequence", "stop_index", "stop_order")


def _first_column(columns: Iterable[str], aliases: Sequence[str]) -> str | None:
    normalized = {str(column).strip().lower(): column for column in columns}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def load_etm(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in (".parquet", ".pq"):
        return pd.read_parquet(path)
    raise ValueError("unsupported file type: use CSV or Parquet")


def clean_etm_table(table: pd.DataFrame | Iterable[Mapping[str, object]]) -> pd.DataFrame:
    frame = table.copy() if isinstance(table, pd.DataFrame) else pd.DataFrame(list(table))
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    frame = frame.drop_duplicates()
    return frame


def infer_alightings(
    table: pd.DataFrame | Iterable[Mapping[str, object]],
    *,
    decay: float = 0.08,
) -> list[dict]:
    """Infer destination alightings with an exponential attraction-decay model.

    Assumptions:
    - boarding/alighting counts are per trip and stop.
    - stop_sequence is numeric or otherwise sortable as listed in the table.
    - missing alightings are inferred by distributing onboard passengers across
      downstream stops using distance-decayed destination attraction.
    - invalid, negative, or non-numeric counts are removed.
    """
    if decay < 0:
        raise ValueError("decay must be non-negative")
    frame = clean_etm_table(table)
    trip_col = _first_column(frame.columns, TRIP_ALIASES)
    route_col = _first_column(frame.columns, ROUTE_ALIASES)
    stop_col = _first_column(frame.columns, STOP_ALIASES)
    seq_col = _first_column(frame.columns, SEQUENCE_ALIASES)
    boarding_col = _first_column(frame.columns, BOARDING_ALIASES)
    alighting_col = _first_column(frame.columns, ALIGHTING_ALIASES)
    if boarding_col is None:
        raise ValueError("tabular input requires a boarding count column")
    if seq_col is None and stop_col is None:
        raise ValueError("tabular input requires stop_sequence or stop_id")

    trip_col = trip_col or "__trip__"
    route_col = route_col or "__route__"
    if trip_col not in frame:
        frame[trip_col] = 0
    if route_col not in frame:
        frame[route_col] = ""
    frame["_sequence"] = pd.to_numeric(frame[seq_col], errors="coerce") if seq_col in frame else range(len(frame))
    frame["_boarding"] = pd.to_numeric(frame[boarding_col], errors="coerce").fillna(0).clip(lower=0)
    if alighting_col:
        frame["_observed_alighting"] = pd.to_numeric(frame[alighting_col], errors="coerce")
    else:
        frame["_observed_alighting"] = float("nan")
    frame = frame.dropna(subset=["_sequence"])

    output: list[dict] = []
    grouped = frame.groupby([route_col, trip_col], sort=False, dropna=False)
    for (route, trip), rows in grouped:
        rows = rows.sort_values("_sequence")
        onboard = 0
        origin_attractions: dict[object, float] = defaultdict(float)
        for row_index, row in rows.iterrows():
            sequence = int(row["_sequence"]) if float(row["_sequence"]).is_integer() else row["_sequence"]
            stop = row[stop_col] if stop_col in row and stop_col in rows.columns else sequence
            boarding = int(row["_boarding"])
            origin_attractions[stop] += boarding
            onboard += boarding

            observed = row["_observed_alighting"]
            if pd.notna(observed) and observed >= 0:
                alighting = min(int(round(observed)), onboard)
            else:
                downstream = list(origin_attractions.items())
                distance = 1.0
                weights = []
                for candidate_stop, attraction in downstream:
                    weights.append(max(1.0, attraction) * math.exp(-decay * distance))
                    distance += 1.0
                weight_sum = sum(weights)
                attraction_share = weights[0] / weight_sum if weight_sum else 0.0
                alighting = int(round(onboard * attraction_share)) if onboard else 0
                alighting = min(alighting, onboard)
            onboard -= alighting
            onboard = max(onboard, 0)
            output.append({
                "route_id": route,
                "trip_id": trip,
                "stop_id": stop,
                "stop_sequence": sequence,
                "boardings": boarding,
                "alightings": alighting,
                "onboard": onboard,
            })
    return output


def segment_occupancy_profile(
    inferred: Sequence[Mapping[str, object]],
    *,
    seated_capacity: int | float,
    total_capacity: int | float,
) -> list[dict]:
    if seated_capacity <= 0 or total_capacity <= 0:
        raise ValueError("capacity values must be positive")
    if seated_capacity > total_capacity:
        raise ValueError("seated_capacity cannot exceed total_capacity")

    profile: dict[tuple[object, object, object], dict] = {}
    for row in inferred:
        key = (row["route_id"], row["trip_id"], row["stop_id"])
        onboard = max(int(row["onboard"]), 0)
        ratio = onboard / float(seated_capacity)
        tier = occupancy_tier(onboard, seated_capacity, total_capacity)
        profile[key] = {
            "route_id": row["route_id"],
            "trip_id": row["trip_id"],
            "stop_id": row["stop_id"],
            "stop_sequence": row["stop_sequence"],
            "passengers": onboard,
            "seated_capacity": float(seated_capacity),
            "total_capacity": float(total_capacity),
            "crowdedness_index": round(ratio, 4),
            "occupancy_tier": tier.value,
        }
    return sorted(profile.values(), key=lambda item: (
        str(item["route_id"]), str(item["trip_id"]), item["stop_sequence"]
    ))
