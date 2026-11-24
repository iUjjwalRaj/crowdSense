from __future__ import annotations

import csv
import gc
import os
import sys
import threading
import zipfile
from datetime import date, datetime
from io import TextIOWrapper
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.providers import GTFS_HEALTH, valid_coordinate, utc_now
from app.repositories import record_gtfs_import


class GTFSEdge:
    __slots__ = ("from_stop", "to_stop", "departure", "arrival", "trip_id", "route_id", "headsign", "service_id")

    def __init__(
        self,
        from_stop: str,
        to_stop: str,
        departure: int,
        arrival: int,
        trip_id: str,
        route_id: str,
        headsign: str,
        service_id: str,
    ):
        self.from_stop = from_stop
        self.to_stop = to_stop
        self.departure = departure
        self.arrival = arrival
        self.trip_id = trip_id
        self.route_id = route_id
        self.headsign = headsign
        self.service_id = service_id

    def __getitem__(self, key: str):
        return getattr(self, key)

    def get(self, key: str, default=None):
        return getattr(self, key, default)


def _time_seconds(value: str) -> int:
    parts = str(value).strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"invalid GTFS time: {value}")
    hour, minute, second = (int(part) for part in parts)
    if minute >= 60 or second >= 60:
        raise ValueError(f"invalid GTFS time: {value}")
    if hour < 0 or hour > 49:
        raise ValueError(f"invalid GTFS time outside GTFS service-day range: {value}")
    return hour * 3600 + minute * 60 + second


class GTFSNetwork:
    def __init__(self, source: str | Path):
        self.source = Path(source)
        self.stops: dict[str, dict] = {}
        self.routes: dict[str, dict] = {}
        self.trips: dict[str, dict] = {}
        self.edges: list[dict] = []
        self.timezone_name: str | None = None
        self.timezone: ZoneInfo | None = None
        self.load_errors: list[str] = []
        self.load()

    @property
    def raw_stop_times(self) -> list[dict]:
        rows: list[dict] = []
        for row in self._read_rows("stop_times.txt"):
            trip_id = row["trip_id"].strip()
            if trip_id not in self.trips:
                continue
            stop_id = row["stop_id"].strip()
            if stop_id not in self.stops:
                continue
            try:
                arrival = _time_seconds(row["arrival_time"])
                departure = _time_seconds(row["departure_time"])
                sequence = int(row["stop_sequence"])
            except (KeyError, TypeError, ValueError):
                continue
            rows.append({
                "trip_id": trip_id,
                "stop_id": stop_id,
                "arrival_seconds": arrival,
                "departure_seconds": departure,
                "stop_sequence": sequence,
            })
        return rows

    def _open_member(self, name: str):
        if self.source.is_dir():
            path = self.source / name
            return path.open("r", encoding="utf-8-sig", newline="")
        if zipfile.is_zipfile(self.source):
            archive = zipfile.ZipFile(self.source)
            if name not in archive.namelist():
                raise KeyError(name)
            return TextIOWrapper(archive.open(name), encoding="utf-8-sig")
        raise ValueError("GTFS source must be a directory or zip file")

    def _read_rows(self, name: str) -> Iterable[dict]:
        try:
            handle = self._open_member(name)
        except (FileNotFoundError, KeyError):
            return []
        with handle:
            yield from csv.DictReader(handle)

    def load(self) -> None:
        valid_stops = 0
        valid_routes = 0
        valid_trip_times = 0
        self.load_errors = []
        agency_rows = list(self._read_rows("agency.txt"))
        self.agencies = agency_rows
        if agency_rows:
            timezone_name = str(agency_rows[0].get("agency_timezone", "")).strip()
            if timezone_name:
                try:
                    self.timezone_name = timezone_name
                    self.timezone = ZoneInfo(timezone_name)
                except (ZoneInfoNotFoundError, ValueError):
                    self.load_errors.append(f"Invalid agency_timezone: {timezone_name}")
            else:
                self.load_errors.append("agency.txt is missing agency_timezone")
        else:
            self.load_errors.append("agency.txt is missing")
        for row in self._read_rows("stops.txt"):
            stop_id = row.get("stop_id", "").strip()
            if not stop_id:
                continue
            try:
                lat = float(row["stop_lat"])
                lng = float(row["stop_lon"])
            except (KeyError, TypeError, ValueError):
                lat = None
                lng = None
            if not valid_coordinate(lat, lng):
                lat = None
                lng = None
            self.stops[stop_id] = {
                "stop_id": stop_id,
                "name": row.get("stop_name", "").strip(),
                "lat": lat,
                "lng": lng,
                "location_type": row.get("location_type", "0"),
            }
            if lat is not None:
                valid_stops += 1

        for row in self._read_rows("routes.txt"):
            route_id = row.get("route_id", "").strip()
            if not route_id:
                continue
            self.routes[route_id] = {
                "route_id": route_id,
                "short_name": row.get("route_short_name", "").strip(),
                "long_name": row.get("route_long_name", "").strip(),
                "type": row.get("route_type", ""),
            }
            valid_routes += 1

        calendar: dict[str, set[int]] = {}
        for row in self._read_rows("calendar.txt"):
            service_id = row.get("service_id", "").strip()
            if not service_id:
                continue
            calendar[service_id] = {
                index for index, key in enumerate(
                    ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
                )
                if row.get(key, "0") == "1"
            }
            try:
                start = datetime.strptime(row["start_date"], "%Y%m%d").date()
                end = datetime.strptime(row["end_date"], "%Y%m%d").date()
            except (KeyError, TypeError, ValueError):
                start = None
                end = None
            if not hasattr(calendar, "_bounds"):
                pass
            self.calendar_bounds = getattr(self, "calendar_bounds", {})
            self.calendar_bounds[service_id] = (start, end)

        for row in self._read_rows("trips.txt"):
            trip_id = row["trip_id"].strip()
            self.trips[trip_id] = {
                "trip_id": trip_id,
                "route_id": row["route_id"].strip(),
                "service_id": row["service_id"].strip(),
                "headsign": row.get("trip_headsign", "").strip(),
            }

        stop_times: dict[str, list[tuple[int, str, int, int]]] = {}
        try:
            st_handle = self._open_member("stop_times.txt")
        except (FileNotFoundError, KeyError):
            st_handle = None
        if st_handle is not None:
            with st_handle:
                reader = csv.reader(st_handle)
                header = next(reader, None)
                if header:
                    col_idx = {col.strip(): idx for idx, col in enumerate(header)}
                    i_trip = col_idx.get("trip_id")
                    i_stop = col_idx.get("stop_id")
                    i_arr = col_idx.get("arrival_time")
                    i_dep = col_idx.get("departure_time")
                    i_seq = col_idx.get("stop_sequence")
                    if None not in (i_trip, i_stop, i_arr, i_dep, i_seq):
                        req_len = max(i_trip, i_stop, i_arr, i_dep, i_seq) + 1
                        trips_map = self.trips
                        stops_map = self.stops
                        intern = sys.intern
                        for row in reader:
                            if len(row) < req_len:
                                continue
                            trip_id = row[i_trip].strip()
                            if trip_id not in trips_map:
                                continue
                            stop_id = row[i_stop].strip()
                            if stop_id not in stops_map:
                                continue
                            try:
                                arrival = _time_seconds(row[i_arr])
                                departure = _time_seconds(row[i_dep])
                                sequence = int(row[i_seq])
                            except (ValueError, TypeError):
                                continue
                            valid_trip_times += 1
                            stop_times.setdefault(trip_id, []).append(
                                (sequence, intern(stop_id), arrival, departure)
                            )

        edges = self.edges
        intern = sys.intern
        for trip_id, times in stop_times.items():
            times.sort(key=lambda item: item[0])
            trip = self.trips[trip_id]
            t_id = intern(trip_id)
            r_id = intern(trip["route_id"])
            h_sign = intern(trip["headsign"]) if trip["headsign"] else ""
            s_id = intern(trip["service_id"])
            for start, end in zip(times, times[1:]):
                if end[2] < start[3]:
                    continue
                edges.append(
                    GTFSEdge(start[1], end[1], start[3], end[2], t_id, r_id, h_sign, s_id)
                )
        del stop_times
        gc.collect()

        self.calendar = calendar
        self._load_calendar_dates()
        GTFS_HEALTH.configured = True
        GTFS_HEALTH.last_successful_sync = utc_now()
        GTFS_HEALTH.valid_record_count = valid_stops
        GTFS_HEALTH.blocking_errors = []
        if not valid_stops:
            GTFS_HEALTH.blocking_errors.append("No GTFS stops with valid coordinates")
        if not valid_routes:
            GTFS_HEALTH.blocking_errors.append("No GTFS routes")
        if not valid_trip_times:
            GTFS_HEALTH.blocking_errors.append("No valid GTFS stop_times")
        try:
            record_gtfs_import(
                source_uri=str(self.source),
                status="success" if not GTFS_HEALTH.blocking_errors else "partial",
                valid_routes=valid_routes,
                valid_stops=valid_stops,
                blocking_errors=GTFS_HEALTH.blocking_errors,
            )
        except Exception:
            GTFS_HEALTH.blocking_errors.append("Database persistence is unavailable")

    def _load_calendar_dates(self) -> None:
        exceptions: dict[str, dict[str, int]] = {}
        for row in self._read_rows("calendar_dates.txt"):
            try:
                day = datetime.strptime(row["date"], "%Y%m%d").date()
                exceptions.setdefault(row["service_id"], {})[day.isoformat()] = int(row["exception_type"])
            except (KeyError, TypeError, ValueError):
                continue
        self.calendar_dates = exceptions

    def active_service(self, service_id: str, travel_date: date) -> bool:
        exceptions = self.calendar_dates.get(service_id, {})
        if travel_date.isoformat() in exceptions:
            return exceptions[travel_date.isoformat()] == 1
        if service_id in self.calendar:
            bounds = getattr(self, "calendar_bounds", {}).get(service_id)
            if bounds:
                start, end = bounds
                if start is not None and travel_date < start:
                    return False
                if end is not None and travel_date > end:
                    return False
            return travel_date.weekday() in self.calendar[service_id]
        # GTFS requires calendar.txt or calendar_dates.txt. A service absent from
        # both is not assumed available.
        return False

    def find_stop(self, value: str) -> str | None:
        value = value.strip()
        if value in self.stops:
            return value
        lowered = value.lower()
        matches = [
            stop_id for stop_id, stop in self.stops.items()
            if stop["name"].lower() == lowered
        ]
        if len(matches) == 1:
            return matches[0]

        # Canonical aliases for standard hubs
        canonical_aliases = {
            "hapur": "HPU",
            "noida sector 62": "237",
            "noida sec-62": "237",
            "noida sec 62": "237",
            "patna": "PNBE",
            "patna jn": "PNBE",
            "delhi": "NDLS",
            "new delhi": "NDLS",
            "anand vihar": "74",
            "anand vihar terminal": "ANVT",
            "kashmere gate": "8",
            "rajiv chowk": "207",
        }
        if lowered in canonical_aliases and canonical_aliases[lowered] in self.stops:
            return canonical_aliases[lowered]

        # Normalized comparison (handling sec- vs sector, punctuation)
        norm = lowered.replace("sector", "sec").replace("-", " ").replace(".", " ").strip()
        norm_matches = [
            stop_id for stop_id, stop in self.stops.items()
            if stop["name"].lower().replace("sector", "sec").replace("-", " ").replace(".", " ").strip() == norm
        ]
        if len(norm_matches) == 1:
            return norm_matches[0]

        # Prefix matching
        prefix_matches = [
            stop_id for stop_id, stop in self.stops.items()
            if stop["name"].lower().startswith(lowered)
        ]
        if len(prefix_matches) == 1:
            return prefix_matches[0]

        return None


_cached_networks: dict[tuple[str, float], GTFSNetwork] = {}
_network_lock = threading.Lock()


def get_gtfs_network() -> GTFSNetwork | None:
    source = os.getenv("CROWDSENSE_GTFS_PATH")
    if not source:
        if os.getenv("CROWDSENSE_GTFS_SOURCE") == "database":
            from app.repositories import load_network_from_db
            try:
                return load_network_from_db()
            except Exception:
                return None
        return None
    if source == "database":
        from app.repositories import load_network_from_db
        try:
            return load_network_from_db()
        except Exception:
            return None
    path = Path(source)
    if not path.exists():
        return None
    try:
        cache_key = (str(path.resolve()), path.stat().st_mtime)
    except Exception:
        with _network_lock:
            return GTFSNetwork(path)
    cached = _cached_networks.get(cache_key)
    if cached is not None:
        return cached
    with _network_lock:
        cached = _cached_networks.get(cache_key)
        if cached is not None:
            return cached
        network = GTFSNetwork(path)
        _cached_networks[cache_key] = network
        return network
