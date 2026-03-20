from __future__ import annotations

import pytest

from app.models.domain import HexCoord, TerrainHex, TerrainType
from app.utils.hex_grid import (
    hex_add,
    hex_astar,
    hex_distance,
    hex_line,
    hex_neighbors,
    hex_reachable,
    hex_ring,
    hex_spiral,
    hex_subtract,
    movement_cost_default,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def coord(q: int, r: int) -> HexCoord:
    return HexCoord(q=q, r=r)


def plain_hex(q: int, r: int) -> TerrainHex:
    return TerrainHex(coord=coord(q, r), terrain_type=TerrainType.PLAIN)


def make_terrain(hexes: list[TerrainHex]) -> dict[HexCoord, TerrainHex]:
    return {h.coord: h for h in hexes}


def plain_grid(qs: range, rs: range) -> dict[HexCoord, TerrainHex]:
    """Build a plain-terrain grid over q in qs, r in rs."""
    hexes = [plain_hex(q, r) for q in qs for r in rs]
    return make_terrain(hexes)


# ---------------------------------------------------------------------------
# hex_add / hex_subtract
# ---------------------------------------------------------------------------

def test_hex_add_basic() -> None:
    assert hex_add(coord(1, 2), coord(3, 4)) == coord(4, 6)


def test_hex_subtract_basic() -> None:
    assert hex_subtract(coord(4, 6), coord(3, 4)) == coord(1, 2)


# ---------------------------------------------------------------------------
# hex_distance
# ---------------------------------------------------------------------------

def test_distance_straight() -> None:
    assert hex_distance(coord(0, 0), coord(3, 0)) == 3


def test_distance_diagonal() -> None:
    # (0,0) to (1,2): cube coords (0,0,0) -> (1,2,-3), max(1,2,3)=3
    assert hex_distance(coord(0, 0), coord(1, 2)) == 3


def test_distance_zero() -> None:
    assert hex_distance(coord(0, 0), coord(0, 0)) == 0


def test_distance_negative_coords() -> None:
    # (-2,-2): s=4  (2,2): s=-4  dq=4, dr=4, ds=8 -> max=8
    assert hex_distance(coord(-2, -2), coord(2, 2)) == 8


# ---------------------------------------------------------------------------
# hex_neighbors
# ---------------------------------------------------------------------------

def test_neighbors_count() -> None:
    neighbors = hex_neighbors(coord(0, 0))
    assert len(neighbors) == 6


def test_neighbors_all_distance_one() -> None:
    origin = coord(0, 0)
    for n in hex_neighbors(origin):
        assert hex_distance(origin, n) == 1


def test_neighbors_unique() -> None:
    neighbors = hex_neighbors(coord(0, 0))
    assert len(set(neighbors)) == 6


def test_neighbors_non_origin() -> None:
    center = coord(2, -1)
    neighbors = hex_neighbors(center)
    assert len(neighbors) == 6
    for n in neighbors:
        assert hex_distance(center, n) == 1


# ---------------------------------------------------------------------------
# hex_ring
# ---------------------------------------------------------------------------

def test_ring_radius_zero() -> None:
    center = coord(0, 0)
    assert hex_ring(center, 0) == [center]


def test_ring_radius_one_count() -> None:
    assert len(hex_ring(coord(0, 0), 1)) == 6


def test_ring_radius_two_count() -> None:
    assert len(hex_ring(coord(0, 0), 2)) == 12


def test_ring_radius_three_count() -> None:
    assert len(hex_ring(coord(0, 0), 3)) == 18


def test_ring_all_correct_distance() -> None:
    center = coord(0, 0)
    for radius in (1, 2, 3):
        for h in hex_ring(center, radius):
            assert hex_distance(center, h) == radius


def test_ring_no_duplicates() -> None:
    center = coord(0, 0)
    ring = hex_ring(center, 2)
    assert len(ring) == len(set(ring))


# ---------------------------------------------------------------------------
# hex_spiral
# ---------------------------------------------------------------------------

def test_spiral_radius_zero() -> None:
    result = hex_spiral(coord(0, 0), 0)
    assert result == [coord(0, 0)]


def test_spiral_radius_one_count() -> None:
    assert len(hex_spiral(coord(0, 0), 1)) == 7  # 1 + 6


def test_spiral_radius_two_count() -> None:
    assert len(hex_spiral(coord(0, 0), 2)) == 19  # 1 + 6 + 12


def test_spiral_contains_center() -> None:
    center = coord(0, 0)
    assert center in hex_spiral(center, 2)


def test_spiral_all_within_radius() -> None:
    center = coord(0, 0)
    for h in hex_spiral(center, 2):
        assert hex_distance(center, h) <= 2


def test_spiral_no_duplicates() -> None:
    result = hex_spiral(coord(0, 0), 3)
    assert len(result) == len(set(result))


# ---------------------------------------------------------------------------
# hex_line
# ---------------------------------------------------------------------------

def test_line_same_point() -> None:
    a = coord(0, 0)
    assert hex_line(a, a) == [a]


def test_line_straight_count() -> None:
    result = hex_line(coord(0, 0), coord(3, 0))
    assert len(result) == 4


def test_line_straight_points() -> None:
    result = hex_line(coord(0, 0), coord(3, 0))
    assert result[0] == coord(0, 0)
    assert result[-1] == coord(3, 0)


def test_line_straight_sequential() -> None:
    result = hex_line(coord(0, 0), coord(3, 0))
    for i in range(len(result) - 1):
        assert hex_distance(result[i], result[i + 1]) == 1


def test_line_all_contiguous() -> None:
    a = coord(0, 0)
    b = coord(2, -2)
    result = hex_line(a, b)
    assert result[0] == a
    assert result[-1] == b
    assert len(result) == hex_distance(a, b) + 1
    for i in range(len(result) - 1):
        assert hex_distance(result[i], result[i + 1]) == 1


# ---------------------------------------------------------------------------
# movement_cost_default
# ---------------------------------------------------------------------------

def test_movement_cost_plain() -> None:
    t = TerrainHex(coord=coord(0, 0), terrain_type=TerrainType.PLAIN)
    assert movement_cost_default(t) == 1


def test_movement_cost_forest() -> None:
    t = TerrainHex(coord=coord(0, 0), terrain_type=TerrainType.FOREST)
    assert movement_cost_default(t) == 2


def test_movement_cost_urban() -> None:
    t = TerrainHex(coord=coord(0, 0), terrain_type=TerrainType.URBAN)
    assert movement_cost_default(t) == 2


def test_movement_cost_mountain() -> None:
    t = TerrainHex(coord=coord(0, 0), terrain_type=TerrainType.MOUNTAIN)
    assert movement_cost_default(t) == 3


def test_movement_cost_river() -> None:
    t = TerrainHex(coord=coord(0, 0), terrain_type=TerrainType.RIVER)
    assert movement_cost_default(t) == 3


def test_movement_cost_bridge() -> None:
    t = TerrainHex(coord=coord(0, 0), terrain_type=TerrainType.BRIDGE)
    assert movement_cost_default(t) == 1


def test_movement_cost_water() -> None:
    t = TerrainHex(coord=coord(0, 0), terrain_type=TerrainType.WATER)
    assert movement_cost_default(t) == 999


# ---------------------------------------------------------------------------
# hex_astar
# ---------------------------------------------------------------------------

def _build_plain_corridor() -> dict[HexCoord, TerrainHex]:
    """Straight corridor: q in 0..4, r=0, all PLAIN."""
    return make_terrain([plain_hex(q, 0) for q in range(5)])


def test_astar_straight_path() -> None:
    terrain = _build_plain_corridor()
    path = hex_astar(coord(0, 0), coord(4, 0), terrain)
    assert path is not None
    assert path[0] == coord(0, 0)
    assert path[-1] == coord(4, 0)
    assert len(path) == 5


def test_astar_same_start_goal() -> None:
    terrain = _build_plain_corridor()
    path = hex_astar(coord(0, 0), coord(0, 0), terrain)
    assert path == [coord(0, 0)]


def test_astar_no_path_off_map() -> None:
    terrain = _build_plain_corridor()
    # Goal is not in terrain_map
    path = hex_astar(coord(0, 0), coord(10, 10), terrain)
    assert path is None


def test_astar_blocked_hex_detour() -> None:
    """Path from (0,0) to (2,0) with (1,0) blocked — must go around."""
    # Build a small grid wide enough to detour
    terrain = plain_grid(range(-1, 4), range(-2, 3))
    blocked = {coord(1, 0)}
    path = hex_astar(coord(0, 0), coord(2, 0), terrain, blocked=blocked)
    assert path is not None
    assert path[0] == coord(0, 0)
    assert path[-1] == coord(2, 0)
    assert coord(1, 0) not in path


def test_astar_blocked_all_neighbors_no_path() -> None:
    """Start is completely surrounded by blocked hexes."""
    terrain = plain_grid(range(-2, 4), range(-2, 4))
    neighbors = hex_neighbors(coord(0, 0))
    blocked = set(neighbors)
    path = hex_astar(coord(0, 0), coord(3, 0), terrain, blocked=blocked)
    assert path is None


def test_astar_impassable_water_detour() -> None:
    """Water hex forces detour."""
    # Corridor with water at (2,0); detour through (2,-1)
    hexes = [plain_hex(q, 0) for q in range(5)]
    hexes += [plain_hex(q, -1) for q in range(5)]
    # Replace (2,0) with WATER
    hexes = [h for h in hexes if h.coord != coord(2, 0)]
    hexes.append(TerrainHex(coord=coord(2, 0), terrain_type=TerrainType.WATER))
    terrain = make_terrain(hexes)
    path = hex_astar(coord(0, 0), coord(4, 0), terrain)
    assert path is not None
    assert coord(2, 0) not in path
    assert path[-1] == coord(4, 0)


def test_astar_path_is_contiguous() -> None:
    terrain = plain_grid(range(-3, 4), range(-3, 4))
    path = hex_astar(coord(-2, -2), coord(2, 2), terrain)
    assert path is not None
    for i in range(len(path) - 1):
        assert hex_distance(path[i], path[i + 1]) == 1


# ---------------------------------------------------------------------------
# hex_reachable
# ---------------------------------------------------------------------------

def test_reachable_mp2_all_plain() -> None:
    """MP=2 on all-plain grid from (0,0) — should reach radius-2 spiral."""
    terrain = plain_grid(range(-3, 4), range(-3, 4))
    reachable = hex_reachable(coord(0, 0), 2, terrain)
    # Should include center + ring-1 + ring-2 = 19 hexes (and possibly more
    # if the grid extends, but distance<=2 hexes cost <=2 with plain terrain)
    expected = set(hex_spiral(coord(0, 0), 2))
    # All expected hexes must be reachable
    assert expected.issubset(reachable)
    # No hex further than 2 steps should be reachable on all-plain
    for h in reachable:
        assert hex_distance(coord(0, 0), h) <= 2


def test_reachable_includes_start() -> None:
    terrain = plain_grid(range(-2, 3), range(-2, 3))
    reachable = hex_reachable(coord(0, 0), 3, terrain)
    assert coord(0, 0) in reachable


def test_reachable_mountain_excluded_at_mp2() -> None:
    """Mountain costs 3 MP; with only 2 MP it should be unreachable."""
    terrain = plain_grid(range(-3, 4), range(-3, 4))
    mountain_coord = coord(1, 0)
    terrain = dict(terrain)  # mutable copy
    terrain[mountain_coord] = TerrainHex(
        coord=mountain_coord, terrain_type=TerrainType.MOUNTAIN
    )
    reachable = hex_reachable(coord(0, 0), 2, terrain)
    assert mountain_coord not in reachable


def test_reachable_mountain_included_at_mp3() -> None:
    """Mountain costs 3 MP; with 3 MP it should be reachable."""
    terrain = plain_grid(range(-3, 4), range(-3, 4))
    mountain_coord = coord(1, 0)
    terrain = dict(terrain)
    terrain[mountain_coord] = TerrainHex(
        coord=mountain_coord, terrain_type=TerrainType.MOUNTAIN
    )
    reachable = hex_reachable(coord(0, 0), 3, terrain)
    assert mountain_coord in reachable


def test_reachable_blocked_excluded() -> None:
    terrain = plain_grid(range(-3, 4), range(-3, 4))
    blocked = {coord(1, 0), coord(0, 1)}
    reachable = hex_reachable(coord(0, 0), 3, terrain, blocked=blocked)
    assert coord(1, 0) not in reachable
    assert coord(0, 1) not in reachable


def test_reachable_water_excluded() -> None:
    terrain = plain_grid(range(-2, 3), range(-2, 3))
    water_coord = coord(1, 0)
    terrain = dict(terrain)
    terrain[water_coord] = TerrainHex(
        coord=water_coord, terrain_type=TerrainType.WATER
    )
    reachable = hex_reachable(coord(0, 0), 5, terrain)
    assert water_coord not in reachable


def test_reachable_zero_mp() -> None:
    """With 0 MP only the start hex is reachable."""
    terrain = plain_grid(range(-2, 3), range(-2, 3))
    reachable = hex_reachable(coord(0, 0), 0, terrain)
    assert reachable == {coord(0, 0)}
