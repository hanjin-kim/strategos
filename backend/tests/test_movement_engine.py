from __future__ import annotations

import pytest

from app.engine.game_state import GameState
from app.engine.movement_engine import MovementEngine
from app.models.actions import ActionType, MilitaryAction
from app.models.domain import (
    HexCoord,
    Side,
    TerrainHex,
    TerrainType,
    Unit,
    UnitSize,
    UnitStatus,
    UnitType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plain_terrain(q_range: range, r_range: range) -> dict[HexCoord, TerrainHex]:
    """Build a terrain dict of PLAIN hexes for given q/r ranges."""
    terrain: dict[HexCoord, TerrainHex] = {}
    for q in q_range:
        for r in r_range:
            coord = HexCoord(q=q, r=r)
            terrain[coord] = TerrainHex(coord=coord, terrain_type=TerrainType.PLAIN)
    return terrain


def _make_unit(
    uid: str,
    side: Side,
    q: int,
    r: int,
    mp: int = 4,
    unit_type: UnitType = UnitType.INFANTRY,
    status: UnitStatus = UnitStatus.ACTIVE,
) -> Unit:
    return Unit(
        id=uid,
        name=uid,
        side=side,
        unit_type=unit_type,
        size=UnitSize.BATTALION,
        position=HexCoord(q=q, r=r),
        strength=1.0,
        morale=1.0,
        movement_points=mp,
        max_movement_points=mp,
        attack_power=10.0,
        defense_power=10.0,
        effective_range=1,
        ammo=1.0,
        fuel=1.0,
        status=status,
    )


def _make_action(
    unit_id: str,
    target_q: int,
    target_r: int,
    action_type: ActionType = ActionType.MOVE,
) -> MilitaryAction:
    return MilitaryAction(
        action_id=f"act_{unit_id}",
        turn=1,
        commander_id="cmd1",
        unit_id=unit_id,
        action_type=action_type,
        target_hex=HexCoord(q=target_q, r=target_r),
    )


def _build_state(
    units: list[Unit],
    terrain: dict[HexCoord, TerrainHex],
) -> GameState:
    state = GameState()
    state.terrain = terrain
    for u in units:
        state.units[u.id] = u
    return state


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMovementEngine:
    def setup_method(self):
        self.engine = MovementEngine()

    # 1. Simple move: (0,0) -> (2,0) on plain, MP=4
    def test_simple_move(self):
        terrain = _make_plain_terrain(range(-1, 6), range(-1, 6))
        unit = _make_unit("u1", Side.BLUE, 0, 0, mp=4)
        state = _build_state([unit], terrain)

        results = self.engine.execute_moves(
            [_make_action("u1", 2, 0)], state
        )

        assert len(results) == 1
        r = results[0]
        assert r.unit_id == "u1"
        assert r.final_position == HexCoord(q=2, r=0)
        assert r.movement_spent == 2
        assert r.remaining_mp == 2
        # path includes start and all steps
        assert HexCoord(q=0, r=0) in r.path
        assert HexCoord(q=2, r=0) in r.path

    # 2. Partial move: MP=2, wants (5,0) -> only reaches (2,0)
    def test_partial_move_mp_limited(self):
        terrain = _make_plain_terrain(range(-1, 8), range(-1, 4))
        unit = _make_unit("u1", Side.BLUE, 0, 0, mp=2)
        state = _build_state([unit], terrain)

        results = self.engine.execute_moves(
            [_make_action("u1", 5, 0)], state
        )

        assert len(results) == 1
        r = results[0]
        assert r.movement_spent == 2
        assert r.remaining_mp == 0
        # Must not overshoot MP
        assert r.final_position != HexCoord(q=5, r=0)

    # 3. Mountain terrain: unit MP=2, mountain at (1,0) costs 3 -> can't cross.
    #    The corridor is narrow: only (0,0), (1,0), (2,0) exist, so A* has no
    #    alternative route around the mountain.
    def test_mountain_blocks_move(self):
        # Only provide three hexes in a straight line so there is no alternate route
        coords = [HexCoord(q=0, r=0), HexCoord(q=1, r=0), HexCoord(q=2, r=0)]
        terrain: dict[HexCoord, TerrainHex] = {}
        for c in coords:
            terrain[c] = TerrainHex(coord=c, terrain_type=TerrainType.PLAIN)
        # Override (1,0) with mountain (cost 3)
        mountain_coord = HexCoord(q=1, r=0)
        terrain[mountain_coord] = TerrainHex(
            coord=mountain_coord, terrain_type=TerrainType.MOUNTAIN
        )
        unit = _make_unit("u1", Side.BLUE, 0, 0, mp=2)
        state = _build_state([unit], terrain)

        results = self.engine.execute_moves(
            [_make_action("u1", 2, 0)], state
        )

        assert len(results) == 1
        r = results[0]
        # Can't afford mountain (cost 3 > mp 2), stays at start
        assert r.final_position == HexCoord(q=0, r=0)
        assert r.movement_spent == 0

    # 4. Blocked by enemy: path routes around enemy unit
    def test_path_routes_around_enemy(self):
        # Grid: 0..4 in q, -2..2 in r (wide enough to route around)
        terrain = _make_plain_terrain(range(-1, 6), range(-3, 4))
        unit = _make_unit("u1", Side.BLUE, 0, 0, mp=6)
        enemy = _make_unit("e1", Side.RED, 1, 0, mp=4)
        state = _build_state([unit, enemy], terrain)

        results = self.engine.execute_moves(
            [_make_action("u1", 2, 0)], state
        )

        assert len(results) == 1
        r = results[0]
        # Should reach (2,0) but not pass through (1,0)
        assert r.final_position == HexCoord(q=2, r=0)
        assert HexCoord(q=1, r=0) not in r.path

    # 5. No path available -> stays in place
    def test_no_path_stays_in_place(self):
        # Surround unit with water so it can't move
        origin = HexCoord(q=0, r=0)
        terrain: dict[HexCoord, TerrainHex] = {
            origin: TerrainHex(coord=origin, terrain_type=TerrainType.PLAIN),
        }
        # Add water in all 6 neighbors
        from app.utils.hex_grid import hex_neighbors
        for n in hex_neighbors(origin):
            terrain[n] = TerrainHex(coord=n, terrain_type=TerrainType.WATER)
        # Add target but no passable path to it
        target = HexCoord(q=3, r=0)
        terrain[target] = TerrainHex(coord=target, terrain_type=TerrainType.PLAIN)

        unit = _make_unit("u1", Side.BLUE, 0, 0, mp=4)
        state = _build_state([unit], terrain)

        results = self.engine.execute_moves(
            [_make_action("u1", 3, 0)], state
        )

        assert len(results) == 1
        r = results[0]
        assert r.final_position == HexCoord(q=0, r=0)
        assert r.movement_spent == 0

    # 6. WEGO conflict - same destination, different sides: both cancelled
    def test_same_dest_different_sides_both_cancelled(self):
        terrain = _make_plain_terrain(range(-1, 6), range(-1, 4))
        blue = _make_unit("b1", Side.BLUE, 0, 0, mp=4)
        red = _make_unit("r1", Side.RED, 2, 0, mp=4)
        state = _build_state([blue, red], terrain)

        results = self.engine.execute_moves(
            [
                _make_action("b1", 1, 0),
                _make_action("r1", 1, 0),
            ],
            state,
        )

        assert len(results) == 2
        by_id = {r.unit_id: r for r in results}
        assert by_id["b1"].final_position == HexCoord(q=0, r=0)
        assert by_id["r1"].final_position == HexCoord(q=2, r=0)
        assert by_id["b1"].movement_spent == 0
        assert by_id["r1"].movement_spent == 0

    # 7. WEGO conflict - same destination, same side: first moves, second stays
    def test_same_dest_same_side_first_moves(self):
        terrain = _make_plain_terrain(range(-1, 6), range(-1, 4))
        b1 = _make_unit("b1", Side.BLUE, 0, 0, mp=4)
        b2 = _make_unit("b2", Side.BLUE, 0, 1, mp=4)
        state = _build_state([b1, b2], terrain)

        results = self.engine.execute_moves(
            [
                _make_action("b1", 1, 0),
                _make_action("b2", 1, 0),
            ],
            state,
        )

        assert len(results) == 2
        by_id = {r.unit_id: r for r in results}
        # b1 listed first -> it moves; b2 stays
        assert by_id["b1"].final_position == HexCoord(q=1, r=0)
        assert by_id["b2"].final_position == HexCoord(q=0, r=1)
        assert by_id["b1"].movement_spent > 0
        assert by_id["b2"].movement_spent == 0

    # 8. Cross-move enemies: A->B, B->A -> both cancelled
    def test_cross_move_enemies_both_cancelled(self):
        terrain = _make_plain_terrain(range(-1, 4), range(-1, 4))
        blue = _make_unit("b1", Side.BLUE, 0, 0, mp=4)
        red = _make_unit("r1", Side.RED, 1, 0, mp=4)
        state = _build_state([blue, red], terrain)

        results = self.engine.execute_moves(
            [
                _make_action("b1", 1, 0),
                _make_action("r1", 0, 0),
            ],
            state,
        )

        assert len(results) == 2
        by_id = {r.unit_id: r for r in results}
        assert by_id["b1"].final_position == HexCoord(q=0, r=0)
        assert by_id["r1"].final_position == HexCoord(q=1, r=0)

    # 9. Triggered combat: unit moves adjacent to enemy
    def test_triggered_combat_adjacent_enemy(self):
        terrain = _make_plain_terrain(range(-1, 6), range(-1, 4))
        blue = _make_unit("b1", Side.BLUE, 0, 0, mp=4)
        red = _make_unit("r1", Side.RED, 3, 0, mp=4)
        state = _build_state([blue, red], terrain)

        results = self.engine.execute_moves(
            [_make_action("b1", 2, 0)], state
        )

        assert len(results) == 1
        r = results[0]
        assert r.final_position == HexCoord(q=2, r=0)
        # (2,0) is adjacent to (3,0) -> should trigger combat
        assert len(r.triggered_combats) > 0
        assert ("b1", "r1") in r.triggered_combats

    # 10. Empty move list -> empty results
    def test_empty_move_list(self):
        state = GameState()
        results = self.engine.execute_moves([], state)
        assert results == []

    # 11. DESTROYED unit ignored
    def test_destroyed_unit_ignored(self):
        terrain = _make_plain_terrain(range(-1, 6), range(-1, 4))
        unit = _make_unit("u1", Side.BLUE, 0, 0, mp=4, status=UnitStatus.DESTROYED)
        state = _build_state([unit], terrain)

        results = self.engine.execute_moves(
            [_make_action("u1", 2, 0)], state
        )

        assert results == []

    # 12. Armor mountain penalty: cost is base + 1 (3+1=4).
    #     Use a narrow three-hex corridor so A* cannot route around the mountain.
    def test_armor_mountain_penalty(self):
        # Only three hexes in a straight line — no alternate route
        coords = [HexCoord(q=0, r=0), HexCoord(q=1, r=0), HexCoord(q=2, r=0)]
        terrain: dict[HexCoord, TerrainHex] = {}
        for c in coords:
            terrain[c] = TerrainHex(coord=c, terrain_type=TerrainType.PLAIN)
        mountain_coord = HexCoord(q=1, r=0)
        terrain[mountain_coord] = TerrainHex(
            coord=mountain_coord, terrain_type=TerrainType.MOUNTAIN
        )
        # Armor with MP=3: base mountain cost 3, armor penalty +1 = 4 > MP=3 -> can't cross
        armor = _make_unit("a1", Side.BLUE, 0, 0, mp=3, unit_type=UnitType.ARMOR)
        state = _build_state([armor], terrain)

        results = self.engine.execute_moves(
            [_make_action("a1", 2, 0)], state
        )

        assert len(results) == 1
        r = results[0]
        # Armor mountain cost = 4 > MP=3, can't cross
        assert r.final_position == HexCoord(q=0, r=0)
        assert r.movement_spent == 0
