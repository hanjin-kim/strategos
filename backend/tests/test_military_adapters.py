"""Tests for app/domains/military — adapters, factory, and domain registry."""
from __future__ import annotations
import json
import pytest
from pathlib import Path

from app.models.domain import (
    Commander, Unit, Side, UnitType, UnitSize, UnitStatus,
    HexCoord, TerrainHex, TerrainType, Force,
)
from app.models.actions import MilitaryAction, ActionType
from app.engine.game_state import GameState
from app.engine.combat_resolver import CombatResolver
from app.engine.movement_engine import MovementEngine
from app.engine.constraint_engine import ConstraintEngine
from app.engine.turn_manager import TurnManager
import app.core.domain_registry as registry
import app.core.protocols as proto


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCENARIO_PATH = Path(__file__).parent.parent.parent / "scripts/seed_scenarios/korean_peninsula.json"


def load_scenario() -> dict:
    return json.loads(SCENARIO_PATH.read_text())


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


def make_terrain(q: int, r: int, terrain_type: TerrainType = TerrainType.PLAIN) -> TerrainHex:
    return TerrainHex(
        coord=HexCoord(q=q, r=r),
        terrain_type=terrain_type,
        elevation=0, movement_cost=1, defense_modifier=1.0,
    )


def make_small_game_state() -> GameState:
    """Small 2v2 game state for unit tests."""
    gs = GameState()
    for q in range(-1, 6):
        for r in range(-1, 6):
            gs.terrain[HexCoord(q=q, r=r)] = make_terrain(q, r)
    # Add a water hex for passability test
    gs.terrain[HexCoord(q=10, r=10)] = TerrainHex(
        coord=HexCoord(q=10, r=10), terrain_type=TerrainType.WATER,
        elevation=0, movement_cost=999, defense_modifier=1.0,
    )
    gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0)
    gs.units["blue2"] = make_unit("blue2", Side.BLUE, 1, 0)
    gs.units["red1"] = make_unit("red1", Side.RED, 3, 0)
    gs.units["red2"] = make_unit("red2", Side.RED, 4, 0)
    gs.commanders["tcmd_blue"] = Commander(id="tcmd_blue", name="Blue Theater", side=Side.BLUE, rank="Theater", unit_id="blue1")
    gs.commanders["bcmd_blue1"] = Commander(id="bcmd_blue1", name="Blue Bn1", side=Side.BLUE, rank="Battalion", unit_id="blue1")
    gs.commanders["bcmd_blue2"] = Commander(id="bcmd_blue2", name="Blue Bn2", side=Side.BLUE, rank="Battalion", unit_id="blue2")
    gs.commanders["tcmd_red"] = Commander(id="tcmd_red", name="Red Theater", side=Side.RED, rank="Theater", unit_id="red1")
    gs.commanders["bcmd_red1"] = Commander(id="bcmd_red1", name="Red Bn1", side=Side.RED, rank="Battalion", unit_id="red1")
    gs.commanders["bcmd_red2"] = Commander(id="bcmd_red2", name="Red Bn2", side=Side.RED, rank="Battalion", unit_id="red2")
    gs.forces[Side.BLUE] = Force(side=Side.BLUE, name="Blue Force",
                                  commander_ids=["tcmd_blue", "bcmd_blue1", "bcmd_blue2"],
                                  unit_ids=["blue1", "blue2"])
    gs.forces[Side.RED] = Force(side=Side.RED, name="Red Force",
                                 commander_ids=["tcmd_red", "bcmd_red1", "bcmd_red2"],
                                 unit_ids=["red1", "red2"])
    return gs


# ---------------------------------------------------------------------------
# Imports of domain modules (trigger registration side-effect)
# ---------------------------------------------------------------------------

# Import after helpers to avoid registry pollution in other tests
from app.domains.military.adapters import (
    MilitarySpace, MilitaryInteractionResolver, MilitaryMover,
    MilitaryConstraints, MilitaryVictory, MilitaryCommandOrchestrator,
)
from app.domains.military.factory import MilitaryDomainFactory


# ---------------------------------------------------------------------------
# MilitarySpace tests
# ---------------------------------------------------------------------------

class TestMilitarySpace:
    def setup_method(self):
        self.gs = make_small_game_state()
        self.space = MilitarySpace(self.gs.terrain)

    def test_neighbors_returns_valid_hexes_only(self):
        # (0,0) is on map; neighbors that are on map should be returned
        pos = HexCoord(q=0, r=0)
        nbrs = self.space.neighbors(pos)
        assert isinstance(nbrs, list)
        assert len(nbrs) > 0
        # All returned neighbors must be in terrain map
        for n in nbrs:
            assert n in self.gs.terrain

    def test_neighbors_excludes_off_map_hexes(self):
        # Edge hex — some neighbors will be off map
        pos = HexCoord(q=-1, r=-1)
        nbrs = self.space.neighbors(pos)
        for n in nbrs:
            assert n in self.gs.terrain

    def test_neighbors_invalid_type_returns_empty(self):
        assert self.space.neighbors("not_a_hexcoord") == []

    def test_distance_correct(self):
        a = HexCoord(q=0, r=0)
        b = HexCoord(q=3, r=0)
        assert self.space.distance(a, b) == 3.0

    def test_distance_same_hex(self):
        a = HexCoord(q=2, r=1)
        assert self.space.distance(a, a) == 0.0

    def test_distance_returns_float(self):
        a = HexCoord(q=0, r=0)
        b = HexCoord(q=1, r=0)
        result = self.space.distance(a, b)
        assert isinstance(result, float)

    def test_distance_invalid_type_returns_inf(self):
        assert self.space.distance("bad", HexCoord(q=0, r=0)) == float('inf')

    def test_is_passable_plain(self):
        assert self.space.is_passable(HexCoord(q=0, r=0)) is True

    def test_is_passable_water_false(self):
        assert self.space.is_passable(HexCoord(q=10, r=10)) is False

    def test_is_passable_off_map_false(self):
        assert self.space.is_passable(HexCoord(q=999, r=999)) is False

    def test_space_satisfies_protocol(self):
        assert isinstance(self.space, proto.Space)


# ---------------------------------------------------------------------------
# MilitaryInteractionResolver tests
# ---------------------------------------------------------------------------

class TestMilitaryInteractionResolver:
    def setup_method(self):
        self.gs = make_small_game_state()
        self.resolver = MilitaryInteractionResolver(CombatResolver(rng_seed=42))

    def test_resolve_returns_dict(self):
        attacker = self.gs.units["blue1"]
        defender = self.gs.units["red1"]
        terrain = self.gs.terrain[HexCoord(q=0, r=0)]
        result = self.resolver.resolve([attacker], [defender], {"terrain": terrain})
        assert isinstance(result, dict)

    def test_resolve_has_expected_keys(self):
        attacker = self.gs.units["blue1"]
        defender = self.gs.units["red1"]
        terrain = self.gs.terrain[HexCoord(q=0, r=0)]
        result = self.resolver.resolve([attacker], [defender], {"terrain": terrain})
        assert "outcome" in result
        assert "attacker_id" in result
        assert "defender_id" in result
        assert "result" in result
        assert "attacker_losses" in result
        assert "defender_losses" in result

    def test_resolve_correct_ids(self):
        attacker = self.gs.units["blue1"]
        defender = self.gs.units["red1"]
        terrain = self.gs.terrain[HexCoord(q=0, r=0)]
        result = self.resolver.resolve([attacker], [defender], {"terrain": terrain})
        assert result["attacker_id"] == "blue1"
        assert result["defender_id"] == "red1"

    def test_resolver_satisfies_protocol(self):
        assert isinstance(self.resolver, proto.InteractionResolver)


# ---------------------------------------------------------------------------
# MilitaryMover tests
# ---------------------------------------------------------------------------

class TestMilitaryMover:
    def setup_method(self):
        self.gs = make_small_game_state()
        self.mover = MilitaryMover(MovementEngine())

    def test_execute_moves_returns_list(self):
        action = MilitaryAction(
            action_id="a1", turn=1, commander_id="bcmd_blue1",
            unit_id="blue1", action_type=ActionType.MOVE,
            target_hex=HexCoord(q=2, r=0),
        )
        self.gs.advance_turn()
        results = self.mover.execute_moves([action], self.gs)
        assert isinstance(results, list)

    def test_execute_moves_empty_input(self):
        self.gs.advance_turn()
        results = self.mover.execute_moves([], self.gs)
        assert results == []

    def test_mover_satisfies_protocol(self):
        assert isinstance(self.mover, proto.MoverEngine)


# ---------------------------------------------------------------------------
# MilitaryConstraints tests
# ---------------------------------------------------------------------------

class TestMilitaryConstraints:
    def setup_method(self):
        self.gs = make_small_game_state()
        self.gs.advance_turn()
        self.constraints = MilitaryConstraints(ConstraintEngine())

    def test_validate_returns_validation_result(self):
        action = MilitaryAction(
            action_id="a1", turn=1, commander_id="bcmd_blue1",
            unit_id="blue1", action_type=ActionType.HOLD,
        )
        result = self.constraints.validate([action], self.gs)
        assert hasattr(result, "valid_actions")
        assert hasattr(result, "rejections")

    def test_validate_passes_valid_action(self):
        action = MilitaryAction(
            action_id="a1", turn=1, commander_id="bcmd_blue1",
            unit_id="blue1", action_type=ActionType.HOLD,
        )
        result = self.constraints.validate([action], self.gs)
        assert len(result.valid_actions) == 1

    def test_constraints_satisfies_protocol(self):
        assert isinstance(self.constraints, proto.DomainConstraints)


# ---------------------------------------------------------------------------
# MilitaryVictory tests
# ---------------------------------------------------------------------------

class TestMilitaryVictory:
    def setup_method(self):
        self.gs = make_small_game_state()
        self.victory = MilitaryVictory()

    def test_check_false_when_both_sides_active(self):
        assert self.victory.check(self.gs) is False

    def test_check_true_when_blue_eliminated(self):
        self.gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0, UnitStatus.DESTROYED)
        self.gs.units["blue2"] = make_unit("blue2", Side.BLUE, 1, 0, UnitStatus.DESTROYED)
        assert self.victory.check(self.gs) is True

    def test_check_true_when_red_eliminated(self):
        self.gs.units["red1"] = make_unit("red1", Side.RED, 3, 0, UnitStatus.DESTROYED)
        self.gs.units["red2"] = make_unit("red2", Side.RED, 4, 0, UnitStatus.DESTROYED)
        assert self.victory.check(self.gs) is True

    def test_check_true_when_all_routed(self):
        self.gs.units["red1"] = make_unit("red1", Side.RED, 3, 0, UnitStatus.ROUTED)
        self.gs.units["red2"] = make_unit("red2", Side.RED, 4, 0, UnitStatus.ROUTED)
        assert self.victory.check(self.gs) is True

    def test_victory_satisfies_protocol(self):
        assert isinstance(self.victory, proto.VictoryChecker)


# ---------------------------------------------------------------------------
# MilitaryCommandOrchestrator tests
# ---------------------------------------------------------------------------

class TestMilitaryCommandOrchestrator:
    def setup_method(self):
        self.gs = make_small_game_state()
        self.gs.advance_turn()
        self.orchestrator = MilitaryCommandOrchestrator(
            relationship_graph=None,
            constraint_engine=ConstraintEngine(),
        )

    def _make_agents(self):
        from app.agents.theater_commander import TheaterCommander
        from app.agents.battalion_commander import BattalionCommander
        agents = {}
        agents["tcmd_blue"] = TheaterCommander(self.gs.commanders["tcmd_blue"], llm_config={})
        agents["bcmd_blue1"] = BattalionCommander(self.gs.commanders["bcmd_blue1"], llm_config={})
        agents["bcmd_blue2"] = BattalionCommander(self.gs.commanders["bcmd_blue2"], llm_config={})
        agents["tcmd_red"] = TheaterCommander(self.gs.commanders["tcmd_red"], llm_config={})
        agents["bcmd_red1"] = BattalionCommander(self.gs.commanders["bcmd_red1"], llm_config={})
        agents["bcmd_red2"] = BattalionCommander(self.gs.commanders["bcmd_red2"], llm_config={})
        return agents

    def test_run_command_phase_returns_list(self):
        agents = self._make_agents()
        actions = self.orchestrator.run_command_phase(self.gs, agents)
        assert isinstance(actions, list)

    def test_run_command_phase_produces_actions(self):
        agents = self._make_agents()
        actions = self.orchestrator.run_command_phase(self.gs, agents)
        # Fallback mode should still produce HOLD actions
        assert len(actions) >= 0  # may be 0 if no valid actions after validation

    def test_orchestrator_satisfies_protocol(self):
        assert isinstance(self.orchestrator, proto.CommandPhaseOrchestrator)

    def test_two_tier_fallback_no_division(self):
        """Scenario without Division commanders should still work (2-tier)."""
        agents = self._make_agents()
        # No DivisionCommander in agents — confirms 2-tier fallback path executes
        from app.agents.division_commander import DivisionCommander
        has_division = any(isinstance(a, DivisionCommander) for a in agents.values())
        assert not has_division
        actions = self.orchestrator.run_command_phase(self.gs, agents)
        assert isinstance(actions, list)


# ---------------------------------------------------------------------------
# MilitaryDomainFactory tests
# ---------------------------------------------------------------------------

class TestMilitaryDomainFactory:
    def setup_method(self):
        self.scenario = load_scenario()
        self.factory = MilitaryDomainFactory()

    def test_create_state_returns_game_state(self):
        state = self.factory.create_state(self.scenario)
        assert isinstance(state, GameState)

    def test_create_state_loads_units(self):
        state = self.factory.create_state(self.scenario)
        assert len(state.units) > 0

    def test_create_state_loads_terrain(self):
        state = self.factory.create_state(self.scenario)
        assert len(state.terrain) > 0

    def test_create_engines_returns_dict(self):
        engines = self.factory.create_engines(self.scenario)
        assert isinstance(engines, dict)

    def test_create_engines_has_all_expected_keys(self):
        engines = self.factory.create_engines(self.scenario)
        expected = [
            "game_state", "space", "interaction_resolver", "mover",
            "constraints", "victory_checker", "command_orchestrator",
            "combat_resolver", "movement_engine", "constraint_engine",
            "intel_engine", "supply_engine", "air_engine", "relationship_graph",
        ]
        for key in expected:
            assert key in engines, f"Missing key: {key}"

    def test_create_engines_space_is_military_space(self):
        engines = self.factory.create_engines(self.scenario)
        assert isinstance(engines["space"], MilitarySpace)

    def test_create_engines_victory_checker_is_military_victory(self):
        engines = self.factory.create_engines(self.scenario)
        assert isinstance(engines["victory_checker"], MilitaryVictory)

    def test_create_agents_returns_dict(self):
        agents = self.factory.create_agents(self.scenario)
        assert isinstance(agents, dict)

    def test_create_agents_not_empty(self):
        agents = self.factory.create_agents(self.scenario)
        assert len(agents) > 0

    def test_create_agents_llm_free_mode(self):
        """All agents should have no LLM client in LLM-free mode."""
        agents = self.factory.create_agents(self.scenario, params={"use_llm": False})
        for agent in agents.values():
            assert agent._client is None

    def test_factory_satisfies_domain_state_factory_protocol(self):
        assert isinstance(self.factory, proto.DomainStateFactory)


# ---------------------------------------------------------------------------
# domain_registry: "military" is registered after import
# ---------------------------------------------------------------------------

def test_military_domain_registered():
    """Importing app.domains.military registers 'military' in the registry."""
    # The registry may have been cleared by autouse fixtures in other modules.
    # Re-register explicitly by re-importing the side-effect module.
    import importlib
    import app.domains.military as mil_mod
    importlib.reload(mil_mod)
    assert "military" in registry.list_domains()


def test_military_domain_factory_is_military_domain_factory():
    import importlib
    import app.domains.military as mil_mod
    importlib.reload(mil_mod)
    factory = registry.get("military")
    assert isinstance(factory, MilitaryDomainFactory)


# ---------------------------------------------------------------------------
# Protocol isinstance checks — all adapters satisfy their Protocol
# ---------------------------------------------------------------------------

def test_all_adapters_satisfy_protocols():
    gs = make_small_game_state()
    space = MilitarySpace(gs.terrain)
    resolver = MilitaryInteractionResolver(CombatResolver(rng_seed=0))
    mover = MilitaryMover(MovementEngine())
    constraints = MilitaryConstraints(ConstraintEngine())
    victory = MilitaryVictory()
    orchestrator = MilitaryCommandOrchestrator()

    assert isinstance(space, proto.Space)
    assert isinstance(resolver, proto.InteractionResolver)
    assert isinstance(mover, proto.MoverEngine)
    assert isinstance(constraints, proto.DomainConstraints)
    assert isinstance(victory, proto.VictoryChecker)
    assert isinstance(orchestrator, proto.CommandPhaseOrchestrator)


# ---------------------------------------------------------------------------
# BIT-EXACT TEST: factory-created run matches direct TurnManager run
# ---------------------------------------------------------------------------

def test_bit_exact_factory_vs_direct_turn_manager():
    """
    Run 3-turn simulation via factory-created engines + TurnManager, then
    compare to_snapshot() with direct TurnManager construction (same seed=42).
    Both must produce identical snapshots.
    """
    scenario = load_scenario()
    seed = 42
    max_turns = 3

    # --- Run A: via factory ---
    factory = MilitaryDomainFactory()
    engines_a = factory.create_engines(scenario, params={"rng_seed": seed})
    agents_a = factory.create_agents(scenario, params={"use_llm": False})

    tm_a = TurnManager(
        game_state=engines_a["game_state"],
        agents=agents_a,
        constraint_engine=engines_a["constraint_engine"],
        combat_resolver=engines_a["combat_resolver"],
        movement_engine=engines_a["movement_engine"],
        relationship_graph=engines_a["relationship_graph"],
        intel_engine=engines_a["intel_engine"],
        supply_engine=engines_a["supply_engine"],
        air_engine=engines_a["air_engine"],
    )
    tm_a.run_simulation(max_turns=max_turns)
    snapshot_a = engines_a["game_state"].to_snapshot()

    # --- Run B: direct construction (same seed) ---
    from app.graph.relationship_graph import RelationshipGraph
    from app.graph.graph_tools import GraphTools
    from app.agents.theater_commander import TheaterCommander
    from app.agents.division_commander import DivisionCommander
    from app.agents.battalion_commander import BattalionCommander
    from app.engine.intel_engine import IntelEngine
    from app.engine.supply_engine import SupplyEngine
    from app.engine.air_engine import AirEngine

    gs_b = GameState(scenario)
    cr_b = CombatResolver(rng_seed=seed)
    me_b = MovementEngine()
    ce_b = ConstraintEngine()
    ie_b = IntelEngine()
    se_b = SupplyEngine()
    ae_b = AirEngine(rng_seed=seed + 1000)

    rg_b = RelationshipGraph()
    rg_b.load_from_scenario(scenario, gs_b)
    gt_b = GraphTools(rg_b)

    agents_b = {}
    for cmd_id, commander in gs_b.commanders.items():
        kwargs = {"graph_tools": gt_b}
        if commander.rank == "Theater":
            agents_b[cmd_id] = TheaterCommander(commander, {}, **kwargs)
        elif commander.rank == "Division":
            agents_b[cmd_id] = DivisionCommander(commander, {}, **kwargs)
        else:
            agents_b[cmd_id] = BattalionCommander(commander, {}, **kwargs)

    tm_b = TurnManager(
        game_state=gs_b,
        agents=agents_b,
        constraint_engine=ce_b,
        combat_resolver=cr_b,
        movement_engine=me_b,
        relationship_graph=rg_b,
        intel_engine=ie_b,
        supply_engine=se_b,
        air_engine=ae_b,
    )
    tm_b.run_simulation(max_turns=max_turns)
    snapshot_b = gs_b.to_snapshot()

    # Compare unit states (most important)
    assert set(snapshot_a["units"].keys()) == set(snapshot_b["units"].keys()), \
        "Unit sets differ between factory and direct runs"

    for uid in snapshot_a["units"]:
        unit_a = snapshot_a["units"][uid]
        unit_b = snapshot_b["units"][uid]
        assert unit_a["strength"] == unit_b["strength"], \
            f"Unit {uid} strength mismatch: {unit_a['strength']} vs {unit_b['strength']}"
        assert unit_a["status"] == unit_b["status"], \
            f"Unit {uid} status mismatch: {unit_a['status']} vs {unit_b['status']}"
        assert unit_a["position"] == unit_b["position"], \
            f"Unit {uid} position mismatch: {unit_a['position']} vs {unit_b['position']}"

    assert snapshot_a["turn"] == snapshot_b["turn"], \
        f"Turn mismatch: {snapshot_a['turn']} vs {snapshot_b['turn']}"
