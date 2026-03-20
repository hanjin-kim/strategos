from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.engine.game_state import GameState
from app.models.domain import HexCoord, Side, TerrainType

SCENARIO_PATH = Path(__file__).parent.parent.parent / "scripts" / "seed_scenarios" / "korean_peninsula.json"


@pytest.fixture(scope="module")
def scenario_data() -> dict:
    with open(SCENARIO_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def state(scenario_data) -> GameState:
    return GameState(scenario_data=scenario_data)


# 1. Load JSON -> GameState: no errors
def test_scenario_loads_without_error(scenario_data):
    gs = GameState(scenario_data=scenario_data)
    assert gs is not None


# 2. Correct unit counts: 5 BLUE, 5 RED
def test_unit_counts(state):
    blue_units = state.get_units_by_side(Side.BLUE)
    red_units = state.get_units_by_side(Side.RED)
    assert len(blue_units) == 5
    assert len(red_units) == 5


# 3. Correct commander counts: 5 BLUE, 5 RED
def test_commander_counts(state):
    blue_cmds = [c for c in state.commanders.values() if c.side == Side.BLUE]
    red_cmds = [c for c in state.commanders.values() if c.side == Side.RED]
    assert len(blue_cmds) == 5
    assert len(red_cmds) == 5


# 4. Correct terrain count: 180 hexes
def test_terrain_hex_count(state):
    assert len(state.terrain) == 180


# 5. Force names correct
def test_force_names(state):
    assert state.forces[Side.BLUE].name == "ROK/US Combined Forces"
    assert state.forces[Side.RED].name == "DPRK Forces"


# 6. Specific unit exists: blue_1mech_1bn at position (2, 5)
def test_blue_1mech_1bn_position(state):
    unit = state.get_unit("blue_1mech_1bn")
    assert unit is not None
    assert unit.position == HexCoord(q=2, r=5)


# 7. Specific terrain exists: Seoul at (3, 5) is URBAN
def test_seoul_hex_is_urban(state):
    terrain = state.get_terrain_at(HexCoord(q=3, r=5))
    assert terrain is not None
    assert terrain.terrain_type == TerrainType.URBAN
    assert terrain.name == "Seoul"


# 8. Snapshot roundtrip: to_snapshot -> from_snapshot preserves all data
def test_snapshot_roundtrip(state):
    snapshot = state.to_snapshot()
    restored = GameState.from_snapshot(snapshot)

    assert restored.turn == state.turn
    assert restored.phase == state.phase
    assert len(restored.units) == len(state.units)
    assert len(restored.terrain) == len(state.terrain)
    assert len(restored.commanders) == len(state.commanders)
    assert len(restored.forces) == len(state.forces)

    unit = restored.get_unit("blue_1mech_1bn")
    assert unit is not None
    assert unit.position == HexCoord(q=2, r=5)
    assert unit.side == Side.BLUE

    seoul = restored.get_terrain_at(HexCoord(q=3, r=5))
    assert seoul is not None
    assert seoul.terrain_type == TerrainType.URBAN

    assert Side.BLUE in restored.forces
    assert Side.RED in restored.forces


# 9. Relationship data present in scenario JSON
def test_relationships_present(scenario_data):
    rels = scenario_data.get("relationships", [])
    assert len(rels) > 0
    types = {r["type"] for r in rels}
    assert "COMMANDS" in types
    assert "BELONGS_TO" in types
    assert "SUPPLIES" in types
