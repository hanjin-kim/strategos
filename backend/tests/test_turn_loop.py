"""Tests for app.core.turn_loop.TurnLoop."""
from __future__ import annotations

import pytest

from app.core.turn_loop import TurnLoop


# ---------------------------------------------------------------------------
# Mock Protocol implementations
# ---------------------------------------------------------------------------

class MockState:
    """Minimal GameStateProtocol mock."""

    def __init__(self, turns_until_victory: int = 999):
        self.turn = 0
        self.phase = 0
        self._turns_until_victory = turns_until_victory
        self.units: dict = {}

    def get_entity(self, entity_id: str):
        return None

    def get_entities_by_side(self, side: str) -> list:
        return []

    def get_unit(self, unit_id: str):
        return self.units.get(unit_id)

    def advance_turn(self) -> None:
        self.turn += 1
        self.phase = 0

    def advance_phase(self) -> None:
        self.phase += 1

    def to_snapshot(self) -> dict:
        return {"turn": self.turn}

    def update_unit(self, unit_id: str, **kwargs) -> None:
        if unit_id in self.units:
            for k, v in kwargs.items():
                setattr(self.units[unit_id], k, v)


class MockOrchestrator:
    """Mock CommandPhaseOrchestrator."""

    def __init__(self, actions=None):
        self._actions = actions or []
        self.call_count = 0

    def run_command_phase(self, state, agents: dict) -> list:
        self.call_count += 1
        return list(self._actions)


class MockMover:
    """Mock MoverEngine."""

    def __init__(self, results=None):
        self._results = results or []
        self.call_count = 0

    def execute_moves(self, actions: list, state) -> list:
        self.call_count += 1
        return list(self._results)


class MockResolver:
    """Mock InteractionResolver."""

    def __init__(self):
        self.call_count = 0

    def resolve(self, actors: list, targets: list, context: dict) -> dict:
        self.call_count += 1
        return {"result": "ATTACKER_WINS"}


class MockConstraints:
    """Mock DomainConstraints."""

    def validate(self, actions: list, state) -> list:
        return actions


class MockVictory:
    """Mock VictoryChecker — never triggers."""

    def check(self, state) -> bool:
        return False


class MockVictoryAfterN:
    """Mock VictoryChecker that triggers after N turns."""

    def __init__(self, stop_at: int):
        self._stop_at = stop_at

    def check(self, state) -> bool:
        return state.turn >= self._stop_at


class MockAction:
    """Minimal action stub."""

    def __init__(self, action_type: str, unit_id: str = "u1", target_unit_id: str | None = None):
        self.action_type = action_type
        self.unit_id = unit_id
        self.target_unit_id = target_unit_id


# ---------------------------------------------------------------------------
# Helper to build a default TurnLoop
# ---------------------------------------------------------------------------

def _make_loop(
    state=None,
    orchestrator=None,
    mover=None,
    resolver=None,
    constraints=None,
    victory=None,
    agents=None,
) -> TurnLoop:
    return TurnLoop(
        state=state or MockState(),
        command_orchestrator=orchestrator or MockOrchestrator(),
        mover=mover or MockMover(),
        interaction_resolver=resolver or MockResolver(),
        constraints=constraints or MockConstraints(),
        victory_checker=victory or MockVictory(),
        agents=agents or {},
    )


# ---------------------------------------------------------------------------
# 1. run_simulation runs N turns when victory never fires
# ---------------------------------------------------------------------------

def test_run_simulation_runs_max_turns():
    state = MockState()
    loop = _make_loop(state=state, victory=MockVictory())
    loop.run_simulation(max_turns=5)
    assert state.turn == 5


def test_run_simulation_returns_summary_dict():
    loop = _make_loop()
    result = loop.run_simulation(max_turns=3)
    assert isinstance(result, dict)
    assert "total_turns" in result
    assert "turn_results" in result


def test_run_simulation_summary_total_turns_matches_state():
    state = MockState()
    loop = _make_loop(state=state)
    result = loop.run_simulation(max_turns=4)
    assert result["total_turns"] == state.turn


def test_turn_results_accumulated_correctly():
    loop = _make_loop()
    loop.run_simulation(max_turns=3)
    assert len(loop.turn_results) == 3


def test_turn_result_fields_present():
    loop = _make_loop()
    loop.run_simulation(max_turns=1)
    tr = loop.turn_results[0]
    assert "turn" in tr
    assert "actions" in tr
    assert "movements" in tr
    assert "combats" in tr


# ---------------------------------------------------------------------------
# 2. Victory checker stops simulation early
# ---------------------------------------------------------------------------

def test_victory_checker_stops_simulation():
    state = MockState()
    loop = _make_loop(state=state, victory=MockVictoryAfterN(stop_at=3))
    loop.run_simulation(max_turns=10)
    assert state.turn == 3


def test_victory_checker_at_turn_1_stops_immediately():
    state = MockState()
    loop = _make_loop(state=state, victory=MockVictoryAfterN(stop_at=1))
    result = loop.run_simulation(max_turns=10)
    assert state.turn == 1
    assert len(loop.turn_results) == 1


# ---------------------------------------------------------------------------
# 3. COMMAND phase delegates to orchestrator
# ---------------------------------------------------------------------------

def test_command_phase_delegates_to_orchestrator():
    orchestrator = MockOrchestrator()
    loop = _make_loop(orchestrator=orchestrator)
    loop.run_simulation(max_turns=2)
    assert orchestrator.call_count == 2


# ---------------------------------------------------------------------------
# 4. EXECUTION phase delegates to mover for MOVE actions
# ---------------------------------------------------------------------------

def test_execution_phase_calls_mover_for_move_actions():
    mover = MockMover()
    actions = [MockAction("MOVE", "u1")]
    orchestrator = MockOrchestrator(actions=actions)
    loop = _make_loop(orchestrator=orchestrator, mover=mover)
    loop.run_simulation(max_turns=1)
    assert mover.call_count == 1


def test_execution_phase_skips_mover_when_no_move_actions():
    mover = MockMover()
    actions = [MockAction("HOLD", "u1")]
    orchestrator = MockOrchestrator(actions=actions)
    loop = _make_loop(orchestrator=orchestrator, mover=mover)
    loop.run_simulation(max_turns=1)
    assert mover.call_count == 0


# ---------------------------------------------------------------------------
# 5. RESOLUTION phase delegates to resolver for ATTACK actions
# ---------------------------------------------------------------------------

class _MockUnit:
    def __init__(self, uid, position=(0, 0)):
        self.id = uid
        self.position = position
        self.side = "BLUE"
        self.status = "ACTIVE"


def test_resolution_phase_calls_resolver_for_attack_actions():
    resolver = MockResolver()
    state = MockState()
    state.units["u1"] = _MockUnit("u1", (0, 0))
    state.units["u2"] = _MockUnit("u2", (1, 0))
    actions = [MockAction("ATTACK", "u1", target_unit_id="u2")]
    orchestrator = MockOrchestrator(actions=actions)
    loop = _make_loop(state=state, orchestrator=orchestrator, resolver=resolver)
    loop.run_simulation(max_turns=1)
    assert resolver.call_count == 1


# ---------------------------------------------------------------------------
# 6. Hook registration and execution
# ---------------------------------------------------------------------------

def test_register_hook_invalid_phase_raises_value_error():
    loop = _make_loop()
    with pytest.raises(ValueError, match="Unknown hook phase"):
        loop.register_hook("invalid_phase", lambda s: None)


def test_pre_turn_hook_is_called():
    calls = []
    loop = _make_loop()
    loop.register_hook("pre_turn", lambda s: calls.append("pre_turn"))
    loop.run_simulation(max_turns=2)
    assert calls.count("pre_turn") == 2


def test_post_command_hook_receives_actions():
    received = []
    loop = _make_loop()
    loop.register_hook("post_command", lambda s, actions: received.append(actions))
    loop.run_simulation(max_turns=1)
    assert len(received) == 1


def test_post_resolution_hook_is_called():
    calls = []
    loop = _make_loop()
    loop.register_hook("post_resolution", lambda s, actions, combats: calls.append(1))
    loop.run_simulation(max_turns=1)
    assert calls == [1]


def test_post_turn_hook_is_called():
    calls = []
    loop = _make_loop()
    loop.register_hook("post_turn", lambda s, actions, combats, move_results: calls.append(1))
    loop.run_simulation(max_turns=3)
    assert len(calls) == 3


# ---------------------------------------------------------------------------
# 7. Hook failure does not crash the loop
# ---------------------------------------------------------------------------

def test_hook_failure_does_not_crash_simulation():
    def bad_hook(state):
        raise RuntimeError("hook exploded")

    loop = _make_loop()
    loop.register_hook("pre_turn", bad_hook)
    # Should not raise
    result = loop.run_simulation(max_turns=2)
    assert result["total_turns"] == 2


# ---------------------------------------------------------------------------
# 8. Multiple hooks on same phase all execute
# ---------------------------------------------------------------------------

def test_multiple_hooks_same_phase_all_called():
    calls = []
    loop = _make_loop()
    loop.register_hook("pre_turn", lambda s: calls.append("a"))
    loop.register_hook("pre_turn", lambda s: calls.append("b"))
    loop.run_simulation(max_turns=1)
    assert "a" in calls
    assert "b" in calls


# ---------------------------------------------------------------------------
# 9. TurnLoop with military adapters (minimal scenario, 3 turns)
# ---------------------------------------------------------------------------

def _minimal_scenario() -> dict:
    hexes = [
        {"q": q, "r": 0, "terrain": "PLAIN", "movement_cost": 1, "defense_modifier": 1.0}
        for q in range(-1, 8)
    ]
    return {
        "map": {"hexes": hexes},
        "forces": {
            "BLUE": {
                "name": "Blue Force",
                "units": [
                    {
                        "id": "blue_1",
                        "name": "Blue Bn 1",
                        "type": "INFANTRY",
                        "size": "BATTALION",
                        "position": {"q": 0, "r": 0},
                        "strength": 1.0,
                        "morale": 0.8,
                        "max_movement_points": 3,
                        "attack_power": 10.0,
                        "defense_power": 10.0,
                        "effective_range": 1,
                    }
                ],
                "commanders": [
                    {"id": "blue_tc", "name": "Blue Theater", "rank": "Theater", "unit_id": "blue_1"},
                    {"id": "blue_bn", "name": "Blue Bn Cmd", "rank": "Battalion", "unit_id": "blue_1"},
                ],
            },
            "RED": {
                "name": "Red Force",
                "units": [
                    {
                        "id": "red_1",
                        "name": "Red Bn 1",
                        "type": "INFANTRY",
                        "size": "BATTALION",
                        "position": {"q": 5, "r": 0},
                        "strength": 1.0,
                        "morale": 0.8,
                        "max_movement_points": 3,
                        "attack_power": 10.0,
                        "defense_power": 10.0,
                        "effective_range": 1,
                    }
                ],
                "commanders": [
                    {"id": "red_tc", "name": "Red Theater", "rank": "Theater", "unit_id": "red_1"},
                    {"id": "red_bn", "name": "Red Bn Cmd", "rank": "Battalion", "unit_id": "red_1"},
                ],
            },
        },
    }


def test_turn_loop_with_military_adapters_runs_3_turns():
    """TurnLoop wired to real military adapters runs 3 turns without error."""
    from app.engine.game_state import GameState
    from app.engine.combat_resolver import CombatResolver
    from app.engine.movement_engine import MovementEngine
    from app.engine.constraint_engine import ConstraintEngine
    from app.domains.military.adapters import (
        MilitaryInteractionResolver,
        MilitaryMover,
        MilitaryConstraints,
        MilitaryVictory,
        MilitaryCommandOrchestrator,
    )
    from app.graph.relationship_graph import RelationshipGraph
    from app.agents.theater_commander import TheaterCommander
    from app.agents.battalion_commander import BattalionCommander

    scenario = _minimal_scenario()
    game_state = GameState(scenario)

    combat_resolver = CombatResolver(rng_seed=42)
    movement_engine = MovementEngine()
    constraint_engine = ConstraintEngine()

    relationship_graph = RelationshipGraph()
    relationship_graph.load_from_scenario(scenario, game_state)

    from app.graph.graph_tools import GraphTools
    graph_tools = GraphTools(relationship_graph)

    llm_config = {"api_key": "", "base_url": "", "model": ""}
    agents = {}
    for cmd_id, commander in game_state.commanders.items():
        if commander.rank == "Theater":
            agents[cmd_id] = TheaterCommander(commander, llm_config, graph_tools=graph_tools)
        else:
            agents[cmd_id] = BattalionCommander(commander, llm_config, graph_tools=graph_tools)

    loop = TurnLoop(
        state=game_state,
        command_orchestrator=MilitaryCommandOrchestrator(relationship_graph, constraint_engine),
        mover=MilitaryMover(movement_engine),
        interaction_resolver=MilitaryInteractionResolver(combat_resolver),
        constraints=MilitaryConstraints(constraint_engine),
        victory_checker=MilitaryVictory(),
        agents=agents,
    )

    result = loop.run_simulation(max_turns=3)
    assert result["total_turns"] >= 1
    assert len(loop.turn_results) >= 1


def test_turn_loop_military_returns_dict_summary():
    """run_simulation always returns a dict with expected keys."""
    from app.engine.game_state import GameState
    from app.engine.combat_resolver import CombatResolver
    from app.engine.movement_engine import MovementEngine
    from app.engine.constraint_engine import ConstraintEngine
    from app.domains.military.adapters import (
        MilitaryInteractionResolver,
        MilitaryMover,
        MilitaryConstraints,
        MilitaryVictory,
        MilitaryCommandOrchestrator,
    )
    from app.graph.relationship_graph import RelationshipGraph
    from app.agents.theater_commander import TheaterCommander
    from app.agents.battalion_commander import BattalionCommander
    from app.graph.graph_tools import GraphTools

    scenario = _minimal_scenario()
    game_state = GameState(scenario)
    constraint_engine = ConstraintEngine()
    relationship_graph = RelationshipGraph()
    relationship_graph.load_from_scenario(scenario, game_state)
    graph_tools = GraphTools(relationship_graph)
    llm_config = {"api_key": "", "base_url": "", "model": ""}

    agents = {}
    for cmd_id, commander in game_state.commanders.items():
        if commander.rank == "Theater":
            agents[cmd_id] = TheaterCommander(commander, llm_config, graph_tools=graph_tools)
        else:
            agents[cmd_id] = BattalionCommander(commander, llm_config, graph_tools=graph_tools)

    loop = TurnLoop(
        state=game_state,
        command_orchestrator=MilitaryCommandOrchestrator(relationship_graph, constraint_engine),
        mover=MilitaryMover(MovementEngine()),
        interaction_resolver=MilitaryInteractionResolver(CombatResolver(rng_seed=7)),
        constraints=MilitaryConstraints(constraint_engine),
        victory_checker=MilitaryVictory(),
        agents=agents,
    )

    result = loop.run_simulation(max_turns=2)
    assert "total_turns" in result
    assert "turn_results" in result
    assert isinstance(result["turn_results"], list)
