from __future__ import annotations
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Entity(Protocol):
    """Domain entity (unit, business unit, etc.)."""
    id: str
    side: str
    status: str
    position: Any


@runtime_checkable
class Action(Protocol):
    """Domain action (military action, business decision, etc.)."""
    action_type: str
    entity_id: str
    target: Any


@runtime_checkable
class Space(Protocol):
    """Spatial model (hex grid, market graph, etc.)."""
    def neighbors(self, pos: Any) -> list: ...
    def distance(self, a: Any, b: Any) -> float: ...
    def is_passable(self, pos: Any) -> bool: ...


@runtime_checkable
class GameStateProtocol(Protocol):
    """Minimum state interface for TurnLoop."""
    def get_entity(self, entity_id: str) -> Entity | None: ...
    def get_entities_by_side(self, side: str) -> list: ...
    def advance_turn(self) -> None: ...
    def advance_phase(self) -> None: ...
    def to_snapshot(self) -> dict: ...


@runtime_checkable
class InteractionResolver(Protocol):
    """Resolves interactions between entities (combat, competition, etc.)."""
    def resolve(self, actors: list, targets: list, context: dict) -> dict: ...


@runtime_checkable
class MoverEngine(Protocol):
    """Handles entity movement/expansion."""
    def execute_moves(self, actions: list, state: Any) -> list: ...


@runtime_checkable
class DomainConstraints(Protocol):
    """Validates actions against domain rules."""
    def validate(self, actions: list, state: Any) -> Any: ...


@runtime_checkable
class VictoryChecker(Protocol):
    """Checks victory/end conditions."""
    def check(self, state: Any) -> bool: ...


@runtime_checkable
class CommandPhaseOrchestrator(Protocol):
    """Orchestrates command phase (military 3-tier, business hierarchy, etc.)."""
    def run_command_phase(self, state: Any, agents: dict) -> list: ...


@runtime_checkable
class DomainStateFactory(Protocol):
    """Factory for creating domain-specific state, engines, and agents."""
    def create_state(self, scenario: dict) -> Any: ...
    def create_engines(self, scenario: dict, params: dict) -> dict: ...
    def create_agents(self, scenario: dict, params: dict) -> dict: ...
