"""Tests for app.core.protocols and app.core.domain_registry."""
from __future__ import annotations
import pytest

import app.core.protocols as proto
import app.core.domain_registry as registry


# ---------------------------------------------------------------------------
# Mock implementations
# ---------------------------------------------------------------------------

class MockEntity:
    def __init__(self):
        self.id = "e1"
        self.side = "BLUE"
        self.status = "ACTIVE"
        self.position = (0, 0)


class MockAction:
    def __init__(self):
        self.action_type = "MOVE"
        self.entity_id = "e1"
        self.target = (1, 0)


class MockSpace:
    def neighbors(self, pos): return []
    def distance(self, a, b): return 0.0
    def is_passable(self, pos): return True


class MockGameState:
    def get_entity(self, entity_id): return None
    def get_entities_by_side(self, side): return []
    def advance_turn(self): pass
    def advance_phase(self): pass
    def to_snapshot(self): return {}


class MockInteractionResolver:
    def resolve(self, actors, targets, context): return {}


class MockMoverEngine:
    def execute_moves(self, actions, state): return []


class MockDomainConstraints:
    def validate(self, actions, state): return actions


class MockVictoryChecker:
    def check(self, state): return False


class MockCommandPhaseOrchestrator:
    def run_command_phase(self, state, agents): return []


class MockDomainStateFactory:
    def create_state(self, scenario): return {}
    def create_engines(self, scenario, params): return {}
    def create_agents(self, scenario, params): return {}


class MockDomainFactory:
    """Stub factory object used to test domain registry."""
    pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_registry():
    """Ensure registry is empty before and after each test."""
    registry.clear()
    yield
    registry.clear()


# ---------------------------------------------------------------------------
# 1. All 10 Protocols exist in the module
# ---------------------------------------------------------------------------

def test_all_protocols_exist():
    expected = [
        "Entity", "Action", "Space", "GameStateProtocol",
        "InteractionResolver", "MoverEngine", "DomainConstraints",
        "VictoryChecker", "CommandPhaseOrchestrator", "DomainStateFactory",
    ]
    for name in expected:
        assert hasattr(proto, name), f"Protocol '{name}' missing from protocols module"


# ---------------------------------------------------------------------------
# 2. Each Protocol is runtime_checkable
# ---------------------------------------------------------------------------

def test_entity_protocol_is_runtime_checkable():
    assert isinstance(MockEntity(), proto.Entity)


def test_action_protocol_is_runtime_checkable():
    assert isinstance(MockAction(), proto.Action)


def test_space_protocol_is_runtime_checkable():
    assert isinstance(MockSpace(), proto.Space)


def test_game_state_protocol_is_runtime_checkable():
    assert isinstance(MockGameState(), proto.GameStateProtocol)


def test_interaction_resolver_protocol_is_runtime_checkable():
    assert isinstance(MockInteractionResolver(), proto.InteractionResolver)


def test_mover_engine_protocol_is_runtime_checkable():
    assert isinstance(MockMoverEngine(), proto.MoverEngine)


def test_domain_constraints_protocol_is_runtime_checkable():
    assert isinstance(MockDomainConstraints(), proto.DomainConstraints)


def test_victory_checker_protocol_is_runtime_checkable():
    assert isinstance(MockVictoryChecker(), proto.VictoryChecker)


def test_command_phase_orchestrator_protocol_is_runtime_checkable():
    assert isinstance(MockCommandPhaseOrchestrator(), proto.CommandPhaseOrchestrator)


def test_domain_state_factory_protocol_is_runtime_checkable():
    assert isinstance(MockDomainStateFactory(), proto.DomainStateFactory)


# ---------------------------------------------------------------------------
# 3. Missing required attribute/method fails isinstance
# ---------------------------------------------------------------------------

def test_entity_missing_attribute_fails():
    class Bad:
        id = "x"
        side = "RED"
        # missing status and position

    assert not isinstance(Bad(), proto.Entity)


def test_space_missing_method_fails():
    class BadSpace:
        def neighbors(self, pos): return []
        # missing distance and is_passable

    assert not isinstance(BadSpace(), proto.Space)


def test_game_state_missing_method_fails():
    class BadState:
        def get_entity(self, entity_id): return None
        def get_entities_by_side(self, side): return []
        # missing advance_turn, advance_phase, to_snapshot

    assert not isinstance(BadState(), proto.GameStateProtocol)


# ---------------------------------------------------------------------------
# 4. DomainRegistry tests
# ---------------------------------------------------------------------------

def test_registry_register_and_get():
    factory = MockDomainFactory()
    registry.register("military", factory)
    assert registry.get("military") is factory


def test_registry_get_unknown_raises_key_error():
    with pytest.raises(KeyError, match="not registered"):
        registry.get("nonexistent")


def test_registry_list_domains_empty():
    assert registry.list_domains() == []


def test_registry_list_domains_after_registration():
    registry.register("military", MockDomainFactory())
    registry.register("business", MockDomainFactory())
    domains = registry.list_domains()
    assert "military" in domains
    assert "business" in domains
    assert len(domains) == 2


def test_registry_clear():
    registry.register("military", MockDomainFactory())
    registry.clear()
    assert registry.list_domains() == []


def test_registry_overwrite_existing():
    first = MockDomainFactory()
    second = MockDomainFactory()
    registry.register("military", first)
    registry.register("military", second)
    assert registry.get("military") is second


def test_registry_key_error_message_includes_available():
    registry.register("military", MockDomainFactory())
    with pytest.raises(KeyError) as exc_info:
        registry.get("unknown")
    assert "military" in str(exc_info.value)


def test_registry_multiple_domains_independent():
    f1, f2 = MockDomainFactory(), MockDomainFactory()
    registry.register("a", f1)
    registry.register("b", f2)
    assert registry.get("a") is f1
    assert registry.get("b") is f2
