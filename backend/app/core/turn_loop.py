from __future__ import annotations
from typing import Any, Callable
import logging

logger = logging.getLogger(__name__)


class TurnLoop:
    """Domain-agnostic simulation turn loop with hook system.

    3-phase loop: COMMAND -> EXECUTION -> RESOLUTION
    Delegates all domain logic to Protocol implementations.
    Cross-cutting concerns (intel, supply, etc.) handled via hooks.
    """

    def __init__(
        self,
        state: Any,  # GameStateProtocol
        command_orchestrator: Any,  # CommandPhaseOrchestrator
        mover: Any,  # MoverEngine
        interaction_resolver: Any,  # InteractionResolver
        constraints: Any,  # DomainConstraints
        victory_checker: Any,  # VictoryChecker
        agents: dict,
    ):
        self.state = state
        self.command_orchestrator = command_orchestrator
        self.mover = mover
        self.interaction_resolver = interaction_resolver
        self.constraints = constraints
        self.victory_checker = victory_checker
        self.agents = agents

        # Hook registry: phase_name -> list of callbacks
        self._hooks: dict[str, list[Callable]] = {
            "pre_turn": [],
            "post_command": [],
            "post_resolution": [],
            "post_turn": [],
        }
        self._turn_results: list[dict] = []

    def register_hook(self, phase: str, callback: Callable) -> None:
        """Register a hook callback for a phase."""
        if phase not in self._hooks:
            raise ValueError(
                f"Unknown hook phase: {phase}. Valid: {list(self._hooks.keys())}"
            )
        self._hooks[phase].append(callback)

    def _run_hooks(self, phase: str, **kwargs) -> None:
        """Run all hooks for a phase."""
        for hook in self._hooks[phase]:
            try:
                hook(self.state, **kwargs)
            except Exception as e:
                logger.warning("Hook failed in %s: %s", phase, e)

    def run_simulation(self, max_turns: int = 72) -> dict:
        """Run full simulation. Returns summary dict."""
        for turn in range(1, max_turns + 1):
            turn_result = self._run_turn(turn)
            self._turn_results.append(turn_result)

            if self.victory_checker.check(self.state):
                logger.info("Victory condition met at turn %d", turn)
                break

        return {
            "total_turns": (
                self.state.turn
                if hasattr(self.state, "turn")
                else len(self._turn_results)
            ),
            "turn_results": self._turn_results,
        }

    def _run_turn(self, turn: int) -> dict:
        """Execute one turn."""
        self.state.advance_turn()

        # Pre-turn hooks (intel update, supply calculation, etc.)
        self._run_hooks("pre_turn")

        # Phase 1: COMMAND
        actions = self.command_orchestrator.run_command_phase(self.state, self.agents)
        self._run_hooks("post_command", actions=actions)

        # Phase 2: EXECUTION
        self.state.advance_phase()
        move_actions = [
            a
            for a in actions
            if hasattr(a, "action_type") and a.action_type in ("MOVE", "RETREAT")
        ]
        move_results = (
            self.mover.execute_moves(move_actions, self.state) if move_actions else []
        )

        # Apply movement results
        for mr in move_results:
            if hasattr(mr, "unit_id") and hasattr(mr, "final_position"):
                entity = (
                    self.state.get_entity(mr.unit_id)
                    if hasattr(self.state, "get_entity")
                    else self.state.get_unit(mr.unit_id)
                )
                if entity and mr.final_position != entity.position:
                    self.state.update_unit(
                        mr.unit_id,
                        position=mr.final_position,
                        movement_points=mr.remaining_mp,
                    )

        # Phase 3: RESOLUTION
        self.state.advance_phase()
        combats = self._resolve_interactions(move_results, actions)

        self._run_hooks("post_resolution", actions=actions, combats=combats)

        # Post-turn hooks (supply effects, intel degradation, graph update, etc.)
        self._run_hooks(
            "post_turn", actions=actions, combats=combats, move_results=move_results
        )

        return {
            "turn": (
                self.state.turn if hasattr(self.state, "turn") else turn
            ),
            "actions": len(actions),
            "movements": len(move_results),
            "combats": len(combats),
        }

    def _resolve_interactions(self, move_results, actions) -> list:
        """Collect and resolve interactions. Domain hooks can enhance."""
        combats = []
        for action in actions:
            if (
                hasattr(action, "action_type")
                and action.action_type == "ATTACK"
            ):
                unit_id = (
                    action.unit_id
                    if hasattr(action, "unit_id")
                    else getattr(action, "entity_id", None)
                )
                actor = None
                if unit_id:
                    actor = (
                        self.state.get_unit(unit_id)
                        if hasattr(self.state, "get_unit")
                        else self.state.get_entity(unit_id)
                    )
                if actor is None:
                    continue
                target = None
                if hasattr(action, "target_unit_id") and action.target_unit_id:
                    target = (
                        self.state.get_unit(action.target_unit_id)
                        if hasattr(self.state, "get_unit")
                        else None
                    )
                if target:
                    terrain = (
                        self.state.get_terrain_at(target.position)
                        if hasattr(self.state, "get_terrain_at")
                        else None
                    )
                    result = self.interaction_resolver.resolve(
                        [actor], [target], {"terrain": terrain}
                    )
                    combats.append(result)
        return combats

    @property
    def turn_results(self) -> list[dict]:
        return self._turn_results
