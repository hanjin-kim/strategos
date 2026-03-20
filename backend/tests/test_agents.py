from __future__ import annotations
import json
import pytest
from unittest.mock import patch, MagicMock
from app.models.domain import (
    Commander, Unit, Side, UnitType, UnitSize, UnitStatus, HexCoord, Force
)
from app.models.actions import (
    MilitaryAction, ActionType, OrderDirective, MissionType
)
from app.engine.game_state import GameState
from app.agents.base_commander import BaseCommander
from app.agents.theater_commander import TheaterCommander
from app.agents.battalion_commander import BattalionCommander
from app.agents.rule_based_fallback import RuleBasedFallback


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_unit(uid: str, side: Side, q: int, r: int, status: UnitStatus = UnitStatus.ACTIVE) -> Unit:
    return Unit(
        id=uid, name=f"Unit-{uid}", side=side,
        unit_type=UnitType.INFANTRY, size=UnitSize.BATTALION,
        position=HexCoord(q=q, r=r),
        strength=1.0, morale=0.8,
        movement_points=2, max_movement_points=2,
        attack_power=10.0, defense_power=10.0,
        effective_range=1, ammo=1.0, fuel=1.0,
        status=status,
    )


def make_commander(cid: str, side: Side, unit_id: str, rank: str = "Battalion") -> Commander:
    return Commander(id=cid, name=f"CMD-{cid}", side=side, rank=rank, unit_id=unit_id)


def make_game_state() -> GameState:
    gs = GameState()
    gs.turn = 1
    # BLUE units
    gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0)
    gs.units["blue2"] = make_unit("blue2", Side.BLUE, 1, 0)
    # RED units: blue1 adjacent (q=0,r=1), blue1 visible at 2 hexes
    gs.units["red1"] = make_unit("red1", Side.RED, 0, 1)   # adjacent to blue1
    gs.units["red2"] = make_unit("red2", Side.RED, 5, 5)   # far away - not visible
    gs.forces[Side.BLUE] = Force(side=Side.BLUE, name="Blue Force", unit_ids=["blue1", "blue2"])
    gs.forces[Side.RED] = Force(side=Side.RED, name="Red Force", unit_ids=["red1", "red2"])
    return gs


def make_blue_battalion_commander() -> BattalionCommander:
    cmd = make_commander("bcmd1", Side.BLUE, "blue1")
    return BattalionCommander(commander=cmd, llm_config={})


def make_blue_theater_commander() -> TheaterCommander:
    cmd = make_commander("tcmd1", Side.BLUE, "blue1", rank="Theater")
    return TheaterCommander(commander=cmd, llm_config={})


# ---------------------------------------------------------------------------
# 1. BaseCommander._apply_fog_of_war: own units visible, distant enemies hidden
# ---------------------------------------------------------------------------

def test_fog_of_war_own_units_visible():
    gs = make_game_state()
    cmd = make_commander("bcmd1", Side.BLUE, "blue1")
    agent = BattalionCommander(commander=cmd, llm_config={})

    visible = agent._apply_fog_of_war(gs)
    own_ids = {u.id for u in visible["own_units"]}
    assert "blue1" in own_ids
    assert "blue2" in own_ids


def test_fog_of_war_adjacent_enemy_visible():
    gs = make_game_state()
    cmd = make_commander("bcmd1", Side.BLUE, "blue1")
    agent = BattalionCommander(commander=cmd, llm_config={})

    visible = agent._apply_fog_of_war(gs)
    enemy_ids = {u.id for u in visible["known_enemy"]}
    # red1 is at (0,1), adjacent to blue1 at (0,0) -> within 2 hex radius
    assert "red1" in enemy_ids


def test_fog_of_war_distant_enemy_hidden():
    gs = make_game_state()
    cmd = make_commander("bcmd1", Side.BLUE, "blue1")
    agent = BattalionCommander(commander=cmd, llm_config={})

    visible = agent._apply_fog_of_war(gs)
    enemy_ids = {u.id for u in visible["known_enemy"]}
    # red2 is at (5,5), far from all blue units -> hidden
    assert "red2" not in enemy_ids


# ---------------------------------------------------------------------------
# 2. BaseCommander._build_context: all required keys present
# ---------------------------------------------------------------------------

def test_build_context_required_keys():
    gs = make_game_state()
    agent = make_blue_battalion_commander()
    visible = agent._apply_fog_of_war(gs)
    ctx = agent._build_context(visible, {}, gs)

    assert "turn" in ctx
    assert "commander" in ctx
    assert "own_units" in ctx
    assert "known_enemy" in ctx
    assert "relationships" in ctx
    assert "recent_memory" in ctx
    assert "orders_from_superior" in ctx


def test_build_context_turn_value():
    gs = make_game_state()
    gs.turn = 5
    agent = make_blue_battalion_commander()
    visible = agent._apply_fog_of_war(gs)
    ctx = agent._build_context(visible, {}, gs)
    assert ctx["turn"] == 5


# ---------------------------------------------------------------------------
# 3. BaseCommander._parse_actions: valid JSON -> MilitaryAction list
# ---------------------------------------------------------------------------

def test_parse_actions_valid_json():
    agent = make_blue_battalion_commander()
    payload = json.dumps([{
        "unit_id": "blue1",
        "action_type": "HOLD",
        "target_hex": None,
        "target_unit_id": None,
        "priority": 2,
        "reasoning": "testing",
    }])
    actions = agent._parse_actions(payload, turn=1)
    assert len(actions) == 1
    assert isinstance(actions[0], MilitaryAction)
    assert actions[0].action_type == ActionType.HOLD
    assert actions[0].unit_id == "blue1"


def test_parse_actions_with_target_hex():
    agent = make_blue_battalion_commander()
    payload = json.dumps([{
        "unit_id": "blue1",
        "action_type": "MOVE",
        "target_hex": {"q": 2, "r": 3},
        "priority": 1,
        "reasoning": "move forward",
    }])
    actions = agent._parse_actions(payload, turn=2)
    assert actions[0].target_hex == HexCoord(q=2, r=3)


def test_parse_actions_markdown_code_block():
    agent = make_blue_battalion_commander()
    payload = '```json\n[{"unit_id": "blue1", "action_type": "DEFEND", "priority": 3}]\n```'
    actions = agent._parse_actions(payload, turn=1)
    assert len(actions) == 1
    assert actions[0].action_type == ActionType.DEFEND


def test_parse_actions_resets_failure_counter():
    agent = make_blue_battalion_commander()
    agent._consecutive_failures = 2
    payload = json.dumps([{"unit_id": "blue1", "action_type": "HOLD", "priority": 3}])
    agent._parse_actions(payload, turn=1)
    assert agent._consecutive_failures == 0


# ---------------------------------------------------------------------------
# 4. BaseCommander._parse_actions: invalid JSON -> empty list, failure counter
# ---------------------------------------------------------------------------

def test_parse_actions_invalid_json_returns_empty():
    agent = make_blue_battalion_commander()
    actions = agent._parse_actions("this is not json", turn=1)
    assert actions == []


def test_parse_actions_invalid_json_increments_counter():
    agent = make_blue_battalion_commander()
    assert agent._consecutive_failures == 0
    agent._parse_actions("bad json", turn=1)
    assert agent._consecutive_failures == 1


# ---------------------------------------------------------------------------
# 5. BaseCommander._parse_actions: 3 failures -> fallback_mode = True
# ---------------------------------------------------------------------------

def test_parse_actions_three_failures_triggers_fallback():
    agent = make_blue_battalion_commander()
    for _ in range(3):
        agent._parse_actions("bad json", turn=1)
    assert agent._fallback_mode is True


# ---------------------------------------------------------------------------
# 6. BaseCommander.receive_orders: stores OrderDirective
# ---------------------------------------------------------------------------

def test_receive_orders_stores_directive():
    agent = make_blue_battalion_commander()
    assert agent._current_orders is None

    order = OrderDirective(
        order_id="o1", turn=1, issuer_id="tcmd1",
        target_unit_id="blue1", mission=MissionType.ATTACK,
        priority=2,
    )
    agent.receive_orders(order)
    assert agent._current_orders is order
    assert agent._get_superior_orders() is order


# ---------------------------------------------------------------------------
# 7. TheaterCommander.decide (no LLM): falls back to DEFEND all units
# ---------------------------------------------------------------------------

def test_theater_decide_no_llm_fallback():
    gs = make_game_state()
    agent = make_blue_theater_commander()
    # _client is None, so LLM call returns None -> fallback
    orders = agent.decide(gs)
    assert len(orders) > 0
    for o in orders:
        assert isinstance(o, OrderDirective)
        assert o.mission == MissionType.DEFEND


# ---------------------------------------------------------------------------
# 8. TheaterCommander._parse_orders: valid JSON -> OrderDirective list
# ---------------------------------------------------------------------------

def test_theater_parse_orders_valid_json():
    agent = make_blue_theater_commander()
    payload = json.dumps([{
        "target_unit_id": "blue1",
        "mission": "ATTACK",
        "objective_hex": {"q": 3, "r": 4},
        "priority": 2,
        "reasoning": "push forward",
    }])
    orders = agent._parse_orders(payload, turn=1)
    assert len(orders) == 1
    assert isinstance(orders[0], OrderDirective)
    assert orders[0].mission == MissionType.ATTACK
    assert orders[0].objective_hex == HexCoord(q=3, r=4)
    assert orders[0].target_unit_id == "blue1"


def test_theater_parse_orders_no_objective_hex():
    agent = make_blue_theater_commander()
    payload = json.dumps([{
        "target_unit_id": "blue2",
        "mission": "DEFEND",
        "objective_hex": None,
        "priority": 3,
        "reasoning": "hold position",
    }])
    orders = agent._parse_orders(payload, turn=1)
    assert orders[0].objective_hex is None


def test_theater_parse_orders_invalid_json_returns_empty():
    agent = make_blue_theater_commander()
    orders = agent._parse_orders("garbage", turn=1)
    assert orders == []


# ---------------------------------------------------------------------------
# 9. TheaterCommander._fallback_orders: DEFEND for all active units
# ---------------------------------------------------------------------------

def test_theater_fallback_orders_defend_all_active():
    gs = make_game_state()
    agent = make_blue_theater_commander()
    orders = agent._fallback_orders(gs)

    target_ids = {o.target_unit_id for o in orders}
    assert "blue1" in target_ids
    assert "blue2" in target_ids
    for o in orders:
        assert o.mission == MissionType.DEFEND


def test_theater_fallback_orders_excludes_destroyed():
    gs = make_game_state()
    gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0, status=UnitStatus.DESTROYED)
    agent = make_blue_theater_commander()
    orders = agent._fallback_orders(gs)

    target_ids = {o.target_unit_id for o in orders}
    assert "blue1" not in target_ids
    assert "blue2" in target_ids


# ---------------------------------------------------------------------------
# 10. BattalionCommander.decide (no LLM): uses RuleBasedFallback
# ---------------------------------------------------------------------------

def test_battalion_decide_no_llm_uses_fallback():
    gs = make_game_state()
    agent = make_blue_battalion_commander()
    # _client is None, so LLM returns None; fallback is used
    actions = agent.decide(gs)
    assert len(actions) > 0
    for a in actions:
        assert isinstance(a, MilitaryAction)


def test_battalion_decide_destroyed_unit_returns_empty():
    gs = make_game_state()
    gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0, status=UnitStatus.DESTROYED)
    agent = make_blue_battalion_commander()
    actions = agent.decide(gs)
    assert actions == []


# ---------------------------------------------------------------------------
# 11. BattalionCommander.decide with mock LLM returning valid JSON -> parsed
# ---------------------------------------------------------------------------

def test_battalion_decide_mock_llm_valid_json():
    gs = make_game_state()
    agent = make_blue_battalion_commander()

    llm_response = json.dumps([{
        "unit_id": "blue1",
        "action_type": "HOLD",
        "target_hex": None,
        "priority": 3,
        "reasoning": "mocked",
    }])

    with patch.object(agent, "_call_llm", return_value=llm_response):
        actions = agent.decide(gs)

    assert len(actions) == 1
    assert actions[0].action_type == ActionType.HOLD
    assert actions[0].unit_id == "blue1"


# ---------------------------------------------------------------------------
# 12. BattalionCommander.decide with mock LLM returning garbage -> fallback
# ---------------------------------------------------------------------------

def test_battalion_decide_mock_llm_garbage_uses_fallback():
    gs = make_game_state()
    agent = make_blue_battalion_commander()

    with patch.object(agent, "_call_llm", return_value="not json at all"):
        actions = agent.decide(gs)

    # Fallback should produce actions
    assert len(actions) > 0
    # All should still be MilitaryAction instances
    for a in actions:
        assert isinstance(a, MilitaryAction)


# ---------------------------------------------------------------------------
# 13. BattalionCommander: 3 consecutive failures -> permanent fallback mode
# ---------------------------------------------------------------------------

def test_battalion_three_failures_permanent_fallback():
    gs = make_game_state()
    agent = make_blue_battalion_commander()

    with patch.object(agent, "_call_llm", return_value="bad json"):
        for _ in range(3):
            agent.decide(gs)

    assert agent._fallback_mode is True


def test_battalion_in_fallback_mode_skips_llm():
    gs = make_game_state()
    agent = make_blue_battalion_commander()
    agent._fallback_mode = True

    with patch.object(agent, "_call_llm") as mock_llm:
        actions = agent.decide(gs)
        mock_llm.assert_not_called()

    assert len(actions) > 0


# ---------------------------------------------------------------------------
# 14. Memory updated after decide call
# ---------------------------------------------------------------------------

def test_battalion_memory_updated_after_decide():
    gs = make_game_state()
    agent = make_blue_battalion_commander()

    assert len(agent.memory.recent) == 0
    agent.decide(gs)
    assert len(agent.memory.recent) == 1


def test_theater_memory_updated_after_decide_with_mock_llm():
    gs = make_game_state()
    agent = make_blue_theater_commander()

    llm_response = json.dumps([{
        "target_unit_id": "blue1",
        "mission": "DEFEND",
        "objective_hex": None,
        "priority": 3,
        "reasoning": "mocked theater order",
    }])

    assert len(agent.memory.recent) == 0
    with patch.object(agent, "_call_llm", return_value=llm_response):
        agent.decide(gs)
    assert len(agent.memory.recent) == 1


def test_battalion_memory_records_action_types():
    gs = make_game_state()
    agent = make_blue_battalion_commander()
    agent.decide(gs)

    record = list(agent.memory.recent)[0]
    assert record["turn"] == gs.turn
    assert isinstance(record["actions"], list)
