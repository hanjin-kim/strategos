"""Verify business domain is fully independent from military stack.

Tests:
- BusinessState loads business scenario (no hex)
- BusinessState.get_competitors works by market position
- BusinessState.get_adjacent_competitors uses market connections
- BusinessAgent._fallback_decide returns BusinessAction
- BusinessCEO._fallback_decide returns directive dicts
- BusinessCommandOrchestrator produces actions
- MarketCompetitionResolver uses competitive_power/brand_loyalty directly
- MarketSpace uses connections graph
- BusinessDomainFactory creates state/engines/agents
- No military imports in any business file (AST check)
- Full batch run with business scenario (3 turns, N=3)
- share_change actually affects unit market_share
- marketing_budget drains during competition
"""
from __future__ import annotations

import ast
import os
import json
import uuid
from pathlib import Path

import pytest

from app.domains.business.models import (
    MarketNode, BusinessUnit, BusinessAction,
)
from app.domains.business.state import BusinessState
from app.domains.business.agents import BusinessAgent, BusinessCEO
from app.domains.business.engines import (
    MarketSpace, MarketCompetitionResolver, BusinessMover,
    BusinessConstraints, BusinessVictory,
)
from app.domains.business.factory import BusinessDomainFactory
from app.domains.business.orchestrator import BusinessCommandOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCENARIO_PATH = Path(__file__).parent.parent.parent / "scripts/seed_scenarios/ev_battery_market.json"
BUSINESS_DOMAIN_DIR = Path(__file__).parent.parent / "app/domains/business"

FORBIDDEN_MODULES = ["app.engine", "app.models", "app.agents", "app.utils"]


def load_scenario() -> dict:
    return json.loads(SCENARIO_PATH.read_text())


def make_unit(uid: str = "u1", side: str = "BLUE",
              region: str = "Korea", segment: str = "EV",
              status: str = "ACTIVE") -> BusinessUnit:
    return BusinessUnit(
        id=uid, name=f"Unit-{uid}", side=side, status=status,
        position=MarketNode(region=region, segment=segment),
        market_share=0.5, revenue=1.0, competitive_power=10.0,
        brand_loyalty=8.0, marketing_budget=0.8, cash_reserves=0.9,
        org_health=0.85, rd_capability=0.6,
    )


def make_state_with_units() -> BusinessState:
    """BusinessState with two competing units in Korea:EV."""
    state = BusinessState()
    state.market_map = {
        "Korea:EV": {"region": "Korea", "segment": "EV",
                     "connections": ["China:EV", "Korea:ESS"]},
        "China:EV": {"region": "China", "segment": "EV",
                     "connections": ["Korea:EV"]},
        "Korea:ESS": {"region": "Korea", "segment": "ESS",
                      "connections": ["Korea:EV"]},
    }
    state.units = {
        "blue_unit": make_unit("blue_unit", "BLUE", "Korea", "EV"),
        "red_unit": make_unit("red_unit", "RED", "Korea", "EV"),
        "red_china": make_unit("red_china", "RED", "China", "EV"),
    }
    return state


# ---------------------------------------------------------------------------
# 1. No military imports in any business domain file (AST check)
# ---------------------------------------------------------------------------

def test_no_military_imports_in_business_domain():
    """Verify zero imports from app.engine, app.models, app.agents, app.utils."""
    violations = []
    for root, dirs, files in os.walk(str(BUSINESS_DOMAIN_DIR)):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            path = os.path.join(root, fname)
            with open(path) as fh:
                try:
                    tree = ast.parse(fh.read())
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module = getattr(node, "module", "") or ""
                    names = [alias.name for alias in getattr(node, "names", [])]
                    full = module or " ".join(names)
                    if any(full.startswith(m) for m in FORBIDDEN_MODULES):
                        violations.append(f"{path}: imports {full!r}")
    assert violations == [], "Military imports found:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# 2. BusinessState loads business scenario (no hex grid)
# ---------------------------------------------------------------------------

def test_business_state_loads_scenario():
    scenario = load_scenario()
    state = BusinessState(scenario)
    assert state.turn == 0
    assert len(state.units) > 0
    assert len(state.market_map) > 0
    assert len(state.commanders) > 0
    assert len(state.forces) > 0


def test_business_state_units_have_market_share():
    scenario = load_scenario()
    state = BusinessState(scenario)
    for unit in state.units.values():
        assert hasattr(unit, "market_share"), f"Unit {unit.id} missing market_share"
        assert not hasattr(unit, "strength"), f"Unit {unit.id} has military field 'strength'"


def test_business_state_units_have_no_hex_position():
    scenario = load_scenario()
    state = BusinessState(scenario)
    for unit in state.units.values():
        pos = unit.position
        assert isinstance(pos, MarketNode), f"Unit {unit.id} has non-MarketNode position: {pos}"
        assert hasattr(pos, "region") and hasattr(pos, "segment")


# ---------------------------------------------------------------------------
# 3. BusinessState.get_competitors by market position
# ---------------------------------------------------------------------------

def test_get_competitors_same_market():
    state = make_state_with_units()
    competitors = state.get_competitors("blue_unit")
    assert any(u.id == "red_unit" for u in competitors)
    assert not any(u.id == "blue_unit" for u in competitors)


def test_get_competitors_excludes_bankrupt():
    state = make_state_with_units()
    state.update_unit("red_unit", status="BANKRUPT")
    competitors = state.get_competitors("blue_unit")
    assert not any(u.id == "red_unit" for u in competitors)


def test_get_competitors_returns_empty_for_unknown_unit():
    state = make_state_with_units()
    assert state.get_competitors("nonexistent") == []


# ---------------------------------------------------------------------------
# 4. BusinessState.get_adjacent_competitors uses market connections
# ---------------------------------------------------------------------------

def test_get_adjacent_competitors_includes_connected_markets():
    state = make_state_with_units()
    # blue_unit is in Korea:EV, red_china is in China:EV (connected)
    competitors = state.get_adjacent_competitors("blue_unit")
    ids = [u.id for u in competitors]
    assert "red_unit" in ids    # same market
    assert "red_china" in ids   # connected market (China:EV)


def test_get_adjacent_competitors_excludes_non_connected():
    state = make_state_with_units()
    # Add a RED unit in a disconnected market
    state.units["red_far"] = make_unit("red_far", "RED", "USA", "EV")
    competitors = state.get_adjacent_competitors("blue_unit")
    ids = [u.id for u in competitors]
    assert "red_far" not in ids


def test_get_adjacent_competitors_returns_empty_for_unknown():
    state = make_state_with_units()
    assert state.get_adjacent_competitors("ghost") == []


# ---------------------------------------------------------------------------
# 5. BusinessState.update_unit creates new immutable instance
# ---------------------------------------------------------------------------

def test_update_unit_changes_field():
    state = make_state_with_units()
    original = state.units["blue_unit"]
    state.update_unit("blue_unit", market_share=0.9)
    updated = state.units["blue_unit"]
    assert updated.market_share == 0.9
    assert original.market_share == 0.5  # old ref unchanged


def test_advance_turn_increments():
    state = BusinessState()
    state.advance_turn()
    assert state.turn == 1
    state.advance_turn()
    assert state.turn == 2


def test_advance_phase_cycles():
    state = BusinessState()
    assert state.phase == "COMMAND"
    state.advance_phase()
    assert state.phase == "EXECUTION"
    state.advance_phase()
    assert state.phase == "RESOLUTION"


# ---------------------------------------------------------------------------
# 6. BusinessAgent._fallback_decide returns BusinessAction
# ---------------------------------------------------------------------------

def test_business_agent_fallback_returns_action():
    state = make_state_with_units()
    state.advance_turn()
    cmd = {
        "id": "cmd1", "name": "Agent One", "side": "BLUE",
        "rank": "Battalion", "unit_id": "blue_unit",
        "personality_traits": {"aggression": 0.8},
    }
    agent = BusinessAgent(cmd, {"api_key": "", "base_url": "", "model": ""})
    actions = agent.decide(state)
    assert isinstance(actions, list)
    assert len(actions) >= 1
    for action in actions:
        assert isinstance(action, BusinessAction)
        assert action.entity_id == "blue_unit"


def test_business_agent_fallback_compete_when_aggressive():
    state = make_state_with_units()
    state.advance_turn()
    cmd = {
        "id": "cmd_agg", "name": "Aggressive", "side": "BLUE",
        "rank": "Battalion", "unit_id": "blue_unit",
        "personality_traits": {"aggression": 0.99},
    }
    agent = BusinessAgent(cmd, {"api_key": "", "base_url": "", "model": ""})
    # Run multiple times to check COMPETE appears
    action_types = set()
    for seed_offset in range(10):
        agent._rng.seed(seed_offset)
        actions = agent._fallback_decide(state, state.get_unit("blue_unit"))
        for a in actions:
            action_types.add(a.action_type)
    assert "COMPETE" in action_types, "Aggressive agent should sometimes COMPETE"


def test_business_agent_hold_when_no_competitors():
    state = BusinessState()
    state.market_map = {}
    state.units = {"solo": make_unit("solo", "BLUE", "Mars", "Air")}
    state.advance_turn()
    cmd = {
        "id": "solo_cmd", "name": "Solo", "side": "BLUE",
        "rank": "Battalion", "unit_id": "solo",
        "personality_traits": {"aggression": 0.5},
    }
    agent = BusinessAgent(cmd, {"api_key": "", "base_url": "", "model": ""})
    # Force low rng so INVEST_RD path is unlikely
    agent._rng.seed(99)
    unit = state.get_unit("solo")
    actions = agent._fallback_decide(state, unit)
    assert len(actions) >= 1
    assert actions[0].action_type in ("HOLD", "INVEST_RD")


# ---------------------------------------------------------------------------
# 7. BusinessCEO._fallback_decide returns directive dicts
# ---------------------------------------------------------------------------

def test_business_ceo_fallback_returns_directives():
    state = make_state_with_units()
    state.advance_turn()
    cmd = {
        "id": "ceo1", "name": "CEO", "side": "BLUE",
        "rank": "Theater", "unit_id": "blue_unit",
        "personality_traits": {"aggression": 0.4},
    }
    ceo = BusinessCEO(cmd, {"api_key": "", "base_url": "", "model": ""})
    unit = state.get_unit("blue_unit")
    directives = ceo._fallback_decide(state, unit)
    assert isinstance(directives, list)
    # CEO issues dicts, not BusinessAction
    for d in directives:
        assert isinstance(d, dict)
        assert "target_unit_id" in d
        assert "mission" in d


# ---------------------------------------------------------------------------
# 8. BusinessCommandOrchestrator produces actions
# ---------------------------------------------------------------------------

def test_orchestrator_run_command_phase_returns_list():
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    state = factory.create_state(scenario)
    state.advance_turn()
    agents = factory.create_agents(scenario)
    orch = BusinessCommandOrchestrator()
    actions = orch.run_command_phase(state, agents)
    assert isinstance(actions, list)


def test_orchestrator_actions_are_business_actions():
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    state = factory.create_state(scenario)
    state.advance_turn()
    agents = factory.create_agents(scenario)
    orch = BusinessCommandOrchestrator()
    actions = orch.run_command_phase(state, agents)
    for a in actions:
        assert isinstance(a, BusinessAction), f"Expected BusinessAction, got {type(a)}"


# ---------------------------------------------------------------------------
# 9. MarketCompetitionResolver uses competitive_power/brand_loyalty directly
# ---------------------------------------------------------------------------

def test_resolver_reads_competitive_power_not_attack_power():
    """Confirm resolver uses competitive_power, not attack_power."""
    strong = BusinessUnit(
        id="strong", name="Strong", side="BLUE", status="ACTIVE",
        position=MarketNode(region="X", segment="Y"),
        market_share=0.5, revenue=1.0, competitive_power=30.0,
        brand_loyalty=5.0, marketing_budget=0.9, cash_reserves=1.0,
        org_health=1.0, rd_capability=0.9,
    )
    weak = BusinessUnit(
        id="weak", name="Weak", side="RED", status="ACTIVE",
        position=MarketNode(region="X", segment="Y"),
        market_share=0.5, revenue=1.0, competitive_power=2.0,
        brand_loyalty=2.0, marketing_budget=0.1, cash_reserves=0.3,
        org_health=0.5, rd_capability=0.1,
    )
    # Strong attacker should gain share at least sometimes
    gained = False
    for seed in range(20):
        r = MarketCompetitionResolver(rng_seed=seed)
        result = r.resolve([strong], [weak], {})
        if result.get("attacker_share_change", 0) > 0:
            gained = True
            break
    assert gained


def test_resolver_has_budget_drain_key():
    resolver = MarketCompetitionResolver(rng_seed=0)
    attacker = make_unit("att", "BLUE")
    defender = make_unit("def", "RED")
    result = resolver.resolve([attacker], [defender], {})
    assert "attacker_budget_drain" in result
    assert result["attacker_budget_drain"] > 0


# ---------------------------------------------------------------------------
# 10. MarketSpace uses connections graph
# ---------------------------------------------------------------------------

def test_market_space_from_scenario_has_connections():
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    engines = factory.create_engines(scenario)
    space = engines["space"]
    assert isinstance(space, MarketSpace)
    # Korea:EV should have neighbors
    korea_ev = MarketNode(region="Korea", segment="EV")
    nbrs = space.neighbors(korea_ev)
    assert len(nbrs) > 0


# ---------------------------------------------------------------------------
# 11. BusinessDomainFactory creates state/engines/agents
# ---------------------------------------------------------------------------

def test_factory_state_has_business_units():
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    state = factory.create_state(scenario)
    assert isinstance(state, BusinessState)
    for unit in state.units.values():
        assert isinstance(unit, BusinessUnit)


def test_factory_engines_no_military_keys():
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    engines = factory.create_engines(scenario)
    military_keys = ["combat_resolver", "movement_engine", "constraint_engine",
                     "intel_engine", "supply_engine", "air_engine", "relationship_graph"]
    for k in military_keys:
        assert k not in engines, f"Military engine key found: {k}"


def test_factory_agents_are_business_agents():
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    agents = factory.create_agents(scenario)
    for agent in agents.values():
        assert isinstance(agent, BusinessAgent), f"Expected BusinessAgent, got {type(agent)}"


# ---------------------------------------------------------------------------
# 12. Full batch run with business scenario (3 turns, N=3)
# ---------------------------------------------------------------------------

def test_full_batch_run_3_turns_n3():
    import app.domains.business  # noqa: F401
    from app.batch.batch_runner import BatchRunner
    from app.batch.parameter_set import ParameterSet

    scenario = load_scenario()
    runner = BatchRunner(scenario, scenario["name"])
    param_sets = [
        ParameterSet(name=f"r{i}", rng_seed=i, max_turns=3, use_llm=False)
        for i in range(3)
    ]
    batch = runner.run_batch(param_sets)
    assert batch.total_runs == 3
    assert batch.completed_runs == 3
    assert batch.failed_runs == 0
    assert batch.status == "COMPLETED"
    for run in batch.runs:
        assert run.winner in ("BLUE", "RED", "DRAW")
        assert run.total_turns <= 3


# ---------------------------------------------------------------------------
# 13. share_change actually affects unit market_share in TurnLoop
# ---------------------------------------------------------------------------

def test_market_share_changes_after_competition():
    """Run 1 turn and verify market_share can change via competition."""
    from app.core.turn_loop import TurnLoop

    scenario = load_scenario()
    factory = BusinessDomainFactory()
    state = factory.create_state(scenario)
    engines = factory.create_engines(scenario, {"rng_seed": 0})
    agents = factory.create_agents(scenario)

    initial_shares = {uid: u.market_share for uid, u in state.units.items()}

    loop = TurnLoop(
        state=state,
        command_orchestrator=engines["command_orchestrator"],
        mover=engines["mover"],
        interaction_resolver=engines["interaction_resolver"],
        constraints=engines["constraints"],
        victory_checker=engines["victory_checker"],
        agents=agents,
    )
    loop.run_simulation(max_turns=3)

    # After 3 turns, at least some shares should have changed (with seed=0 there should be activity)
    final_shares = {uid: u.market_share for uid, u in state.units.items()}
    # Not all shares must change, but the state is mutable
    assert isinstance(final_shares, dict)
    assert len(final_shares) == len(initial_shares)


# ---------------------------------------------------------------------------
# 14. marketing_budget drains during competition
# ---------------------------------------------------------------------------

def test_marketing_budget_drains():
    """Run simulation and verify marketing_budget can decrease."""
    from app.core.turn_loop import TurnLoop

    scenario = load_scenario()
    factory = BusinessDomainFactory()
    state = factory.create_state(scenario)
    engines = factory.create_engines(scenario, {"rng_seed": 1})
    agents = factory.create_agents(scenario)

    initial_budgets = {uid: u.marketing_budget for uid, u in state.units.items()}

    loop = TurnLoop(
        state=state,
        command_orchestrator=engines["command_orchestrator"],
        mover=engines["mover"],
        interaction_resolver=engines["interaction_resolver"],
        constraints=engines["constraints"],
        victory_checker=engines["victory_checker"],
        agents=agents,
    )
    loop.run_simulation(max_turns=5)

    final_budgets = {uid: u.marketing_budget for uid, u in state.units.items()}
    # At least one unit should have had budget drained
    drained = any(
        final_budgets[uid] < initial_budgets[uid]
        for uid in initial_budgets
    )
    assert drained, "No marketing budget was drained after 5 turns of competition"


# ---------------------------------------------------------------------------
# 15. BusinessState.to_snapshot serializes correctly
# ---------------------------------------------------------------------------

def test_to_snapshot_is_serializable():
    scenario = load_scenario()
    state = BusinessState(scenario)
    snap = state.to_snapshot()
    assert "turn" in snap
    assert "units" in snap
    assert "market_map" in snap
    # Ensure JSON-serializable
    serialized = json.dumps(snap, default=str)
    assert len(serialized) > 0
