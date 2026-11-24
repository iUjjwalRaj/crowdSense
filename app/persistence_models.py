from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Agency(Base):
    __tablename__ = "agencies"
    id: Mapped[int] = mapped_column(primary_key=True)
    agency_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ProviderConfig(Base):
    __tablename__ = "provider_configs"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_type: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    configured: Mapped[bool] = mapped_column(Boolean, default=False)
    source_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    last_successful_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GTFSImport(Base):
    __tablename__ = "gtfs_imports"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_uri: Mapped[str] = mapped_column(String(1024), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    valid_routes: Mapped[int] = mapped_column(Integer, default=0)
    valid_stops: Mapped[int] = mapped_column(Integer, default=0)
    blocking_errors: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)


class Route(Base):
    __tablename__ = "routes"
    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    short_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    long_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    route_type: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Stop(Base):
    __tablename__ = "stops"
    id: Mapped[int] = mapped_column(primary_key=True)
    stop_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_type: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    route_id: Mapped[str] = mapped_column(String(128), ForeignKey("routes.route_id", ondelete="CASCADE"), index=True)
    service_id: Mapped[str] = mapped_column(String(128), index=True)
    headsign: Mapped[str | None] = mapped_column(String(255), nullable=True)


class StopTime(Base):
    __tablename__ = "stop_times"
    __table_args__ = (
        UniqueConstraint("trip_id", "stop_sequence", name="uq_stop_times_trip_sequence"),
        Index("ix_stop_times_trip_stop", "trip_id", "stop_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(128), ForeignKey("trips.trip_id", ondelete="CASCADE"), index=True)
    stop_id: Mapped[str] = mapped_column(String(128), ForeignKey("stops.stop_id", ondelete="CASCADE"), index=True)
    arrival_seconds: Mapped[int] = mapped_column(Integer)
    departure_seconds: Mapped[int] = mapped_column(Integer)
    stop_sequence: Mapped[int] = mapped_column(Integer)


class ServiceCalendar(Base):
    __tablename__ = "service_calendars"
    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    weekdays: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(8), nullable=True)
    exceptions: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)


class PassengerObservation(Base):
    __tablename__ = "passenger_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(128), index=True)
    route_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trip_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stop_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    boarding_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alighting_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_status: Mapped[str] = mapped_column(String(32), default="observed")


class OccupancyEstimate(Base):
    __tablename__ = "occupancy_estimates"
    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    trip_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    stop_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    estimated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    occupancy_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_source: Mapped[str] = mapped_column(String(32), default="unknown")
    data_status: Mapped[str] = mapped_column(String(32), default="unavailable")


class CrowdPrediction(Base):
    __tablename__ = "crowd_predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    trip_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    stop_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    predicted_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    predicted_occupancy: Mapped[float | None] = mapped_column(Float, nullable=True)
    tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    provider_name: Mapped[str] = mapped_column(String(128), index=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    route_id: Mapped[str] = mapped_column(String(128), index=True)
    segment_id: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    evidence: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(36), ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    route_id: Mapped[str] = mapped_column(String(128), index=True)
    segment_id: Mapped[str] = mapped_column(String(128), index=True)
    recommendation_type: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    severity: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    expected_benefit: Mapped[str] = mapped_column(Text)
    cost_if_available: Mapped[str | None] = mapped_column(Text, nullable=True)
    controller_approval: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    execution_status: Mapped[str] = mapped_column(String(32), default="not_executable")
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    controller: Mapped[str] = mapped_column(String(255))
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
