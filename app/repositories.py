from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import db_session
from app.persistence_models import (
    Agency,
    Alert,
    AuditLog,
    GTFSImport,
    OccupancyEstimate,
    PassengerObservation,
    Recommendation,
    Route,
    ServiceCalendar,
    Stop,
    StopTime,
    Trip,
)


def import_agencies(agencies: list[dict]) -> int:
    if not agencies:
        return 0
    with db_session() as session:
        for a in agencies:
            agency_id = str(a.get("agency_id", "")).strip()
            if not agency_id:
                continue
            name = a.get("name") or a.get("agency_name") or agency_id
            timezone = a.get("timezone") or a.get("agency_timezone")
            existing = session.execute(
                select(Agency).where(Agency.agency_id == agency_id)
            ).scalar_one_or_none()
            if existing:
                existing.name = name
                existing.timezone = timezone
            else:
                session.add(Agency(agency_id=agency_id, name=name, timezone=timezone))
        session.flush()
    return len(agencies)


def upsert_routes(routes: list[dict]) -> int:
    if not routes:
        return 0
    with db_session() as session:
        bind = session.get_bind()
        is_sqlite = bind.dialect.name == "sqlite"
        if is_sqlite and len(routes) > 50:
            for i in range(0, len(routes), 5000):
                chunk = routes[i : i + 5000]
                rows = [
                    {
                        "route_id": r["route_id"],
                        "short_name": r.get("short_name"),
                        "long_name": r.get("long_name"),
                        "route_type": str(r.get("route_type") or r.get("type", "")),
                    }
                    for r in chunk
                ]
                stmt = sqlite_insert(Route).values(rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["route_id"],
                    set_={
                        "short_name": stmt.excluded.short_name,
                        "long_name": stmt.excluded.long_name,
                        "route_type": stmt.excluded.route_type,
                    },
                )
                session.execute(stmt)
        else:
            for route in routes:
                existing = session.execute(
                    select(Route).where(Route.route_id == route["route_id"])
                ).scalar_one_or_none()
                if existing:
                    existing.short_name = route.get("short_name")
                    existing.long_name = route.get("long_name")
                    existing.route_type = route.get("route_type") or route.get("type")
                else:
                    session.add(Route(
                        route_id=route["route_id"],
                        short_name=route.get("short_name"),
                        long_name=route.get("long_name"),
                        route_type=route.get("route_type") or route.get("type"),
                    ))
        session.flush()
    return len(routes)


def import_stops(stops: list[dict]) -> int:
    if not stops:
        return 0
    imported = 0
    with db_session() as session:
        bind = session.get_bind()
        is_sqlite = bind.dialect.name == "sqlite"
        if is_sqlite and len(stops) > 50:
            for i in range(0, len(stops), 5000):
                chunk = stops[i : i + 5000]
                rows = [
                    {
                        "stop_id": s["stop_id"],
                        "name": s.get("name"),
                        "lat": s.get("lat"),
                        "lng": s.get("lng"),
                        "location_type": str(s.get("location_type") or "0"),
                    }
                    for s in chunk
                ]
                stmt = sqlite_insert(Stop).values(rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["stop_id"],
                    set_={
                        "name": stmt.excluded.name,
                        "lat": stmt.excluded.lat,
                        "lng": stmt.excluded.lng,
                        "location_type": stmt.excluded.location_type,
                    },
                )
                session.execute(stmt)
            imported = len(stops)
        else:
            for stop in stops:
                existing = session.execute(
                    select(Stop).where(Stop.stop_id == stop["stop_id"])
                ).scalar_one_or_none()
                if existing:
                    existing.name = stop.get("name")
                    existing.lat = stop.get("lat")
                    existing.lng = stop.get("lng")
                    existing.location_type = stop.get("location_type")
                else:
                    session.add(Stop(
                        stop_id=stop["stop_id"],
                        name=stop.get("name"),
                        lat=stop.get("lat"),
                        lng=stop.get("lng"),
                        location_type=stop.get("location_type"),
                    ))
                    imported += 1
        session.flush()
    return imported


def import_service_calendars(calendars: list[dict]) -> int:
    if not calendars:
        return 0
    with db_session() as session:
        bind = session.get_bind()
        is_sqlite = bind.dialect.name == "sqlite"
        if is_sqlite and len(calendars) > 50:
            for i in range(0, len(calendars), 5000):
                chunk = calendars[i : i + 5000]
                rows = [
                    {
                        "service_id": c["service_id"],
                        "weekdays": c.get("weekdays"),
                        "start_date": c.get("start_date"),
                        "end_date": c.get("end_date"),
                        "exceptions": c.get("exceptions"),
                    }
                    for c in chunk
                ]
                stmt = sqlite_insert(ServiceCalendar).values(rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["service_id"],
                    set_={
                        "weekdays": stmt.excluded.weekdays,
                        "start_date": stmt.excluded.start_date,
                        "end_date": stmt.excluded.end_date,
                        "exceptions": stmt.excluded.exceptions,
                    },
                )
                session.execute(stmt)
        else:
            for c in calendars:
                existing = session.execute(
                    select(ServiceCalendar).where(ServiceCalendar.service_id == c["service_id"])
                ).scalar_one_or_none()
                if existing:
                    existing.weekdays = c.get("weekdays")
                    existing.start_date = c.get("start_date")
                    existing.end_date = c.get("end_date")
                    existing.exceptions = c.get("exceptions")
                else:
                    session.add(ServiceCalendar(
                        service_id=c["service_id"],
                        weekdays=c.get("weekdays"),
                        start_date=c.get("start_date"),
                        end_date=c.get("end_date"),
                        exceptions=c.get("exceptions"),
                    ))
        session.flush()
    return len(calendars)


def import_trips(trips: list[dict], batch_size: int = 5000) -> int:
    if not trips:
        return 0
    with db_session() as session:
        bind = session.get_bind()
        is_sqlite = bind.dialect.name == "sqlite"
        if is_sqlite and len(trips) > 50:
            for i in range(0, len(trips), batch_size):
                chunk = trips[i : i + batch_size]
                rows = [
                    {
                        "trip_id": t["trip_id"],
                        "route_id": t["route_id"],
                        "service_id": t["service_id"],
                        "headsign": t.get("headsign") or t.get("trip_headsign"),
                    }
                    for t in chunk
                ]
                stmt = sqlite_insert(Trip).values(rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["trip_id"],
                    set_={
                        "route_id": stmt.excluded.route_id,
                        "service_id": stmt.excluded.service_id,
                        "headsign": stmt.excluded.headsign,
                    },
                )
                session.execute(stmt)
        else:
            for t in trips:
                existing = session.execute(
                    select(Trip).where(Trip.trip_id == t["trip_id"])
                ).scalar_one_or_none()
                if existing:
                    existing.route_id = t["route_id"]
                    existing.service_id = t["service_id"]
                    existing.headsign = t.get("headsign") or t.get("trip_headsign")
                else:
                    session.add(Trip(
                        trip_id=t["trip_id"],
                        route_id=t["route_id"],
                        service_id=t["service_id"],
                        headsign=t.get("headsign") or t.get("trip_headsign"),
                    ))
        session.flush()
    return len(trips)


def import_stop_times(stop_times: list[dict], batch_size: int = 5000) -> int:
    if not stop_times:
        return 0
    with db_session() as session:
        bind = session.get_bind()
        is_sqlite = bind.dialect.name == "sqlite"
        for i in range(0, len(stop_times), batch_size):
            chunk = stop_times[i : i + batch_size]
            rows = [
                {
                    "trip_id": st["trip_id"],
                    "stop_id": st["stop_id"],
                    "arrival_seconds": st["arrival_seconds"],
                    "departure_seconds": st["departure_seconds"],
                    "stop_sequence": st["stop_sequence"],
                }
                for st in chunk
            ]
            if is_sqlite:
                stmt = sqlite_insert(StopTime).values(rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["trip_id", "stop_sequence"],
                    set_={
                        "stop_id": stmt.excluded.stop_id,
                        "arrival_seconds": stmt.excluded.arrival_seconds,
                        "departure_seconds": stmt.excluded.departure_seconds,
                    },
                )
                session.execute(stmt)
            else:
                for r in rows:
                    session.add(StopTime(**r))
        session.flush()
    return len(stop_times)


def get_database_gtfs_counts() -> dict:
    with db_session() as session:
        return {
            "agencies": session.query(func.count(Agency.id)).scalar() or 0,
            "routes": session.query(func.count(Route.id)).scalar() or 0,
            "stops": session.query(func.count(Stop.id)).scalar() or 0,
            "trips": session.query(func.count(Trip.id)).scalar() or 0,
            "stop_times": session.query(func.count(StopTime.id)).scalar() or 0,
            "calendars": session.query(func.count(ServiceCalendar.id)).scalar() or 0,
            "imports": session.query(func.count(GTFSImport.id)).scalar() or 0,
        }


def ingest_gtfs_network_to_db(network, source_uri: str | None = None) -> dict:
    """Ingest an entire GTFSNetwork into the persistent SQLAlchemy tables safely and idempotently."""
    source_uri = source_uri or str(getattr(network, "source", "in_memory"))

    # 1. Agencies
    agency_list = getattr(network, "agencies", [])
    if not agency_list:
        agency_list = [{
            "agency_id": "DEFAULT",
            "name": getattr(network, "timezone_name", "Transit Agency"),
            "timezone": getattr(network, "timezone_name", "Asia/Kolkata"),
        }]
    import_agencies(agency_list)

    # 2. Routes
    upsert_routes(list(network.routes.values()))

    # 3. Stops
    import_stops(list(network.stops.values()))

    # 4. Calendars
    calendar_list = []
    bounds = getattr(network, "calendar_bounds", {})
    dates = getattr(network, "calendar_dates", {})
    all_service_ids = set(network.calendar.keys()) | set(bounds.keys()) | set(dates.keys())
    for sid in all_service_ids:
        weekdays = list(network.calendar.get(sid, []))
        s_bound = bounds.get(sid, (None, None))
        start_str = s_bound[0].strftime("%Y%m%d") if s_bound and s_bound[0] else None
        end_str = s_bound[1].strftime("%Y%m%d") if s_bound and s_bound[1] else None
        exc_list = [
            {"date": d, "exception_type": et}
            for d, et in dates.get(sid, {}).items()
        ]
        calendar_list.append({
            "service_id": sid,
            "weekdays": weekdays,
            "start_date": start_str,
            "end_date": end_str,
            "exceptions": exc_list if exc_list else None,
        })
    import_service_calendars(calendar_list)

    # 5. Trips
    import_trips(list(network.trips.values()))

    # 6. Stop times
    raw_st = getattr(network, "raw_stop_times", None)
    if raw_st:
        import_stop_times(raw_st)
    elif network.edges:
        # Build sequence from edges
        derived_st = []
        for edge in network.edges:
            derived_st.append({
                "trip_id": edge["trip_id"],
                "stop_id": edge["from_stop"],
                "arrival_seconds": edge["departure"],
                "departure_seconds": edge["departure"],
                "stop_sequence": 1,
            })
            derived_st.append({
                "trip_id": edge["trip_id"],
                "stop_id": edge["to_stop"],
                "arrival_seconds": edge["arrival"],
                "departure_seconds": edge["arrival"],
                "stop_sequence": 2,
            })
        import_stop_times(derived_st)

    # Record GTFS Import
    import_id = record_gtfs_import(
        source_uri=source_uri,
        status="success",
        valid_routes=len(network.routes),
        valid_stops=len(network.stops),
        blocking_errors=[],
    )

    counts = get_database_gtfs_counts()
    counts["import_id"] = import_id
    return counts


def load_network_from_db(source_label: str = "database"):
    """Load a GTFSNetwork directly from the database tables."""
    from app.gtfs import GTFSNetwork

    network = GTFSNetwork.__new__(GTFSNetwork)
    network.source = Path(source_label)
    network.stops = {}
    network.routes = {}
    network.trips = {}
    network.edges = []
    network.load_errors = []
    network.calendar = {}
    network.calendar_bounds = {}
    network.calendar_dates = {}

    with db_session() as session:
        agency = session.execute(select(Agency)).scalars().first()
        if agency and agency.timezone:
            network.timezone_name = agency.timezone
            try:
                network.timezone = ZoneInfo(agency.timezone)
            except Exception:
                network.timezone = None
        else:
            network.timezone_name = "Asia/Kolkata"
            network.timezone = ZoneInfo("Asia/Kolkata")

        for s in session.execute(select(Stop)).scalars():
            network.stops[s.stop_id] = {
                "stop_id": s.stop_id,
                "name": s.name or "",
                "lat": s.lat,
                "lng": s.lng,
                "location_type": s.location_type or "0",
            }

        for r in session.execute(select(Route)).scalars():
            network.routes[r.route_id] = {
                "route_id": r.route_id,
                "short_name": r.short_name or "",
                "long_name": r.long_name or "",
                "type": r.route_type or "",
            }

        for t in session.execute(select(Trip)).scalars():
            network.trips[t.trip_id] = {
                "trip_id": t.trip_id,
                "route_id": t.route_id,
                "service_id": t.service_id,
                "headsign": t.headsign or "",
            }

        for c in session.execute(select(ServiceCalendar)).scalars():
            if c.weekdays:
                network.calendar[c.service_id] = set(c.weekdays)
            try:
                start = datetime.strptime(c.start_date, "%Y%m%d").date() if c.start_date else None
                end = datetime.strptime(c.end_date, "%Y%m%d").date() if c.end_date else None
            except Exception:
                start, end = None, None
            network.calendar_bounds[c.service_id] = (start, end)
            if c.exceptions:
                for exc in c.exceptions:
                    network.calendar_dates.setdefault(c.service_id, {})[exc["date"]] = exc["exception_type"]

        # Edges from stop_times
        stop_times_query = session.execute(
            select(StopTime.trip_id, StopTime.stop_id, StopTime.arrival_seconds, StopTime.departure_seconds)
            .order_by(StopTime.trip_id, StopTime.stop_sequence)
        ).all()

        current_trip_id = None
        current_times: list[tuple] = []
        for trip_id, stop_id, arrival, departure in stop_times_query:
            if trip_id != current_trip_id:
                if current_trip_id and current_trip_id in network.trips and len(current_times) > 1:
                    t_info = network.trips[current_trip_id]
                    for start_st, end_st in zip(current_times, current_times[1:]):
                        if end_st[2] >= start_st[3]:
                            network.edges.append({
                                "from_stop": start_st[1],
                                "to_stop": end_st[1],
                                "departure": start_st[3],
                                "arrival": end_st[2],
                                "trip_id": current_trip_id,
                                "route_id": t_info["route_id"],
                                "headsign": t_info["headsign"],
                                "service_id": t_info["service_id"],
                            })
                current_trip_id = trip_id
                current_times = []
            current_times.append((trip_id, stop_id, arrival, departure))

        if current_trip_id and current_trip_id in network.trips and len(current_times) > 1:
            t_info = network.trips[current_trip_id]
            for start_st, end_st in zip(current_times, current_times[1:]):
                if end_st[2] >= start_st[3]:
                    network.edges.append({
                        "from_stop": start_st[1],
                        "to_stop": end_st[1],
                        "departure": start_st[3],
                        "arrival": end_st[2],
                        "trip_id": current_trip_id,
                        "route_id": t_info["route_id"],
                        "headsign": t_info["headsign"],
                        "service_id": t_info["service_id"],
                    })

    return network


def record_gtfs_import(source_uri: str, status: str, valid_routes: int, valid_stops: int, blocking_errors: list[str] | None = None) -> int:
    with db_session() as session:
        record = GTFSImport(
            source_uri=source_uri,
            status=status,
            valid_routes=valid_routes,
            valid_stops=valid_stops,
            blocking_errors=blocking_errors or [],
        )
        session.add(record)
        session.flush()
        return record.id


def save_observation(
    provider_name: str,
    route_id: str | None,
    trip_id: str | None,
    stop_id: str | None,
    observed_at: datetime,
    boarding_count: int | None,
    alighting_count: int | None,
    source_status: str,
) -> int:
    with db_session() as session:
        observation = PassengerObservation(
            provider_name=provider_name,
            route_id=route_id,
            trip_id=trip_id,
            stop_id=stop_id,
            observed_at=observed_at,
            boarding_count=boarding_count,
            alighting_count=alighting_count,
            source_status=source_status,
        )
        session.add(observation)
        session.flush()
        return observation.id


def save_alert_recommendation(alert: dict, recommendation: dict) -> None:
    with db_session() as session:
        existing = session.get(Alert, alert["id"])
        if not existing:
            session.add(Alert(
                id=alert["id"],
                kind=alert["kind"],
                route_id=alert["affected_route"],
                segment_id=alert["affected_segment"],
                severity=alert["severity"],
                confidence=alert["confidence"],
                evidence=alert["evidence"],
            ))
        existing_recommendation = session.get(Recommendation, recommendation["id"])
        if not existing_recommendation:
            session.add(Recommendation(
                id=recommendation["id"],
                alert_id=recommendation["alert_id"],
                route_id=recommendation["affected_route"],
                segment_id=recommendation["affected_segment"],
                recommendation_type=recommendation["recommendation_type"],
                description=recommendation["description"],
                evidence=recommendation["evidence"],
                severity=recommendation["severity"],
                confidence=recommendation["confidence"],
                expected_benefit=recommendation["expected_benefit"],
                cost_if_available=recommendation["cost_if_available"],
                controller_approval=recommendation["controller_approval"],
                execution_status=recommendation["execution_status"],
                outcome=recommendation.get("outcome"),
            ))


def record_audit(recommendation_id: str, action: str, controller: str, rationale: str) -> int:
    with db_session() as session:
        entry = AuditLog(
            recommendation_id=recommendation_id,
            action=action,
            controller=controller,
            rationale=rationale,
        )
        session.add(entry)
        session.flush()
        return entry.id


def list_persisted_audit() -> list[dict]:
    with db_session() as session:
        entries = session.execute(
            select(AuditLog).order_by(AuditLog.timestamp.desc())
        ).scalars().all()
        return [
            {
                "timestamp": entry.timestamp.isoformat(),
                "recommendation_id": entry.recommendation_id,
                "action": entry.action,
                "controller": entry.controller,
                "rationale": entry.rationale,
            }
            for entry in entries
        ]

