from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def valid_coordinate(lat: object, lng: object) -> bool:
    try:
        latitude = float(lat)
        longitude = float(lng)
    except (TypeError, ValueError):
        return False
    return (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


@dataclass
class ProviderHealth:
    provider_type: str
    configured: bool
    last_successful_sync: str | None = None
    valid_record_count: int = 0
    blocking_errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        freshness = "unknown"
        if self.last_successful_sync:
            freshness = "current"
        return {
            "provider_type": self.provider_type,
            "configured": self.configured,
            "last_successful_sync": self.last_successful_sync,
            "valid_record_count": self.valid_record_count,
            "blocking_errors": list(self.blocking_errors),
            "freshness_status": freshness,
        }


class StaticGTFSProvider(Protocol):
    def sync(self) -> ProviderHealth: ...
    def network(self) -> object | None: ...


class ETMProvider(Protocol):
    def sync(self) -> ProviderHealth: ...


class GPSProvider(Protocol):
    def sync(self) -> ProviderHealth: ...


class PassengerCountProvider(Protocol):
    def sync(self) -> ProviderHealth: ...


GTFS_HEALTH = ProviderHealth("gtfs_static", False)
CROWD_HEALTH = ProviderHealth("crowd_passenger_count", False)


def stale_status(last_successful_sync: str | None, stale_after_seconds: int) -> str:
    if not last_successful_sync:
        return "unknown"
    try:
        timestamp = datetime.fromisoformat(last_successful_sync.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()
    except (TypeError, ValueError):
        return "unknown"
    if age < 0:
        return "unknown"
    return "stale" if age > stale_after_seconds else "current"
