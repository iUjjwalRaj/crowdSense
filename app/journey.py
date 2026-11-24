from __future__ import annotations

import heapq
import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Iterable

from app.gtfs import GTFSNetwork
from app.providers import valid_coordinate


def _seconds_since_midnight(value: datetime) -> int:
    return value.hour * 3600 + value.minute * 60 + value.second


def _haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))


def _parse_location(value: str, network: GTFSNetwork) -> tuple[str | None, str | None]:
    if "," in value:
        parts = [part.strip() for part in value.split(",", 1)]
        try:
            lat, lng = float(parts[0]), float(parts[1])
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return None, f"{lat},{lng}"
        except ValueError:
            pass
    return network.find_stop(value), None


def _nearest_stop(network: GTFSNetwork, lat: float, lng: float, radius_meters: float) -> str | None:
    if not valid_coordinate(lat, lng):
        return None
    lat_delta = radius_meters / 110000.0
    candidates: list[tuple[float, str]] = []
    for stop_id, stop in network.stops.items():
        if stop["lat"] is None or stop["lng"] is None:
            continue
        s_lat, s_lng = float(stop["lat"]), float(stop["lng"])
        if abs(s_lat - lat) > lat_delta:
            continue
        distance = _haversine_meters(lat, lng, s_lat, s_lng)
        if distance <= radius_meters:
            candidates.append((distance, stop_id))
    return min(candidates)[1] if candidates else None


def plan_journey(
    network: GTFSNetwork,
    origin: str,
    destination: str,
    *,
    departure: datetime,
    preference: str = "balanced",
    max_transfers: int = 3,
    max_walking_meters: float = 1500,
    origin_lat: float | None = None,
    origin_lng: float | None = None,
    destination_lat: float | None = None,
    destination_lng: float | None = None,
) -> dict:
    if network.timezone is None:
        return {
            "status": "invalid_timezone",
            "alternatives": [],
            "detail": "GTFS agency timezone is missing or invalid.",
        }
    origin_stop = network.find_stop(origin) if origin else None
    destination_stop = network.find_stop(destination) if destination else None

    if origin_stop is None and "," in origin:
        parts = [part.strip() for part in origin.split(",", 1)]
        try:
            parsed_lat, parsed_lng = float(parts[0]), float(parts[1])
            if valid_coordinate(parsed_lat, parsed_lng):
                origin_stop = _nearest_stop(network, parsed_lat, parsed_lng, max_walking_meters)
        except (ValueError, IndexError):
            pass
    if destination_stop is None and "," in destination:
        parts = [part.strip() for part in destination.split(",", 1)]
        try:
            parsed_lat, parsed_lng = float(parts[0]), float(parts[1])
            if valid_coordinate(parsed_lat, parsed_lng):
                destination_stop = _nearest_stop(network, parsed_lat, parsed_lng, max_walking_meters)
        except (ValueError, IndexError):
            pass

    if origin_lat is not None and origin_lng is not None:
        origin_stop = _nearest_stop(network, origin_lat, origin_lng, max_walking_meters)
    if destination_lat is not None and destination_lng is not None:
        destination_stop = _nearest_stop(network, destination_lat, destination_lng, max_walking_meters)

    if origin_stop is None:
        return {"status": "invalid_origin", "alternatives": [], "detail": "Origin stop or location could not be matched to GTFS."}
    if destination_stop is None:
        return {"status": "invalid_destination", "alternatives": [], "detail": "Destination stop or location could not be matched to GTFS."}
    if origin_stop == destination_stop:
        return {"status": "no_route", "alternatives": [], "detail": "Origin and destination resolve to the same stop."}

    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=network.timezone)
    else:
        departure = departure.astimezone(network.timezone)

    departure_epoch = int(departure.timestamp())
    start_seconds = departure_epoch
    candidate_service_days = [
        departure.date() + timedelta(days=offset)
        for offset in (-2, -1, 0, 1, 2)
    ]

    walking_edges: list[dict] = []
    valid_stops = [
        (stop_id, float(stop["lat"]), float(stop["lng"]))
        for stop_id, stop in network.stops.items()
        if stop["lat"] is not None and stop["lng"] is not None
    ]
    valid_stops.sort(key=lambda item: item[1])
    lat_delta = max_walking_meters / 110000.0
    for i, (stop_id, lat1, lng1) in enumerate(valid_stops):
        for j in range(i + 1, len(valid_stops)):
            other_id, lat2, lng2 = valid_stops[j]
            if lat2 - lat1 > lat_delta:
                break
            if abs(lng2 - lng1) > lat_delta * 1.5:
                continue
            distance = _haversine_meters(lat1, lng1, lat2, lng2)
            if distance <= max_walking_meters:
                walk_mins = max(1.0, distance / 80.0 / 60.0)
                walking_edges.append({
                    "from_stop": stop_id,
                    "to_stop": other_id,
                    "minutes": walk_mins,
                    "walking": True,
                })
                walking_edges.append({
                    "from_stop": other_id,
                    "to_stop": stop_id,
                    "minutes": walk_mins,
                    "walking": True,
                })

    edges_by_stop: dict[str, list[dict]] = {}
    for edge in network.edges:
        trip = network.trips.get(edge["trip_id"])
        if not trip:
            continue
        for service_day in candidate_service_days:
            if not network.active_service(trip["service_id"], service_day):
                continue
            service_midnight = datetime.combine(service_day, datetime.min.time(), tzinfo=network.timezone)
            departure_dt = service_midnight + timedelta(seconds=edge["departure"])
            arrival_dt = service_midnight + timedelta(seconds=edge["arrival"])
            departure_epoch_edge = int(departure_dt.timestamp())
            arrival_epoch_edge = int(arrival_dt.timestamp())
            if departure_epoch_edge < departure_epoch:
                continue
            if departure_epoch_edge > departure_epoch + 49 * 3600:
                continue
            concrete = dict(edge)
            concrete["departure_epoch"] = departure_epoch_edge
            concrete["arrival_epoch"] = arrival_epoch_edge
            concrete["service_day"] = service_day.isoformat()
            edges_by_stop.setdefault(edge["from_stop"], []).append(concrete)

    for s, elist in edges_by_stop.items():
        elist.sort(key=lambda item: item["departure_epoch"])

    walking_by_stop: dict[str, list[dict]] = {}
    for edge in walking_edges:
        walking_by_stop.setdefault(edge["from_stop"], []).append(edge)

    dest_stop_obj = network.stops.get(destination_stop, {})
    dest_lat = float(dest_stop_obj["lat"]) if dest_stop_obj.get("lat") is not None else None
    dest_lng = float(dest_stop_obj["lng"]) if dest_stop_obj.get("lng") is not None else None

    def heuristic(stop_id: str) -> float:
        if dest_lat is None or dest_lng is None:
            return 0.0
        s = network.stops.get(stop_id, {})
        if s.get("lat") is None or s.get("lng") is None:
            return 0.0
        dist = _haversine_meters(float(s["lat"]), float(s["lng"]), dest_lat, dest_lng)
        return dist / 50.0  # 50 m/s = 180 km/h

    def route_for(weight_profile: str) -> list[dict] | None:
        heap: list[tuple[float, float, int, int, str, str | None, int, list[dict]]] = []
        counter = 0
        h_start = heuristic(origin_stop)
        heapq.heappush(heap, (h_start, 0.0, departure_epoch, counter, origin_stop, None, 0, []))
        best: dict[tuple[str, str | None, int], tuple[float, int]] = {
            (origin_stop, None, 0): (0.0, departure_epoch)
        }

        while heap:
            priority, cost, arrival_time, _, stop_id, trip_id, transfers, segments = heapq.heappop(heap)
            if stop_id == destination_stop:
                return segments
            if transfers > max_transfers:
                continue

            seen_routes: dict[tuple, int] = {}
            for edge in edges_by_stop.get(stop_id, []):
                if edge["departure_epoch"] < arrival_time:
                    continue
                is_same_trip = (trip_id is not None and edge["trip_id"] == trip_id)
                if not is_same_trip:
                    transfer_count = transfers + 1 if trip_id is not None else transfers
                    if transfer_count > max_transfers:
                        continue
                    r_key = (edge["route_id"], edge["to_stop"])
                    if seen_routes.get(r_key, 0) >= 2:
                        continue
                    seen_routes[r_key] = seen_routes.get(r_key, 0) + 1
                else:
                    transfer_count = transfers

                wait = max(0, edge["departure_epoch"] - arrival_time)
                travel = edge["arrival_epoch"] - edge["departure_epoch"]
                segment = {
                    "boarding_stop_id": stop_id,
                    "destination_stop_id": edge["to_stop"],
                    "route_id": edge["route_id"],
                    "trip_id": edge["trip_id"],
                    "headsign": edge["headsign"],
                    "mode": "transit",
                    "departure_seconds": edge["departure_epoch"],
                    "arrival_seconds": edge["arrival_epoch"],
                    "service_day": edge["service_day"],
                    "waiting_minutes": round(wait / 60, 2),
                    "travel_minutes": round(travel / 60, 2),
                    "walking_minutes": 0,
                    "transfer": transfer_count > transfers,
                    "expected_occupancy": None,
                    "crowdedness_tier": None,
                    "crowdedness_index": None,
                    "prediction_confidence": None,
                    "data_source": "unknown",
                    "data_status": "unavailable",
                    "data_freshness": None,
                }
                if weight_profile == "fastest":
                    added = wait + travel
                elif weight_profile == "comfort":
                    added = wait + travel + transfer_count * 10 * 60
                else:
                    added = wait + travel + transfer_count * 5 * 60
                new_time = edge["arrival_epoch"]
                key = (edge["to_stop"], edge["trip_id"], transfer_count)
                prior = best.get(key)
                if prior is None or (cost + added) < prior[0]:
                    best[key] = (cost + added, new_time)
                    counter += 1
                    h = heuristic(edge["to_stop"])
                    heapq.heappush(heap, (
                        cost + added + h, cost + added, new_time, counter,
                        edge["to_stop"], edge["trip_id"], transfer_count,
                        segments + [segment],
                    ))

            if trip_id is not None:
                for walk in walking_by_stop.get(stop_id, []):
                    walk_time = int(walk["minutes"] * 60)
                    new_transfers = transfers + 1 if len(segments) > 0 else transfers
                    if new_transfers > max_transfers:
                        continue
                    segment = {
                        "boarding_stop_id": stop_id,
                        "destination_stop_id": walk["to_stop"],
                        "route_id": None,
                        "trip_id": None,
                        "headsign": None,
                        "mode": "walk",
                        "departure_seconds": arrival_time,
                        "arrival_seconds": arrival_time + walk_time,
                        "waiting_minutes": 0,
                        "travel_minutes": 0,
                        "walking_minutes": round(walk_time / 60, 2),
                        "transfer": new_transfers > transfers,
                        "expected_occupancy": None,
                        "crowdedness_tier": None,
                        "crowdedness_index": None,
                        "prediction_confidence": None,
                        "data_source": "unknown",
                        "data_status": "unavailable",
                        "data_freshness": None,
                    }
                    added = walk_time + (10 * 60 if weight_profile == "comfort" else 5 * 60)
                    new_time = arrival_time + walk_time
                    key = (walk["to_stop"], None, new_transfers)
                    prior = best.get(key)
                    if prior is None or cost + added < prior[0]:
                        best[key] = (cost + added, new_time)
                        counter += 1
                        h = heuristic(walk["to_stop"])
                        heapq.heappush(heap, (
                            cost + added + h, cost + added, new_time, counter,
                            walk["to_stop"], None, new_transfers, segments + [segment],
                        ))
        return None

    alternatives: list[dict] = []
    for journey_type in ("fastest", "balanced", "comfort"):
        segments = route_for(journey_type)
        if not segments:
            continue
        walking_minutes = sum(segment["walking_minutes"] for segment in segments)
        waiting_minutes = sum(segment["waiting_minutes"] for segment in segments)
        travel_minutes = sum(segment["travel_minutes"] for segment in segments)
        transfer_count = sum(1 for segment in segments if segment["transfer"])
        last_time = max(segment["arrival_seconds"] for segment in segments)
        alternatives.append({
            "type": journey_type,
            "stops": [origin_stop] + [segment["destination_stop_id"] for segment in segments],
            "segments": segments,
            "estimated_minutes": round((last_time - departure_epoch) / 60, 2),
            "waiting_minutes": round(waiting_minutes, 2),
            "travel_minutes": round(travel_minutes, 2),
            "walking_minutes": round(walking_minutes, 2),
            "transfers": transfer_count,
            "fare": None,
            "comfort_score": None,
            "uncertainty": "high",
            "data_source": "unknown",
            "trade_off": (
                "Fastest scheduled option"
                if journey_type == "fastest"
                else "Balanced time and transfer trade-off"
                if journey_type == "balanced"
                else "Preference for fewer transfers and walking"
            ),
        })

    unique: list[dict] = []
    seen: set[str] = set()
    for alternative in alternatives:
        signature = "|".join(
            f"{segment['mode']}:{segment['route_id'] or ''}:{segment['boarding_stop_id']}:{segment['destination_stop_id']}"
            for segment in alternative["segments"]
        )
        if signature not in seen:
            seen.add(signature)
            unique.append(alternative)

    if not unique:
        return {"status": "no_route", "alternatives": [], "detail": "No scheduled or valid walking route was found."}
    return {
        "status": "ok",
        "origin": origin,
        "destination": destination,
        "origin_stop_id": origin_stop,
        "destination_stop_id": destination_stop,
        "departure_time": departure.isoformat(),
        "preference": preference,
        "alternatives": unique,
        "data_source": "gtfs",
    }
