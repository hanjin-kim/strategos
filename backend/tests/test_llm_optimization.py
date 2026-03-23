from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from app.models.domain import (
    Commander, Unit, Side, UnitType, UnitSize, UnitStatus,
    HexCoord, TerrainHex, TerrainType, Force,
)
from app.models.actions import MilitaryAction, ActionType, OrderDirective, MissionType
from app.engine.game_state import GameState
from app.engine.constraint_engine import ConstraintEngine
from app.engine.combat_resolver import CombatResolver
from app.engine.movement_engine import MovementEngine
from app.engine.turn_manager import TurnManager
from app.agents.base_commander import BaseCommander, DOCTRINE_PROMPT
from app.agents.theater_commander import TheaterCommander
from app.agents.battalion_commander import BattalionCommander
from app.agents.division_commander import DivisionCommander


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


def make_commander(cid: str, side: Side, unit_id: str, rank: str = "Battalion") -> Commander:
    return Commander(id=cid, name=f"CMD-{cid}", side=side, rank=rank, unit_id=unit_id)


def make_game_state() -> GameState:
    gs = GameState()
    for q in range(-1, 6):
        for r in range(-1, 6):
            coord = HexCoord(q=q, r=r)
            gs.terrain[coord] = TerrainHex(
                coord=coord,
                terrain_type=TerrainType.PLAIN,
                elevation=0,
                movement_cost=1,
                defense_modifier=1.0,
            )
    gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0)
    gs.units["blue2"] = make_unit("blue2", Side.BLUE, 1, 0)
    gs.units["red1"] = make_unit("red1", Side.RED, 3, 0)
    gs.units["red2"] = make_unit("red2", Side.RED, 4, 0)

    gs.commanders["tcmd_blue"] = make_commander("tcmd_blue", Side.BLUE, "blue1", "Theater")
    gs.commanders["bcmd_blue1"] = make_commander("bcmd_blue1", Side.BLUE, "blue1")
    gs.commanders["bcmd_blue2"] = make_commander("bcmd_blue2", Side.BLUE, "blue2")
    gs.commanders["tcmd_red"] = make_commander("tcmd_red", Side.RED, "red1", "Theater")
    gs.commanders["bcmd_red1"] = make_commander("bcmd_red1", Side.RED, "red1")
    gs.commanders["bcmd_red2"] = make_commander("bcmd_red2", Side.RED, "red2")

    gs.forces[Side.BLUE] = Force(
        side=Side.BLUE, name="Blue Force",
        commander_ids=["tcmd_blue", "bcmd_blue1", "bcmd_blue2"],
        unit_ids=["blue1", "blue2"],
    )
    gs.forces[Side.RED] = Force(
        side=Side.RED, name="Red Force",
        commander_ids=["tcmd_red", "bcmd_red1", "bcmd_red2"],
        unit_ids=["red1", "red2"],
    )
    return gs


def make_agents(gs: GameState) -> dict:
    """Agents with llm_config={} so _client=None, triggering fallback."""
    return {
        "tcmd_blue": TheaterCommander(commander=gs.commanders["tcmd_blue"], llm_config={}),
        "bcmd_blue1": BattalionCommander(commander=gs.commanders["bcmd_blue1"], llm_config={}),
        "bcmd_blue2": BattalionCommander(commander=gs.commanders["bcmd_blue2"], llm_config={}),
        "tcmd_red": TheaterCommander(commander=gs.commanders["tcmd_red"], llm_config={}),
        "bcmd_red1": BattalionCommander(commander=gs.commanders["bcmd_red1"], llm_config={}),
        "bcmd_red2": BattalionCommander(commander=gs.commanders["bcmd_red2"], llm_config={}),
    }


def make_turn_manager(gs: GameState, agents: dict, log_dir: str = "/tmp/test_llm_opt_logs") -> TurnManager:
    return TurnManager(
        game_state=gs,
        agents=agents,
        constraint_engine=ConstraintEngine(),
        combat_resolver=CombatResolver(rng_seed=42),
        movement_engine=MovementEngine(),
        simulation_id="test-llm-opt",
        log_dir=log_dir,
    )


# ---------------------------------------------------------------------------
# 1. DOCTRINE_PROMPT is a non-empty string
# ---------------------------------------------------------------------------

def test_doctrine_prompt_is_nonempty_string():
    assert isinstance(DOCTRINE_PROMPT, str)
    assert len(DOCTRINE_PROMPT) > 0


# ---------------------------------------------------------------------------
# 2. _build_cached_system_prompt returns same string on repeated calls
# ---------------------------------------------------------------------------

def test_cached_system_prompt_returns_same_object_on_repeat():
    cmd = make_commander("c1", Side.BLUE, "u1")
    agent = BattalionCommander(commander=cmd, llm_config={})
    first = agent._build_cached_system_prompt()
    second = agent._build_cached_system_prompt()
    assert first is second  # exact same object (cached)


# ---------------------------------------------------------------------------
# 3. _build_cached_system_prompt includes both doctrine AND persona
# ---------------------------------------------------------------------------

def test_cached_system_prompt_includes_doctrine_and_persona():
    cmd = make_commander("c1", Side.BLUE, "u1")
    agent = BattalionCommander(commander=cmd, llm_config={})
    prompt = agent._build_cached_system_prompt()
    # Doctrine portion
    assert "MILITARY DOCTRINE" in prompt
    # Persona portion (battalion-specific)
    assert "Battalion Commander" in prompt
    assert "BLUE" in prompt


# ---------------------------------------------------------------------------
# 4. invalidate_cache forces a rebuild
# ---------------------------------------------------------------------------

def test_invalidate_cache_forces_rebuild():
    cmd = make_commander("c1", Side.BLUE, "u1")
    agent = BattalionCommander(commander=cmd, llm_config={})
    first = agent._build_cached_system_prompt()
    agent.invalidate_cache()
    assert agent._cached_system_prompt is None
    second = agent._build_cached_system_prompt()
    # After rebuild, content is the same but it was actually re-built
    assert first == second
    assert second is not first  # new object after rebuild


# ---------------------------------------------------------------------------
# 5. _call_agents_parallel with empty list returns empty results
# ---------------------------------------------------------------------------

def test_call_agents_parallel_empty_list():
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents)
    result = tm._call_agents_parallel([], gs)
    assert result == []


# ---------------------------------------------------------------------------
# 6. _call_agents_parallel with single agent calls directly (no thread)
# ---------------------------------------------------------------------------

def test_call_agents_parallel_single_agent_direct_call():
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents)
    tm.game_state.advance_turn()

    agent = agents["bcmd_blue1"]
    called = []
    original_decide = agent.decide

    def mock_decide(state):
        called.append("called")
        return original_decide(state)

    agent.decide = mock_decide

    with patch("app.engine.turn_manager.ThreadPoolExecutor") as mock_executor:
        result = tm._call_agents_parallel([agent], gs)
        # ThreadPoolExecutor should NOT be called for single agent
        mock_executor.assert_not_called()

    assert "called" in called


# ---------------------------------------------------------------------------
# 7. _call_agents_parallel with multiple agents collects all results
# ---------------------------------------------------------------------------

def test_call_agents_parallel_multiple_agents_all_results():
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents)
    tm.game_state.advance_turn()

    bn_agents = [agents["bcmd_blue1"], agents["bcmd_blue2"]]
    results = tm._call_agents_parallel(bn_agents, gs)
    # Both agents should have contributed results (may be empty in fallback, but no crash)
    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# 8. _call_agents_parallel handles agent failure gracefully
# ---------------------------------------------------------------------------

def test_call_agents_parallel_handles_agent_failure():
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents)
    tm.game_state.advance_turn()

    # Create two mock agents — one raises, one succeeds
    good_agent = MagicMock()
    good_action = MagicMock(spec=MilitaryAction)
    good_agent.decide.return_value = [good_action]
    good_agent.commander.id = "good"

    bad_agent = MagicMock()
    bad_agent.decide.side_effect = RuntimeError("LLM timeout")
    bad_agent.commander.id = "bad"

    results = tm._call_agents_parallel([good_agent, bad_agent], gs)
    # Should include the good agent's result, not crash
    assert good_action in results


# ---------------------------------------------------------------------------
# 9. _command_phase works with 2-tier (no division) — backward compat
# ---------------------------------------------------------------------------

def test_command_phase_2tier_backward_compat():
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents)
    tm.game_state.advance_turn()

    # No division commanders in agents — should fall back to 2-tier
    division_agents = [a for a in agents.values() if isinstance(a, DivisionCommander)]
    assert len(division_agents) == 0

    actions = tm._command_phase()
    assert isinstance(actions, list)


# ---------------------------------------------------------------------------
# 10. _command_phase works with 3-tier
# ---------------------------------------------------------------------------

def test_command_phase_3tier_works():
    gs = make_game_state()
    # Add division commander
    gs.commanders["dcmd_blue"] = make_commander("dcmd_blue", Side.BLUE, "blue1", "Division")
    agents = make_agents(gs)
    div_agent = DivisionCommander(
        commander=gs.commanders["dcmd_blue"],
        llm_config={},
    )
    agents["dcmd_blue"] = div_agent

    tm = make_turn_manager(gs, agents)
    tm.game_state.advance_turn()

    actions = tm._command_phase()
    assert isinstance(actions, list)


# ---------------------------------------------------------------------------
# 11. Theater agents for both sides are called
# ---------------------------------------------------------------------------

def test_command_phase_both_theater_agents_called():
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents)
    tm.game_state.advance_turn()

    blue_theater = agents["tcmd_blue"]
    red_theater = agents["tcmd_red"]
    blue_called = []
    red_called = []

    orig_blue = blue_theater.decide
    orig_red = red_theater.decide

    def mock_blue_decide(state):
        blue_called.append(True)
        return orig_blue(state)

    def mock_red_decide(state):
        red_called.append(True)
        return orig_red(state)

    blue_theater.decide = mock_blue_decide
    red_theater.decide = mock_red_decide

    tm._command_phase()

    assert len(blue_called) >= 1
    assert len(red_called) >= 1


# ---------------------------------------------------------------------------
# 12. Theater order distribution to battalions still works
# ---------------------------------------------------------------------------

def test_theater_orders_distributed_to_battalions():
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents)
    tm.game_state.advance_turn()

    # Patch theater to emit a specific order targeting blue1
    blue_theater = agents["tcmd_blue"]
    order = OrderDirective(
        order_id="ord-1",
        turn=1,
        issuer_id="tcmd_blue",
        target_unit_id="blue1",
        mission=MissionType.ATTACK,
        priority=2,
    )
    blue_theater.decide = lambda gs: [order]

    tm._command_phase()

    # bcmd_blue1 commands blue1, should have received the order
    assert agents["bcmd_blue1"]._current_orders is not None


# ---------------------------------------------------------------------------
# 13. Validation still applied per side
# ---------------------------------------------------------------------------

def test_validation_applied_per_side():
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents)
    tm.game_state.advance_turn()

    validate_calls = []
    original_validate = tm.constraint_engine.validate

    def tracking_validate(actions, state, authority_map=None):
        validate_calls.append(len(actions))
        return original_validate(actions, state, authority_map=authority_map)

    tm.constraint_engine.validate = tracking_validate

    tm._command_phase()
    # Should be called twice — once per side
    assert len(validate_calls) == 2


# ---------------------------------------------------------------------------
# 14. _get_action_side returns correct side
# ---------------------------------------------------------------------------

def test_get_action_side_blue():
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents)
    tm.game_state.advance_turn()

    action = MagicMock()
    action.unit_id = "blue1"
    assert tm._get_action_side(action) == Side.BLUE


def test_get_action_side_red():
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents)
    tm.game_state.advance_turn()

    action = MagicMock()
    action.unit_id = "red1"
    assert tm._get_action_side(action) == Side.RED


def test_get_action_side_unknown_defaults_blue():
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents)

    action = MagicMock()
    action.unit_id = "nonexistent"
    assert tm._get_action_side(action) == Side.BLUE


# ---------------------------------------------------------------------------
# 15. Full turn with parallel command phase completes
# ---------------------------------------------------------------------------

def test_full_turn_with_parallel_command_phase():
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents)

    result = tm._run_turn(1)
    assert result is not None
    assert result.turn == 1
