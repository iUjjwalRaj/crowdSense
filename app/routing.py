from __future__ import annotations

import heapq
from typing import Iterable, Mapping


def shortest_routes(
    graph: Mapping[str, Mapping[str, float]],
    origin: str,
    destination: str,
    *,
    alpha: float = 0.5,
    crowd_penalty: float = 1.0,
) -> dict:
    """Return fastest, balanced, and comfort-weighted alternatives.

    Graph edges are directed and weighted by travel minutes.  Each edge may
    also include an optional crowd level via ``graph[to]`` is intentionally
    not used here: graph may be a nested mapping of travel minutes or edge
    dictionaries such as {neighbor: {"minutes": 5, "crowding": 0.8}}.
    """
    alpha = min(max(alpha, 0.0), 1.0)
    crowd_penalty = max(crowd_penalty, 0.0)

    def edge_data(neighbor: str, data: object) -> tuple[float, float]:
        if isinstance(data, Mapping):
            return float(data.get("minutes", data.get("travel_minutes", 0))), float(data.get("crowding", 0))
        return float(data), 0.0

    def route_for(weight: float) -> list[str] | None:
        queue = [(0.0, origin, [origin])]
        best: dict[str, float] = {origin: 0.0}
        while queue:
            cost, stop, path = heapq.heappop(queue)
            if stop == destination:
                return path
            for neighbor, raw in graph.get(stop, {}).items():
                minutes, crowding = edge_data(neighbor, raw)
                penalty = weight * minutes + (1.0 - weight) * crowd_penalty * crowding * 100.0
                new_cost = cost + penalty
                if new_cost < best.get(neighbor, float("inf")):
                    best[neighbor] = new_cost
                    heapq.heappush(queue, (new_cost, neighbor, path + [neighbor]))
        return None

    def details(path: list[str] | None) -> dict | None:
        if not path:
            return None
        minutes = 0.0
        comfort_cost = 0.0
        for start, end in zip(path, path[1:]):
            edge_minutes, crowding = edge_data(end, graph[start][end])
            minutes += edge_minutes
            comfort_cost += crowd_penalty * crowding
        return {
            "stops": path,
            "estimated_minutes": round(minutes, 2),
            "crowd_cost": round(comfort_cost, 4),
        }

    alternatives: list[dict] = []
    fastest = route_for(1.0)
    comfort = route_for(alpha)
    balanced = route_for(0.5)
    if fastest:
        alternatives.append({"type": "fastest", **details(fastest)})
    if balanced:
        item = details(balanced)
        if item and item["stops"] not in [candidate["stops"] for candidate in alternatives]:
            alternatives.append({"type": "balanced", **item})
    if comfort:
        item = details(comfort)
        if item and item["stops"] not in [candidate["stops"] for candidate in alternatives]:
            alternatives.append({"type": "comfort", **item})
    if len(alternatives) == 1:
        alternatives.append({**alternatives[0], "type": "balanced"})
    return {
        "origin": origin,
        "destination": destination,
        "alpha": alpha,
        "alternatives": alternatives,
    }
