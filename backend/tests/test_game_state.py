from __future__ import annotations

import pytest

from app.engine.game_state import GameState
from app.models.domain import HexCoord, Side, UnitStatus
from app.models.simulation import TurnPhase

TEST_SCENARIO = {
    "map": {
        "hexes": [
            {"q": 0, "r": 0, "terrain": "PLAIN", "movement_cost": 1, "defense_modifier": 1.0},
            {"q": 1, "r": 0, "terrain": "PLAIN", "movement_cost": 1, "defense_modifier": 1.0},
            {"q": 0, "r": 1, "terrain": "MOUNTAIN", "movement_cost": 3, "defense_modifier": 1.5},
            {"q": 1, "r": 1, "terrain": "URBAN", "movement_cost": 2, "defense_modifier": 2.0},
            {"q": 2, "r": 0, "terrain": "PLAIN", "movement_cost": 1, "defense_modifier": 1.0},
        ]
    },
    "forces": {
        "BLUE": {
            "name": "Blue Force",
            "units": [
                {
                    "id": "blue_1bn", "name": "1st Battalion", "type": "INFANTRY",
                    "size": "BATTALION", "position": {"q": 0, "r": 0},
                    "strength": 1.0, "morale": 0.8, "max_movement_points": 2,
                    "attack_power": 10.0, "defense_power": 12.0, "effective_range": 1,
                }
            ],
            "commanders": [
                {"id": "blue_cmd1", "name": "Commander 1", "rank": "Battalion", "unit_id": "blue_1bn"}
            ]
        },
        "RED": {
            "name": "Red Force",
            "units": [
                {
                    "id": "red_1bn", "name": "1st Red Bn", "type": "ARMOR",
                    "size": "BATTALION", "position": {"q": 1, "r": 0},
                    "strength": 0.9, "morale": 0.7, "max_movement_points": 4,
                    "attack_power": 15.0, "defense_power": 10.0, "effective_range": 1,
                }
            ],
            "commanders": [
                {"id": "red_cmd1", "name": "Red Commander", "rank": "Battalion", "unit_id": "red_1bn"}
            ]
        }
    }
}


@pytest.fixture
def state():
    return GameState(scenario_data=TEST_SCENARIO)


# 1. Scenario loading
def test_scenario_loading_counts(state):
    assert len(state.units) == 2
    assert len(state.terrain) == 5
    assert len(state.commanders) == 2
    assert len(state.forces) == 2


def test_scenario_loading_sides(state):
    assert Side.BLUE in state.forces
    assert Side.RED in state.forces
    assert state.forces[Side.BLUE].name == "Blue Force"
    assert state.forces[Side.RED].name == "Red Force"


# 2. get_unit
def test_get_unit_existing(state):
    unit = state.get_unit("blue_1bn")
    assert unit is not None
    assert unit.id == "blue_1bn"


def test_get_unit_missing(state):
    assert state.get_unit("nonexistent") is None


# 3. get_units_by_side
def test_get_units_by_side(state):
    blue_units = state.get_units_by_side(Side.BLUE)
    red_units = state.get_units_by_side(Side.RED)
    assert len(blue_units) == 1
    assert len(red_units) == 1
    assert all(u.side == Side.BLUE for u in blue_units)
    assert all(u.side == Side.RED for u in red_units)


# 4. get_terrain_at
def test_get_terrain_at_existing(state):
    terrain = state.get_terrain_at(HexCoord(q=0, r=0))
    assert terrain is not None
    assert terrain.movement_cost == 1


def test_get_terrain_at_missing(state):
    assert state.get_terrain_at(HexCoord(q=99, r=99)) is None


# 5. get_units_at
def test_get_units_at(state):
    units = state.get_units_at(HexCoord(q=0, r=0))
    assert len(units) == 1
    assert units[0].id == "blue_1bn"


def test_get_units_at_empty(state):
    units = state.get_units_at(HexCoord(q=0, r=1))
    assert units == []


# 6. get_adjacent_enemies: blue at (0,0), red at (1,0) -> red is adjacent enemy
def test_get_adjacent_enemies_found(state):
    enemies = state.get_adjacent_enemies("blue_1bn")
    assert len(enemies) == 1
    assert enemies[0].id == "red_1bn"


# 7. get_adjacent_enemies: DESTROYED/ROUTED units excluded
def test_get_adjacent_enemies_excludes_destroyed(state):
    state.update_unit("red_1bn", status=UnitStatus.DESTROYED)
    assert state.get_adjacent_enemies("blue_1bn") == []


def test_get_adjacent_enemies_excludes_routed(state):
    state.update_unit("red_1bn", status=UnitStatus.ROUTED)
    assert state.get_adjacent_enemies("blue_1bn") == []


def test_get_adjacent_enemies_unit_not_found(state):
    assert state.get_adjacent_enemies("nonexistent") == []


# 8. update_unit: changes reflected, old reference unchanged (frozen model)
def test_update_unit(state):
    old_unit = state.get_unit("blue_1bn")
    state.update_unit("blue_1bn", strength=0.5)
    new_unit = state.get_unit("blue_1bn")
    assert new_unit.strength == 0.5
    assert old_unit.strength == 1.0  # frozen, original unchanged


# 9. remove_unit: status becomes DESTROYED
def test_remove_unit(state):
    state.remove_unit("blue_1bn")
    unit = state.get_unit("blue_1bn")
    assert unit is not None  # still in dict for logging
    assert unit.status == UnitStatus.DESTROYED


def test_remove_unit_missing_no_error(state):
    # Should not raise
    state.remove_unit("nonexistent")


# 10. advance_phase: COMMAND -> EXECUTION -> RESOLUTION
def test_advance_phase_sequence(state):
    assert state.phase == TurnPhase.COMMAND
    state.advance_phase()
    assert state.phase == TurnPhase.EXECUTION
    state.advance_phase()
    assert state.phase == TurnPhase.RESOLUTION


def test_advance_phase_no_wrap(state):
    state.phase = TurnPhase.RESOLUTION
    state.advance_phase()
    assert state.phase == TurnPhase.RESOLUTION  # stays at last phase


# 11. advance_turn: turn increments, phase resets, movement_points reset
def test_advance_turn(state):
    state.advance_phase()  # move to EXECUTION
    state.update_unit("red_1bn", movement_points=1)  # spend some MP
    state.advance_turn()
    assert state.turn == 1
    assert state.phase == TurnPhase.COMMAND
    # movement_points reset to max_movement_points
    assert state.get_unit("red_1bn").movement_points == 4


def test_advance_turn_only_resets_active(state):
    state.update_unit("blue_1bn", movement_points=0, status=UnitStatus.DESTROYED)
    state.advance_turn()
    # DESTROYED unit's MP should NOT be reset
    assert state.get_unit("blue_1bn").movement_points == 0


# 12. to_snapshot -> from_snapshot roundtrip
def test_snapshot_roundtrip(state):
    state.advance_phase()
    state.update_unit("blue_1bn", strength=0.7)
    snapshot = state.to_snapshot()
    restored = GameState.from_snapshot(snapshot)

    assert restored.turn == state.turn
    assert restored.phase == state.phase
    assert len(restored.units) == len(state.units)
    assert len(restored.terrain) == len(state.terrain)
    assert len(restored.commanders) == len(state.commanders)
    assert len(restored.forces) == len(state.forces)

    blue = restored.get_unit("blue_1bn")
    assert blue is not None
    assert blue.strength == 0.7
    assert blue.side == Side.BLUE

    terrain = restored.get_terrain_at(HexCoord(q=0, r=1))
    assert terrain is not None
    assert terrain.movement_cost == 3

    assert Side.BLUE in restored.forces
    assert Side.RED in restored.forces


# 13. Empty GameState construction
def test_empty_construction():
    state = GameState()
    assert state.turn == 0
    assert state.phase == TurnPhase.COMMAND
    assert state.units == {}
    assert state.terrain == {}
    assert state.commanders == {}
    assert state.forces == {}
    assert state.combat_log == []
