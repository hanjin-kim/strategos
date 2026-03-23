"""Tests for app/domains/business — models, engines, factory, registry."""
from __future__ import annotations
import json
import importlib
import pytest
from pathlib import Path

import app.core.protocols as proto
import app.core.domain_registry as registry

from app.domains.business.models import (
    MarketNode, BusinessUnit, BusinessAction, MarketTerrain, CompetitionOutcome,
)
from app.domains.business.engines import (
    MarketSpace, MarketCompetitionResolver, BusinessMover,
    BusinessConstraints, BusinessVictory,
)
from app.domains.business.factory import BusinessDomainFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCENARIO_PATH = Path(__file__).parent.parent.parent / "scripts/seed_scenarios/ev_battery_market.json"


def load_scenario() -> dict:
    return json.loads(SCENARIO_PATH.read_text())


def make_market_node(region: str = "Korea", segment: str = "EV") -> MarketNode:
    return MarketNode(region=region, segment=segment)


def make_business_unit(uid: str = "bu1", side: str = "BLUE", status: str = "ACTIVE") -> BusinessUnit:
    return BusinessUnit(
        id=uid,
        name=f"Unit-{uid}",
        side=side,
        status=status,
        position=make_market_node(),
        market_share=0.3,
        revenue=100.0,
        competitive_power=8.0,
        brand_loyalty=7.0,
        marketing_budget=0.6,
        cash_reserves=0.8,
        org_health=0.9,
        rd_capability=0.7,
    )


def make_market_space() -> MarketSpace:
    connections = {
        "Korea:EV": ["China:EV", "Korea:ESS"],
        "China:EV": ["Korea:EV", "USA:EV"],
        "USA:EV": ["China:EV", "Europe:EV"],
        "Europe:EV": ["USA:EV"],
        "Korea:ESS": ["Korea:EV"],
    }
    terrains: dict = {}
    return MarketSpace(connections, terrains)


@pytest.fixture(autouse=True)
def clear_registry():
    registry.clear()
    yield
    registry.clear()


# ---------------------------------------------------------------------------
# 1. MarketNode creation and equality
# ---------------------------------------------------------------------------

def test_market_node_creation():
    node = MarketNode(region="Korea", segment="EV")
    assert node.region == "Korea"
    assert node.segment == "EV"


def test_market_node_equality():
    a = MarketNode(region="Korea", segment="EV")
    b = MarketNode(region="Korea", segment="EV")
    assert a == b


def test_market_node_inequality_different_region():
    a = MarketNode(region="Korea", segment="EV")
    b = MarketNode(region="China", segment="EV")
    assert a != b


def test_market_node_inequality_different_segment():
    a = MarketNode(region="Korea", segment="EV")
    b = MarketNode(region="Korea", segment="ESS")
    assert a != b


def test_market_node_hash_equal_nodes():
    a = MarketNode(region="Korea", segment="EV")
    b = MarketNode(region="Korea", segment="EV")
    assert hash(a) == hash(b)


def test_market_node_usable_in_set():
    a = MarketNode(region="Korea", segment="EV")
    b = MarketNode(region="China", segment="EV")
    s = {a, b}
    assert len(s) == 2


def test_market_node_eq_with_non_marketnode_returns_not_implemented():
    node = MarketNode(region="Korea", segment="EV")
    result = node.__eq__("not_a_node")
    assert result is NotImplemented


# ---------------------------------------------------------------------------
# 2. BusinessUnit creation
# ---------------------------------------------------------------------------

def test_business_unit_creation():
    unit = make_business_unit()
    assert unit.id == "bu1"
    assert unit.side == "BLUE"
    assert unit.status == "ACTIVE"
    assert isinstance(unit.position, MarketNode)


def test_business_unit_default_status():
    unit = BusinessUnit(
        id="u1", name="Test", side="BLUE",
        position=make_market_node(),
        market_share=0.2, revenue=50.0, competitive_power=5.0,
        brand_loyalty=5.0, marketing_budget=0.5, cash_reserves=0.5,
        org_health=0.8, rd_capability=0.6,
    )
    assert unit.status == "ACTIVE"


def test_business_unit_bankrupt_status():
    unit = make_business_unit(status="BANKRUPT")
    assert unit.status == "BANKRUPT"


# ---------------------------------------------------------------------------
# 3. BusinessAction creation
# ---------------------------------------------------------------------------

def test_business_action_creation():
    action = BusinessAction(
        action_id="a1", turn=1, commander_id="cmd1",
        entity_id="bu1", action_type="EXPAND",
        target=make_market_node("China", "EV"),
    )
    assert action.action_id == "a1"
    assert action.action_type == "EXPAND"
    assert action.target == MarketNode(region="China", segment="EV")


def test_business_action_default_intensity():
    action = BusinessAction(
        action_id="a2", turn=1, commander_id="cmd1",
        entity_id="bu1", action_type="HOLD",
    )
    assert action.intensity == 0.5
    assert action.target is None


# ---------------------------------------------------------------------------
# 4. MarketSpace: neighbors, distance, is_passable
# ---------------------------------------------------------------------------

def test_market_space_neighbors_returns_list():
    space = make_market_space()
    node = MarketNode(region="Korea", segment="EV")
    nbrs = space.neighbors(node)
    assert isinstance(nbrs, list)


def test_market_space_neighbors_correct():
    space = make_market_space()
    node = MarketNode(region="Korea", segment="EV")
    nbrs = space.neighbors(node)
    assert MarketNode(region="China", segment="EV") in nbrs
    assert MarketNode(region="Korea", segment="ESS") in nbrs


def test_market_space_neighbors_invalid_type_returns_empty():
    space = make_market_space()
    assert space.neighbors("not_a_node") == []


def test_market_space_distance_same_node():
    space = make_market_space()
    node = MarketNode(region="Korea", segment="EV")
    assert space.distance(node, node) == 0.0


def test_market_space_distance_direct_neighbor():
    space = make_market_space()
    a = MarketNode(region="Korea", segment="EV")
    b = MarketNode(region="China", segment="EV")
    assert space.distance(a, b) == 1.0


def test_market_space_distance_not_connected():
    space = make_market_space()
    a = MarketNode(region="Korea", segment="EV")
    b = MarketNode(region="Europe", segment="EV")
    assert space.distance(a, b) == 2.0


def test_market_space_distance_invalid_type_returns_inf():
    space = make_market_space()
    assert space.distance("bad", MarketNode(region="Korea", segment="EV")) == float('inf')


def test_market_space_is_passable_no_terrain():
    space = make_market_space()
    # No terrain registered — defaults to True
    assert space.is_passable(MarketNode(region="Korea", segment="EV")) is True


def test_market_space_is_passable_invalid_type():
    space = make_market_space()
    assert space.is_passable("not_a_node") is False


def test_market_space_satisfies_space_protocol():
    space = make_market_space()
    assert isinstance(space, proto.Space)


# ---------------------------------------------------------------------------
# 5. MarketCompetitionResolver
# ---------------------------------------------------------------------------

def test_resolver_resolve_returns_dict():
    resolver = MarketCompetitionResolver(rng_seed=42)
    attacker = make_business_unit("att", "BLUE")
    defender = make_business_unit("def", "RED")
    result = resolver.resolve([attacker], [defender], {})
    assert isinstance(result, dict)


def test_resolver_resolve_has_outcome_key():
    resolver = MarketCompetitionResolver(rng_seed=42)
    attacker = make_business_unit("att", "BLUE")
    defender = make_business_unit("def", "RED")
    result = resolver.resolve([attacker], [defender], {})
    assert "outcome" in result


def test_resolver_resolve_empty_actors_returns_none_outcome():
    resolver = MarketCompetitionResolver(rng_seed=42)
    result = resolver.resolve([], [], {})
    assert result["outcome"] is None


def test_resolver_stronger_attacker_can_gain_share():
    """With high competitive_power and seed chosen to trigger gain."""
    resolver = MarketCompetitionResolver(rng_seed=0)
    attacker = BusinessUnit(
        id="att", name="Attacker", side="BLUE", status="ACTIVE",
        position=make_market_node(),
        market_share=0.4, revenue=100.0, competitive_power=20.0,
        brand_loyalty=5.0, marketing_budget=0.9, cash_reserves=0.8,
        org_health=0.9, rd_capability=0.7,
    )
    defender = BusinessUnit(
        id="def", name="Defender", side="RED", status="ACTIVE",
        position=make_market_node(),
        market_share=0.4, revenue=100.0, competitive_power=5.0,
        brand_loyalty=3.0, marketing_budget=0.3, cash_reserves=0.5,
        org_health=0.7, rd_capability=0.4,
    )
    # Run multiple times and expect at least one gain
    gained = False
    for seed in range(10):
        r = MarketCompetitionResolver(rng_seed=seed)
        res = r.resolve([attacker], [defender], {})
        if res.get("attacker_share_change", 0) > 0:
            gained = True
            break
    assert gained, "Strong attacker should be able to gain market share"


def test_resolver_deterministic_with_same_seed():
    resolver1 = MarketCompetitionResolver(rng_seed=42)
    resolver2 = MarketCompetitionResolver(rng_seed=42)
    attacker = make_business_unit("att", "BLUE")
    defender = make_business_unit("def", "RED")
    r1 = resolver1.resolve([attacker], [defender], {})
    r2 = resolver2.resolve([attacker], [defender], {})
    assert r1.get("attacker_share_change") == r2.get("attacker_share_change")
    assert r1.get("narrative") == r2.get("narrative")


def test_resolver_satisfies_interaction_resolver_protocol():
    resolver = MarketCompetitionResolver(rng_seed=42)
    assert isinstance(resolver, proto.InteractionResolver)


# ---------------------------------------------------------------------------
# 6. BusinessMover
# ---------------------------------------------------------------------------

def test_mover_execute_moves_expand_action():
    from app.engine.game_state import GameState
    scenario = load_scenario()
    state = GameState(scenario)
    state.advance_turn()

    action = BusinessAction(
        action_id="m1", turn=1, commander_id="cmd1",
        entity_id="blue_ev_korea", action_type="EXPAND",
        target=MarketNode(region="China", segment="EV"),
    )
    mover = BusinessMover()
    results = mover.execute_moves([action], state)
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["unit_id"] == "blue_ev_korea"
    assert results[0]["final_position"] == MarketNode(region="China", segment="EV")


def test_mover_execute_moves_non_expand_ignored():
    from app.engine.game_state import GameState
    scenario = load_scenario()
    state = GameState(scenario)
    state.advance_turn()

    action = BusinessAction(
        action_id="m2", turn=1, commander_id="cmd1",
        entity_id="blue_ev_korea", action_type="HOLD",
    )
    mover = BusinessMover()
    results = mover.execute_moves([action], state)
    assert results == []


def test_mover_execute_moves_empty_list():
    from app.engine.game_state import GameState
    scenario = load_scenario()
    state = GameState(scenario)
    mover = BusinessMover()
    assert mover.execute_moves([], state) == []


def test_mover_satisfies_mover_engine_protocol():
    mover = BusinessMover()
    assert isinstance(mover, proto.MoverEngine)


# ---------------------------------------------------------------------------
# 7. BusinessConstraints
# ---------------------------------------------------------------------------

def test_constraints_validate_active_unit_passes():
    from app.engine.game_state import GameState
    scenario = load_scenario()
    state = GameState(scenario)
    state.advance_turn()

    action = BusinessAction(
        action_id="c1", turn=1, commander_id="cmd1",
        entity_id="blue_ev_korea", action_type="HOLD",
    )
    constraints = BusinessConstraints()
    result = constraints.validate([action], state)
    assert hasattr(result, "valid_actions")
    assert len(result.valid_actions) == 1


def test_constraints_validate_missing_unit_rejected():
    from app.engine.game_state import GameState
    scenario = load_scenario()
    state = GameState(scenario)

    action = BusinessAction(
        action_id="c2", turn=1, commander_id="cmd1",
        entity_id="nonexistent_unit", action_type="HOLD",
    )
    constraints = BusinessConstraints()
    result = constraints.validate([action], state)
    assert len(result.rejections) == 1
    assert len(result.valid_actions) == 0


def test_constraints_satisfies_domain_constraints_protocol():
    constraints = BusinessConstraints()
    assert isinstance(constraints, proto.DomainConstraints)


# ---------------------------------------------------------------------------
# 8. BusinessVictory
# ---------------------------------------------------------------------------

def test_victory_false_when_both_sides_active():
    from app.engine.game_state import GameState
    scenario = load_scenario()
    state = GameState(scenario)
    victory = BusinessVictory()
    assert victory.check(state) is False


def test_victory_true_when_one_side_all_destroyed():
    from app.engine.game_state import GameState
    from app.models.domain import UnitStatus, Side
    scenario = load_scenario()
    state = GameState(scenario)
    # Destroy all BLUE units
    for uid, unit in list(state.units.items()):
        if unit.side == Side.BLUE:
            state.update_unit(uid, status=UnitStatus.DESTROYED)
    victory = BusinessVictory()
    assert victory.check(state) is True


def test_victory_false_when_no_units():
    victory = BusinessVictory()

    class EmptyState:
        units = {}

    assert victory.check(EmptyState()) is False


def test_victory_satisfies_victory_checker_protocol():
    victory = BusinessVictory()
    assert isinstance(victory, proto.VictoryChecker)


# ---------------------------------------------------------------------------
# 9. BusinessDomainFactory
# ---------------------------------------------------------------------------

def test_factory_create_state_returns_game_state():
    from app.engine.game_state import GameState
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    state = factory.create_state(scenario)
    assert isinstance(state, GameState)


def test_factory_create_state_loads_units():
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    state = factory.create_state(scenario)
    assert len(state.units) > 0


def test_factory_create_engines_returns_dict():
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    engines = factory.create_engines(scenario)
    assert isinstance(engines, dict)


def test_factory_create_engines_has_required_keys():
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    engines = factory.create_engines(scenario)
    expected = [
        "game_state", "space", "interaction_resolver", "mover",
        "constraints", "victory_checker", "command_orchestrator",
        "combat_resolver", "movement_engine", "constraint_engine",
        "intel_engine", "supply_engine", "air_engine", "relationship_graph",
    ]
    for key in expected:
        assert key in engines, f"Missing engine key: {key}"


def test_factory_create_engines_space_is_market_space():
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    engines = factory.create_engines(scenario)
    assert isinstance(engines["space"], MarketSpace)


def test_factory_create_engines_victory_is_business_victory():
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    engines = factory.create_engines(scenario)
    assert isinstance(engines["victory_checker"], BusinessVictory)


def test_factory_create_agents_returns_dict():
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    agents = factory.create_agents(scenario)
    assert isinstance(agents, dict)


def test_factory_create_agents_not_empty():
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    agents = factory.create_agents(scenario)
    assert len(agents) > 0


def test_factory_create_agents_llm_free():
    scenario = load_scenario()
    factory = BusinessDomainFactory()
    agents = factory.create_agents(scenario, params={"use_llm": False})
    for agent in agents.values():
        assert agent._client is None


def test_factory_satisfies_domain_state_factory_protocol():
    factory = BusinessDomainFactory()
    assert isinstance(factory, proto.DomainStateFactory)


# ---------------------------------------------------------------------------
# 10. Protocol isinstance checks for all business engines
# ---------------------------------------------------------------------------

def test_all_business_engines_satisfy_protocols():
    space = make_market_space()
    resolver = MarketCompetitionResolver(rng_seed=42)
    mover = BusinessMover()
    constraints = BusinessConstraints()
    victory = BusinessVictory()

    assert isinstance(space, proto.Space)
    assert isinstance(resolver, proto.InteractionResolver)
    assert isinstance(mover, proto.MoverEngine)
    assert isinstance(constraints, proto.DomainConstraints)
    assert isinstance(victory, proto.VictoryChecker)


# ---------------------------------------------------------------------------
# 11. domain_registry: "business" registered after import
# ---------------------------------------------------------------------------

def test_business_domain_registered_after_import():
    import app.domains.business as biz_mod
    importlib.reload(biz_mod)
    assert "business" in registry.list_domains()


def test_business_domain_factory_is_business_domain_factory():
    import app.domains.business as biz_mod
    importlib.reload(biz_mod)
    factory = registry.get("business")
    assert isinstance(factory, BusinessDomainFactory)


# ---------------------------------------------------------------------------
# 12. BatchRunner with domain="business" scenario (3 turns, LLM-free)
# ---------------------------------------------------------------------------

def test_batch_runner_business_domain_single_run():
    from app.batch.batch_runner import BatchRunner
    from app.batch.parameter_set import ParameterSet
    import app.domains.business  # ensure registered  # noqa: F401

    scenario = load_scenario()
    assert scenario.get("domain") == "business"

    runner = BatchRunner(scenario, scenario["name"])
    params = ParameterSet(name="test", rng_seed=42, max_turns=3, use_llm=False)
    result = runner._execute_single_run(0, params)
    assert result.status == "COMPLETED"
    assert result.total_turns <= 3


def test_batch_runner_business_domain_n3():
    from app.batch.batch_runner import BatchRunner
    from app.batch.parameter_set import ParameterSet
    import app.domains.business  # ensure registered  # noqa: F401

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
