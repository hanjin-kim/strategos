from __future__ import annotations
import json
import pytest
from unittest.mock import patch, MagicMock
from app.models.domain import (
    Commander, Unit, Side, UnitType, UnitSize, UnitStatus, HexCoord, Force,
)
from app.models.actions import OrderDirective, MissionType, MilitaryAction, ActionType
from app.engine.game_state import GameState
from app.agents.division_commander import DivisionCommander
from app.agents.theater_commander import TheaterCommander
from app.agents.battalion_commander import BattalionCommander
from app.graph.graph_tools import GraphTools
from app.graph.relationship_graph import RelationshipGraph
from app.graph.military_ontology import EntityType, RelationType
from app.engine.turn_manager import TurnManager
from app.engine.constraint_engine import ConstraintEngine
from app.engine.combat_resolver import CombatResolver
from app.engine.movement_engine import MovementEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_unit(uid: str, side: Side, q: int = 0, r: int = 0) -> Unit:
    return Unit(
        id=uid, name=f"Unit-{uid}", side=side,
        unit_type=UnitType.INFANTRY, size=UnitSize.BATTALION,
        position=HexCoord(q=q, r=r),
        strength=1.0, morale=0.8,
        movement_points=2, max_movement_points=2,
        attack_power=10.0, defense_power=10.0,
        effective_range=1, ammo=1.0, fuel=1.0,
        status=UnitStatus.ACTIVE,
    )


def make_commander(cid: str, side: Side, unit_id: str, rank: str = "Division") -> Commander:
    return Commander(id=cid, name=f"CMD-{cid}", side=side, rank=rank, unit_id=unit_id)


def make_graph_with_division(
    div_cmd_id: str,
    controlled_unit_ids: list[str],
) -> tuple[RelationshipGraph, GraphTools]:
    """Create a RelationshipGraph where div_cmd_id COMMANDS each unit in controlled_unit_ids."""
    rg = RelationshipGraph()
    rg.add_entity(div_cmd_id, EntityType.COMMANDER)
    for uid in controlled_unit_ids:
        rg.add_entity(uid, EntityType.UNIT)
        rg.add_relationship(div_cmd_id, uid, RelationType.COMMANDS)
    return rg, GraphTools(rg)


def make_game_state_with_units(unit_ids: list[str], side: Side = Side.BLUE) -> GameState:
    gs = GameState()
    gs.turn = 1
    for i, uid in enumerate(unit_ids):
        gs.units[uid] = make_unit(uid, side, q=i, r=0)
    gs.forces[side] = Force(side=side, name=f"{side.value} Force", unit_ids=unit_ids)
    return gs


# ---------------------------------------------------------------------------
# 1. DivisionCommander instantiation
# ---------------------------------------------------------------------------

def test_division_commander_instantiation():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    agent = DivisionCommander(commander=cmd, llm_config={})
    assert agent.commander.id == "dcmd1"
    assert agent._fallback_mode is False
    assert agent._consecutive_failures == 0
    assert agent._client is None


def test_division_commander_instantiation_with_graph():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1", "blue2"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)
    assert agent.graph_tools is gt


# ---------------------------------------------------------------------------
# 2. _build_persona includes command authority
# ---------------------------------------------------------------------------

def test_build_persona_includes_unit_ids():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1", "blue2"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)
    persona = agent._build_persona()
    assert "blue1" in persona or "blue2" in persona
    assert "Division Commander" in persona
    assert "BLUE" in persona


def test_build_persona_no_graph_tools():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    agent = DivisionCommander(commander=cmd, llm_config={})
    persona = agent._build_persona()
    assert "Division Commander" in persona
    # Should not crash without graph_tools
    assert isinstance(persona, str)


# ---------------------------------------------------------------------------
# 3. _fallback_orders generates DEFEND for all controlled units
# ---------------------------------------------------------------------------

def test_fallback_orders_generates_defend():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1", "blue2"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)
    gs = make_game_state_with_units(["blue1", "blue2"])

    orders = agent._fallback_orders(gs)
    assert len(orders) == 2
    for o in orders:
        assert isinstance(o, OrderDirective)
        assert o.mission == MissionType.DEFEND
        assert o.issuer_id == "dcmd1"


def test_fallback_orders_covers_all_controlled_units():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1", "blue2", "blue3"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)
    gs = make_game_state_with_units(["blue1", "blue2", "blue3"])

    orders = agent._fallback_orders(gs)
    target_ids = {o.target_unit_id for o in orders}
    assert target_ids == {"blue1", "blue2", "blue3"}


def test_fallback_orders_no_graph_returns_empty():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    agent = DivisionCommander(commander=cmd, llm_config={})
    gs = make_game_state_with_units(["blue1"])

    orders = agent._fallback_orders(gs)
    assert orders == []


def test_fallback_orders_none_game_state():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)

    orders = agent._fallback_orders(None)
    assert len(orders) == 1
    assert orders[0].turn == 0


# ---------------------------------------------------------------------------
# 4. _parse_order_directives with valid JSON
# ---------------------------------------------------------------------------

def test_parse_order_directives_valid_json():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1", "blue2"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)

    payload = json.dumps([{
        "target_unit_id": "blue1",
        "mission": "ATTACK",
        "objective_hex": {"q": 3, "r": 4},
        "priority": 2,
        "reasoning": "advance",
    }])
    orders = agent._parse_order_directives(payload, turn=1)
    assert len(orders) == 1
    assert orders[0].mission == MissionType.ATTACK
    assert orders[0].objective_hex == HexCoord(q=3, r=4)
    assert orders[0].target_unit_id == "blue1"
    assert orders[0].issuer_id == "dcmd1"


def test_parse_order_directives_no_objective_hex():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)

    payload = json.dumps([{
        "target_unit_id": "blue1",
        "mission": "DEFEND",
        "objective_hex": None,
        "priority": 3,
        "reasoning": "hold",
    }])
    orders = agent._parse_order_directives(payload, turn=1)
    assert orders[0].objective_hex is None


def test_parse_order_directives_markdown_code_block():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)

    payload = '```json\n[{"target_unit_id": "blue1", "mission": "DEFEND", "priority": 3}]\n```'
    orders = agent._parse_order_directives(payload, turn=1)
    assert len(orders) == 1
    assert orders[0].mission == MissionType.DEFEND


def test_parse_order_directives_resets_failure_counter():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)
    agent._consecutive_failures = 2

    payload = json.dumps([{"target_unit_id": "blue1", "mission": "DEFEND", "priority": 3}])
    agent._parse_order_directives(payload, turn=1)
    assert agent._consecutive_failures == 0


# ---------------------------------------------------------------------------
# 5. _parse_order_directives filters out-of-scope units
# ---------------------------------------------------------------------------

def test_parse_order_directives_filters_out_of_scope():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    # Only blue1 is in scope
    _, gt = make_graph_with_division("dcmd1", ["blue1"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)

    payload = json.dumps([
        {"target_unit_id": "blue1", "mission": "ATTACK", "priority": 2},
        {"target_unit_id": "blue2", "mission": "DEFEND", "priority": 3},  # out of scope
    ])
    orders = agent._parse_order_directives(payload, turn=1)
    assert len(orders) == 1
    assert orders[0].target_unit_id == "blue1"


# ---------------------------------------------------------------------------
# 6. _parse_order_directives with malformed JSON -> fallback mode
# ---------------------------------------------------------------------------

def test_parse_order_directives_malformed_json_increments_failure():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)

    agent._parse_order_directives("not valid json", turn=1)
    assert agent._consecutive_failures == 1


def test_parse_order_directives_three_failures_triggers_fallback():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)

    for _ in range(3):
        agent._parse_order_directives("bad json", turn=1)
    assert agent._fallback_mode is True


# ---------------------------------------------------------------------------
# 7. decide() with mock LLM
# ---------------------------------------------------------------------------

def test_decide_mock_llm_valid_json():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1", "blue2"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)
    gs = make_game_state_with_units(["blue1", "blue2"])

    llm_response = json.dumps([
        {"target_unit_id": "blue1", "mission": "ATTACK", "priority": 2, "reasoning": "push"},
        {"target_unit_id": "blue2", "mission": "DEFEND", "priority": 3, "reasoning": "hold"},
    ])

    with patch.object(agent, "_call_llm", return_value=llm_response):
        orders = agent.decide(gs)

    assert len(orders) == 2
    missions = {o.target_unit_id: o.mission for o in orders}
    assert missions["blue1"] == MissionType.ATTACK
    assert missions["blue2"] == MissionType.DEFEND


def test_decide_no_llm_falls_back_to_defend():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1", "blue2"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)
    gs = make_game_state_with_units(["blue1", "blue2"])

    # _client is None, so _call_llm returns None -> fallback
    orders = agent.decide(gs)
    assert len(orders) == 2
    for o in orders:
        assert o.mission == MissionType.DEFEND


def test_decide_in_fallback_mode_skips_llm():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)
    agent._fallback_mode = True
    gs = make_game_state_with_units(["blue1"])

    with patch.object(agent, "_call_llm") as mock_llm:
        orders = agent.decide(gs)
        mock_llm.assert_not_called()

    assert len(orders) == 1


def test_decide_memory_updated_after_successful_llm():
    cmd = make_commander("dcmd1", Side.BLUE, "blue1")
    _, gt = make_graph_with_division("dcmd1", ["blue1"])
    agent = DivisionCommander(commander=cmd, llm_config={}, graph_tools=gt)
    gs = make_game_state_with_units(["blue1"])

    llm_response = json.dumps([
        {"target_unit_id": "blue1", "mission": "DEFEND", "priority": 3},
    ])

    assert len(agent.memory.recent) == 0
    with patch.object(agent, "_call_llm", return_value=llm_response):
        agent.decide(gs)
    assert len(agent.memory.recent) == 1


# ---------------------------------------------------------------------------
# 8. Integration: _command_phase 3-tier flow (Theater->Division->Battalion)
# ---------------------------------------------------------------------------

def make_3tier_setup(tmp_path):
    """Build a minimal 3-tier scenario: Theater -> Division -> Battalion."""
    gs = GameState()
    gs.turn = 1
    from app.models.domain import TerrainHex, TerrainType
    for q in range(-1, 6):
        for r in range(-1, 6):
            from app.models.domain import TerrainHex, TerrainType
            gs.terrain[HexCoord(q=q, r=r)] = TerrainHex(
                coord=HexCoord(q=q, r=r), terrain_type=TerrainType.PLAIN,
                elevation=0, movement_cost=1, defense_modifier=1.0,
            )

    gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0)
    gs.units["red1"] = make_unit("red1", Side.RED, 4, 0)
    gs.forces[Side.BLUE] = Force(side=Side.BLUE, name="Blue", unit_ids=["blue1"])
    gs.forces[Side.RED] = Force(side=Side.RED, name="Red", unit_ids=["red1"])

    gs.commanders["tcmd_blue"] = Commander(
        id="tcmd_blue", name="Blue Theater", side=Side.BLUE, rank="Theater", unit_id="blue1"
    )
    gs.commanders["dcmd_blue"] = Commander(
        id="dcmd_blue", name="Blue Division", side=Side.BLUE, rank="Division", unit_id="blue1"
    )
    gs.commanders["bcmd_blue"] = Commander(
        id="bcmd_blue", name="Blue Bn", side=Side.BLUE, rank="Battalion", unit_id="blue1"
    )
    gs.commanders["tcmd_red"] = Commander(
        id="tcmd_red", name="Red Theater", side=Side.RED, rank="Theater", unit_id="red1"
    )
    gs.commanders["bcmd_red"] = Commander(
        id="bcmd_red", name="Red Bn", side=Side.RED, rank="Battalion", unit_id="red1"
    )

    # Build graph: division commands blue1
    rg = RelationshipGraph()
    rg.add_entity("dcmd_blue", EntityType.COMMANDER)
    rg.add_entity("blue1", EntityType.UNIT)
    rg.add_relationship("dcmd_blue", "blue1", RelationType.COMMANDS)
    gt = GraphTools(rg)

    agents = {
        "tcmd_blue": TheaterCommander(commander=gs.commanders["tcmd_blue"], llm_config={}),
        "dcmd_blue": DivisionCommander(commander=gs.commanders["dcmd_blue"], llm_config={}, graph_tools=gt),
        "bcmd_blue": BattalionCommander(commander=gs.commanders["bcmd_blue"], llm_config={}),
        "tcmd_red": TheaterCommander(commander=gs.commanders["tcmd_red"], llm_config={}),
        "bcmd_red": BattalionCommander(commander=gs.commanders["bcmd_red"], llm_config={}),
    }

    tm = TurnManager(
        game_state=gs,
        agents=agents,
        constraint_engine=ConstraintEngine(),
        combat_resolver=CombatResolver(rng_seed=42),
        movement_engine=MovementEngine(),
        simulation_id="test-3tier",
        log_dir=str(tmp_path / "logs"),
    )
    return tm, gs, agents


def test_command_phase_3tier_produces_actions(tmp_path):
    tm, gs, agents = make_3tier_setup(tmp_path)
    gs.advance_turn()
    actions = tm._command_phase()
    assert isinstance(actions, list)
    for a in actions:
        assert isinstance(a, MilitaryAction)


def test_command_phase_3tier_division_receives_theater_order(tmp_path):
    tm, gs, agents = make_3tier_setup(tmp_path)
    gs.advance_turn()

    # Theater issues order targeting blue1; division controls blue1
    # so division agent should receive that order
    theater_order = OrderDirective(
        order_id="t1", turn=1, issuer_id="tcmd_blue",
        target_unit_id="blue1", mission=MissionType.ATTACK, priority=2,
    )

    div_agent = agents["dcmd_blue"]
    div_gt = div_agent.graph_tools
    scope = div_gt.query_command_scope("dcmd_blue")
    assert "blue1" in scope["commanded_unit_ids"]


# ---------------------------------------------------------------------------
# 9. Integration: _command_phase 2-tier fallback (no Division, Phase 1 behavior)
# ---------------------------------------------------------------------------

def test_command_phase_2tier_no_division_works(tmp_path):
    """Without DivisionCommanders, existing 2-tier flow is unchanged."""
    from app.models.domain import TerrainHex, TerrainType
    gs = GameState()
    gs.turn = 1
    for q in range(-1, 6):
        for r in range(-1, 6):
            gs.terrain[HexCoord(q=q, r=r)] = TerrainHex(
                coord=HexCoord(q=q, r=r), terrain_type=TerrainType.PLAIN,
                elevation=0, movement_cost=1, defense_modifier=1.0,
            )

    gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0)
    gs.units["red1"] = make_unit("red1", Side.RED, 4, 0)
    gs.forces[Side.BLUE] = Force(side=Side.BLUE, name="Blue", unit_ids=["blue1"])
    gs.forces[Side.RED] = Force(side=Side.RED, name="Red", unit_ids=["red1"])
    gs.commanders["tcmd_blue"] = Commander(
        id="tcmd_blue", name="Blue Theater", side=Side.BLUE, rank="Theater", unit_id="blue1"
    )
    gs.commanders["bcmd_blue"] = Commander(
        id="bcmd_blue", name="Blue Bn", side=Side.BLUE, rank="Battalion", unit_id="blue1"
    )
    gs.commanders["tcmd_red"] = Commander(
        id="tcmd_red", name="Red Theater", side=Side.RED, rank="Theater", unit_id="red1"
    )
    gs.commanders["bcmd_red"] = Commander(
        id="bcmd_red", name="Red Bn", side=Side.RED, rank="Battalion", unit_id="red1"
    )

    # No DivisionCommander in agents
    agents = {
        "tcmd_blue": TheaterCommander(commander=gs.commanders["tcmd_blue"], llm_config={}),
        "bcmd_blue": BattalionCommander(commander=gs.commanders["bcmd_blue"], llm_config={}),
        "tcmd_red": TheaterCommander(commander=gs.commanders["tcmd_red"], llm_config={}),
        "bcmd_red": BattalionCommander(commander=gs.commanders["bcmd_red"], llm_config={}),
    }

    tm = TurnManager(
        game_state=gs,
        agents=agents,
        constraint_engine=ConstraintEngine(),
        combat_resolver=CombatResolver(rng_seed=42),
        movement_engine=MovementEngine(),
        simulation_id="test-2tier",
        log_dir=str(tmp_path / "logs"),
    )
    gs.advance_turn()
    actions = tm._command_phase()

    # Should work without error and produce MilitaryActions
    assert isinstance(actions, list)
    for a in actions:
        assert isinstance(a, MilitaryAction)


# ---------------------------------------------------------------------------
# 10. COMMANDS constraint allows Commander->Commander
# ---------------------------------------------------------------------------

def test_commands_relation_allows_commander_to_commander():
    from app.graph.military_ontology import RELATION_CONSTRAINTS, RelationType, EntityType
    allowed_targets = RELATION_CONSTRAINTS[RelationType.COMMANDS][1]
    assert EntityType.COMMANDER in allowed_targets


def test_commands_relation_still_allows_commander_to_unit():
    from app.graph.military_ontology import RELATION_CONSTRAINTS, RelationType, EntityType
    allowed_targets = RELATION_CONSTRAINTS[RelationType.COMMANDS][1]
    assert EntityType.UNIT in allowed_targets


# ---------------------------------------------------------------------------
# 11. query_command_scope returns correct units for division
# ---------------------------------------------------------------------------

def test_query_command_scope_division_units():
    rg, gt = make_graph_with_division("dcmd1", ["blue1", "blue2"])
    scope = gt.query_command_scope("dcmd1")
    assert set(scope["commanded_unit_ids"]) == {"blue1", "blue2"}
    assert scope["commander_id"] == "dcmd1"


def test_query_command_scope_unknown_commander_returns_empty():
    rg = RelationshipGraph()
    gt = GraphTools(rg)
    scope = gt.query_command_scope("nonexistent")
    assert scope["commanded_unit_ids"] == []


# ---------------------------------------------------------------------------
# 12. Backward compatibility: existing 2-tier scenarios work unchanged
# ---------------------------------------------------------------------------

def test_2tier_simulation_completes(tmp_path):
    """Full simulation with only Theater+Battalion agents must complete without error."""
    from app.models.domain import TerrainHex, TerrainType
    gs = GameState()
    for q in range(-1, 6):
        for r in range(-1, 6):
            gs.terrain[HexCoord(q=q, r=r)] = TerrainHex(
                coord=HexCoord(q=q, r=r), terrain_type=TerrainType.PLAIN,
                elevation=0, movement_cost=1, defense_modifier=1.0,
            )
    gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0)
    gs.units["red1"] = make_unit("red1", Side.RED, 4, 0)
    gs.forces[Side.BLUE] = Force(side=Side.BLUE, name="Blue", unit_ids=["blue1"])
    gs.forces[Side.RED] = Force(side=Side.RED, name="Red", unit_ids=["red1"])
    gs.commanders["tcmd_blue"] = Commander(
        id="tcmd_blue", name="Blue Theater", side=Side.BLUE, rank="Theater", unit_id="blue1"
    )
    gs.commanders["bcmd_blue"] = Commander(
        id="bcmd_blue", name="Blue Bn", side=Side.BLUE, rank="Battalion", unit_id="blue1"
    )
    gs.commanders["tcmd_red"] = Commander(
        id="tcmd_red", name="Red Theater", side=Side.RED, rank="Theater", unit_id="red1"
    )
    gs.commanders["bcmd_red"] = Commander(
        id="bcmd_red", name="Red Bn", side=Side.RED, rank="Battalion", unit_id="red1"
    )
    agents = {
        "tcmd_blue": TheaterCommander(commander=gs.commanders["tcmd_blue"], llm_config={}),
        "bcmd_blue": BattalionCommander(commander=gs.commanders["bcmd_blue"], llm_config={}),
        "tcmd_red": TheaterCommander(commander=gs.commanders["tcmd_red"], llm_config={}),
        "bcmd_red": BattalionCommander(commander=gs.commanders["bcmd_red"], llm_config={}),
    }
    tm = TurnManager(
        game_state=gs, agents=agents,
        constraint_engine=ConstraintEngine(),
        combat_resolver=CombatResolver(rng_seed=42),
        movement_engine=MovementEngine(),
        simulation_id="test-compat",
        log_dir=str(tmp_path / "logs"),
    )
    result = tm.run_simulation(max_turns=3)
    assert result is gs
    assert gs.turn == 3
