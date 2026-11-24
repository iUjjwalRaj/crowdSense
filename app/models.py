from __future__ import annotations

from enum import Enum


class OccupancyTier(str, Enum):
    SEATS_AVAILABLE = "SEATS_AVAILABLE"
    STANDING_AVAILABLE = "STANDING_AVAILABLE"
    CRUSH_LOAD = "CRUSH_LOAD"
    FULL = "FULL"


def occupancy_ratio(passengers: int | float, seated_capacity: int | float, total_capacity: int | float) -> float:
    if total_capacity <= 0:
        raise ValueError("total_capacity must be positive")
    if seated_capacity < 0:
        raise ValueError("capacity values must be non-negative")
    if float(seated_capacity) > float(total_capacity):
        raise ValueError("seated_capacity cannot exceed total_capacity")
    if seated_capacity <= 0:
        raise ValueError("seated_capacity must be positive")
    return float(passengers) / float(seated_capacity)


def occupancy_tier(passengers: int | float, seated_capacity: int | float, total_capacity: int | float) -> OccupancyTier:
    ratio = occupancy_ratio(passengers, seated_capacity, total_capacity)
    if ratio <= 0.70:
        return OccupancyTier.SEATS_AVAILABLE
    if ratio <= 1.15:
        return OccupancyTier.STANDING_AVAILABLE
    if ratio <= 1.50:
        return OccupancyTier.CRUSH_LOAD
    return OccupancyTier.FULL
