from __future__ import annotations

import heapq
from collections.abc import Callable

from app.models.domain import HexCoord, TerrainHex, TerrainType

# Six axial directions (E, NE, NW, W, SW, SE)
DIRECTIONS = [
    HexCoord(q=1, r=0),
    HexCoord(q=1, r=-1),
    HexCoord(q=0, r=-1),
    HexCoord(q=-1, r=0),
    HexCoord(q=-1, r=1),
    HexCoord(q=0, r=1),
]


def hex_add(a: HexCoord, b: HexCoord) -> HexCoord:
    return HexCoord(q=a.q + b.q, r=a.r + b.r)


def hex_subtract(a: HexCoord, b: HexCoord) -> HexCoord:
    return HexCoord(q=a.q - b.q, r=a.r - b.r)


def hex_distance(a: HexCoord, b: HexCoord) -> int:
    """Manhattan distance in cube coordinates: max(|dq|, |dr|, |ds|)."""
    dq = abs(a.q - b.q)
    dr = abs(a.r - b.r)
    ds = abs(a.s - b.s)
    return max(dq, dr, ds)


def hex_neighbors(coord: HexCoord) -> list[HexCoord]:
    """Return the 6 adjacent hexes."""
    return [hex_add(coord, d) for d in DIRECTIONS]


def hex_ring(center: HexCoord, radius: int) -> list[HexCoord]:
    """All hexes at exactly `radius` distance from center."""
    if radius == 0:
        return [center]
    results = []
    # Start radius steps in direction 4 (SW)
    current = center
    for _ in range(radius):
        current = hex_add(current, DIRECTIONS[4])
    for i in range(6):
        for _ in range(radius):
            results.append(current)
            current = hex_add(current, DIRECTIONS[i])
    return results


def hex_spiral(center: HexCoord, radius: int) -> list[HexCoord]:
    """All hexes within radius (inclusive), spiraling outward."""
    results = [center]
    for r in range(1, radius + 1):
        results.extend(hex_ring(center, r))
    return results


def hex_line(a: HexCoord, b: HexCoord) -> list[HexCoord]:
    """Line draw between two hexes using linear interpolation in cube coordinates."""
    n = hex_distance(a, b)
    if n == 0:
        return [a]
    results = []
    for i in range(n + 1):
        t = i / n
        fq = a.q + (b.q - a.q) * t
        fr = a.r + (b.r - a.r) * t
        fs = a.s + (b.s - a.s) * t
        rq = round(fq)
        rr = round(fr)
        rs = round(fs)
        # Fix rounding errors: the largest fractional deviation gets corrected
        dq = abs(rq - fq)
        dr = abs(rr - fr)
        ds = abs(rs - fs)
        if dq > dr and dq > ds:
            rq = -rr - rs
        elif dr > ds:
            rr = -rq - rs
        results.append(HexCoord(q=rq, r=rr))
    return results


def movement_cost_default(terrain: TerrainHex) -> int:
    """Default movement cost by terrain type."""
    costs: dict[TerrainType, int] = {
        TerrainType.PLAIN: 1,
        TerrainType.FOREST: 2,
        TerrainType.URBAN: 2,
        TerrainType.MOUNTAIN: 3,
        TerrainType.RIVER: 3,
        TerrainType.BRIDGE: 1,
        TerrainType.WATER: 999,  # impassable
    }
    return costs.get(terrain.terrain_type, 1)


def hex_astar(
    start: HexCoord,
    goal: HexCoord,
    terrain_map: dict[HexCoord, TerrainHex],
    cost_fn: Callable[[TerrainHex], int] = movement_cost_default,
    blocked: set[HexCoord] | None = None,
) -> list[HexCoord] | None:
    """A* pathfinding on hex grid. Returns path including start and goal, or None if no path."""
    if blocked is None:
        blocked = set()
    if start == goal:
        return [start]

    open_set: list[tuple[int, int, HexCoord]] = [(0, 0, start)]
    counter = 0
    came_from: dict[HexCoord, HexCoord] = {}
    g_score: dict[HexCoord, int] = {start: 0}

    while open_set:
        _, _, current = heapq.heappop(open_set)

        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        for neighbor in hex_neighbors(current):
            if neighbor in blocked:
                continue
            terrain = terrain_map.get(neighbor)
            if terrain is None:
                continue  # off map
            cost = cost_fn(terrain)
            if cost >= 999:
                continue  # impassable
            tentative_g = g_score[current] + cost
            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + hex_distance(neighbor, goal)
                counter += 1
                heapq.heappush(open_set, (f, counter, neighbor))

    return None  # no path found


def hex_reachable(
    start: HexCoord,
    movement_points: int,
    terrain_map: dict[HexCoord, TerrainHex],
    cost_fn: Callable[[TerrainHex], int] = movement_cost_default,
    blocked: set[HexCoord] | None = None,
) -> set[HexCoord]:
    """BFS to find all hexes reachable within given movement points."""
    if blocked is None:
        blocked = set()
    visited: set[HexCoord] = {start}
    queue: list[tuple[HexCoord, int]] = [(start, movement_points)]

    while queue:
        current, remaining = queue.pop(0)
        for neighbor in hex_neighbors(current):
            if neighbor in visited or neighbor in blocked:
                continue
            terrain = terrain_map.get(neighbor)
            if terrain is None:
                continue
            cost = cost_fn(terrain)
            if cost >= 999:
                continue
            if remaining >= cost:
                visited.add(neighbor)
                queue.append((neighbor, remaining - cost))

    return visited
