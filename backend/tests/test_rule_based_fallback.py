from __future__ import annotations

import uuid
import pytest

from app.agents.rule_based_fallback import RuleBasedFallback
from app.engine.game_state import GameState
from app.models.actions import ActionType, MissionType, OrderDirective
from app.models.domain import HexCoord, Side, UnitStatus


# ---------------------------------------------------------------------------
# Test scenario builder
# ---------------------------------------------------------------------------

def _make_scenario(blue_pos: dict, red_pos: dict | None = None, extra_hexes: list[dict] | None = None) -> dict:
    """Build a minimal scenario dict with configurable unit positions."""
    hexes = [
        {"q": 0, "r": 0, "terrain": "PLAIN", "movement_cost": 1, "defense_modifier": 1.0},
        {"q": 1, "r": 0, "terrain": "PLAIN", "movement_cost": 1, "defense_modifier": 1.0},
        {"q": 2, "r": 0, "terrain": "PLAIN", "movement_cost": 1, "defense_modifier": 1.0},
        {"q": -1, "r": 0, "terrain": "PLAIN", "movement_cost": 1, "defense_modifier": 1.0},
        {"q": 0, "r": -1, "terrain": "PLAIN", "movement_cost": 1, "defense_modifier": 1.0},
        {"q": 0, "r": 1, "terrain": "PLAIN", "movement_cost": 1, "defense_modifier": 1.0},
        {"q": 5, "r": 0, "terrain": "PLAIN", "movement_cost": 1, "defense_modifier": 1.0},
    ]
    if extra_hexes:
        hexes.extend(extra_hexes)

    blue_units = [
        {
            "id": "blue_1", "name": "Blue Bn 1", "type": "INFANTRY",
            "size": "BATTALION", "position": blue_pos,
            "strength": 1.0, "morale": 0.8, "max_movement_points": 2,
            "attack_power": 10.0, "defense_power": 10.0, "effective_range": 1,
        }
    ]

    red_units = []
    if red_pos:
        red_units.append({
            "id": "red_1", "name": "Red Bn 1", "type": "ARMOR",
            "size": "BATTALION", "position": red_pos,
            "strength": 1.0, "morale": 0.8, "max_movement_points": 4,
            "attack_power": 15.0, "defense_power": 10.0, "effective_range": 1,
        })

    scenario = {
        "map": {"hexes": hexes},
        "forces": {
            "BLUE": {
                "name": "Blue Force",
                "units": blue_units,
                "commanders": [
                    {"id": "blue_cmd1", "name": "Blue Commander", "rank": "Battalion", "unit_id": "blue_1"}
                ],
            },
        },
    }
    if red_units:
        scenario["forces"]["RED"] = {
            "name": "Red Force",
            "units": red_units,
            "commanders": [
                {"id": "red_cmd1", "name": "Red Commander", "rank": "Battalion", "unit_id": "red_1"}
            ],
        }
    return scenario


def _make_order(mission: MissionType, objective_hex: HexCoord | None = None) -> OrderDirective:
    return OrderDirective(
        order_id=str(uuid.uuid4()),
        turn=0,
        issuer_id="superior_cmd",
        target_unit_id="blue_1",
        mission=mission,
        objective_hex=objective_hex,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fallback():
    return RuleBasedFallback()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

# 1. DESTROYED unit -> empty list
def test_destroyed_unit_returns_empty(fallback):
    state = GameState(scenario_data=_make_scenario(blue_pos={"q": 0, "r": 0}))
    state.update_unit("blue_1", status=UnitStatus.DESTROYED)
    unit = state.get_unit("blue_1")
    result = fallback.decide("blue_cmd1", unit, state)
    assert result == []


# 2. ROUTED unit -> RETREAT action (away from enemy)
def test_routed_unit_retreats(fallback):
    state = GameState(scenario_data=_make_scenario(
        blue_pos={"q": 0, "r": 0},
        red_pos={"q": 1, "r": 0},
    ))
    state.update_unit("blue_1", status=UnitStatus.ROUTED)
    unit = state.get_unit("blue_1")
    result = fallback.decide("blue_cmd1", unit, state)
    assert len(result) == 1
    assert result[0].action_type == ActionType.RETREAT
    # Should retreat away from red at (1,0) - target must be on map
    assert result[0].target_hex is not None
    assert result[0].target_hex != HexCoord(q=1, r=0)


# 3. Enemy adjacent (not routed) -> DEFEND
def test_enemy_adjacent_defends(fallback):
    state = GameState(scenario_data=_make_scenario(
        blue_pos={"q": 0, "r": 0},
        red_pos={"q": 1, "r": 0},
    ))
    unit = state.get_unit("blue_1")
    result = fallback.decide("blue_cmd1", unit, state)
    assert len(result) == 1
    assert result[0].action_type == ActionType.DEFEND


# 4. OrderDirective ATTACK with objective_hex -> MOVE toward objective
def test_attack_order_with_objective_moves(fallback):
    state = GameState(scenario_data=_make_scenario(blue_pos={"q": 0, "r": 0}))
    objective = HexCoord(q=2, r=0)
    orders = _make_order(MissionType.ATTACK, objective_hex=objective)
    unit = state.get_unit("blue_1")
    result = fallback.decide("blue_cmd1", unit, state, superior_orders=orders)
    assert len(result) == 1
    assert result[0].action_type == ActionType.MOVE
    assert result[0].target_hex == objective


# 5. OrderDirective ATTACK without objective -> MOVE toward nearest enemy
def test_attack_order_without_objective_moves_to_enemy(fallback):
    state = GameState(scenario_data=_make_scenario(
        blue_pos={"q": 0, "r": 0},
        red_pos={"q": 5, "r": 0},
    ))
    orders = _make_order(MissionType.ATTACK)
    unit = state.get_unit("blue_1")
    result = fallback.decide("blue_cmd1", unit, state, superior_orders=orders)
    assert len(result) == 1
    assert result[0].action_type == ActionType.MOVE
    assert result[0].target_hex == HexCoord(q=5, r=0)


# 6. OrderDirective DEFEND -> DEFEND
def test_defend_order_defends(fallback):
    state = GameState(scenario_data=_make_scenario(blue_pos={"q": 0, "r": 0}))
    orders = _make_order(MissionType.DEFEND)
    unit = state.get_unit("blue_1")
    result = fallback.decide("blue_cmd1", unit, state, superior_orders=orders)
    assert len(result) == 1
    assert result[0].action_type == ActionType.DEFEND


# 7. OrderDirective WITHDRAW with objective -> RETREAT toward objective
def test_withdraw_order_retreats_to_objective(fallback):
    state = GameState(scenario_data=_make_scenario(blue_pos={"q": 0, "r": 0}))
    objective = HexCoord(q=-1, r=0)
    orders = _make_order(MissionType.WITHDRAW, objective_hex=objective)
    unit = state.get_unit("blue_1")
    result = fallback.decide("blue_cmd1", unit, state, superior_orders=orders)
    assert len(result) == 1
    assert result[0].action_type == ActionType.RETREAT
    assert result[0].target_hex == objective


# 8. OrderDirective RESERVE -> HOLD
def test_reserve_order_holds(fallback):
    state = GameState(scenario_data=_make_scenario(blue_pos={"q": 0, "r": 0}))
    orders = _make_order(MissionType.RESERVE)
    unit = state.get_unit("blue_1")
    result = fallback.decide("blue_cmd1", unit, state, superior_orders=orders)
    assert len(result) == 1
    assert result[0].action_type == ActionType.HOLD


# 9. No orders, no adjacent enemy -> HOLD (default)
def test_no_orders_no_enemy_holds(fallback):
    state = GameState(scenario_data=_make_scenario(blue_pos={"q": 0, "r": 0}))
    unit = state.get_unit("blue_1")
    result = fallback.decide("blue_cmd1", unit, state)
    assert len(result) == 1
    assert result[0].action_type == ActionType.HOLD


# 10. ROUTED unit with no valid retreat hex -> HOLD
def test_routed_no_valid_retreat_hex_holds(fallback):
    # Place blue at (0,0) with only (0,0) on the map - all neighbors off map
    state = GameState(scenario_data={
        "map": {
            "hexes": [
                {"q": 0, "r": 0, "terrain": "PLAIN", "movement_cost": 1, "defense_modifier": 1.0},
            ]
        },
        "forces": {
            "BLUE": {
                "name": "Blue Force",
                "units": [
                    {
                        "id": "blue_1", "name": "Blue Bn 1", "type": "INFANTRY",
                        "size": "BATTALION", "position": {"q": 0, "r": 0},
                        "strength": 1.0, "morale": 0.8, "max_movement_points": 2,
                        "attack_power": 10.0, "defense_power": 10.0, "effective_range": 1,
                    }
                ],
                "commanders": [
                    {"id": "blue_cmd1", "name": "Blue Commander", "rank": "Battalion", "unit_id": "blue_1"}
                ],
            },
            "RED": {
                "name": "Red Force",
                "units": [
                    {
                        "id": "red_1", "name": "Red Bn 1", "type": "ARMOR",
                        "size": "BATTALION", "position": {"q": 1, "r": 0},
                        "strength": 1.0, "morale": 0.8, "max_movement_points": 4,
                        "attack_power": 15.0, "defense_power": 10.0, "effective_range": 1,
                    }
                ],
                "commanders": [
                    {"id": "red_cmd1", "name": "Red Commander", "rank": "Battalion", "unit_id": "red_1"}
                ],
            },
        },
    })
    state.update_unit("blue_1", status=UnitStatus.ROUTED)
    unit = state.get_unit("blue_1")
    result = fallback.decide("blue_cmd1", unit, state)
    assert len(result) == 1
    assert result[0].action_type == ActionType.HOLD


# 11. All actions have "Rule-based fallback" reasoning
def test_all_actions_have_fallback_reasoning(fallback):
    # Test a few different scenarios to verify reasoning string
    scenarios_and_orders = [
        (_make_scenario(blue_pos={"q": 0, "r": 0}), None),
        (_make_scenario(blue_pos={"q": 0, "r": 0}), _make_order(MissionType.ATTACK, HexCoord(q=2, r=0))),
        (_make_scenario(blue_pos={"q": 0, "r": 0}), _make_order(MissionType.DEFEND)),
        (_make_scenario(blue_pos={"q": 0, "r": 0}), _make_order(MissionType.WITHDRAW, HexCoord(q=-1, r=0))),
    ]
    for scenario, orders in scenarios_and_orders:
        state = GameState(scenario_data=scenario)
        unit = state.get_unit("blue_1")
        result = fallback.decide("blue_cmd1", unit, state, superior_orders=orders)
        for action in result:
            assert action.reasoning == "Rule-based fallback"
