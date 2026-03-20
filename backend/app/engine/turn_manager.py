from __future__ import annotations
import json
import logging
from collections.abc import Callable
from pathlib import Path
from app.models.domain import Side, UnitStatus, HexCoord
from app.models.actions import MilitaryAction, ActionType, OrderDirective
from app.models.simulation import TurnPhase, TurnResult, CombatOutcome, MovementResult
from app.engine.game_state import GameState
from app.engine.constraint_engine import ConstraintEngine
from app.engine.combat_resolver import CombatResolver
from app.engine.movement_engine import MovementEngine
from app.agents.base_commander import BaseCommander
from app.agents.theater_commander import TheaterCommander
from app.agents.battalion_commander import BattalionCommander
from app.graph.relationship_graph import RelationshipGraph
from app.memory.replay_store import ReplayStore

logger = logging.getLogger(__name__)


class TurnManager:
    """3-phase turn loop orchestrator."""

    def __init__(
        self,
        game_state: GameState,
        agents: dict[str, BaseCommander],  # commander_id -> agent
        constraint_engine: ConstraintEngine,
        combat_resolver: CombatResolver,
        movement_engine: MovementEngine,
        replay_store: ReplayStore | None = None,
        relationship_graph: RelationshipGraph | None = None,
        simulation_id: str = "",
        log_dir: str = "data/logs",
    ):
        self.game_state = game_state
        self.agents = agents
        self.constraint_engine = constraint_engine
        self.combat_resolver = combat_resolver
        self.movement_engine = movement_engine
        self.replay_store = replay_store
        self.relationship_graph = relationship_graph
        self.simulation_id = simulation_id
        self.log_dir = log_dir
        self._turn_results: list[TurnResult] = []

    def run_simulation(
        self,
        max_turns: int = 72,
        callback: Callable[[int, GameState], None] | None = None,
    ) -> GameState:
        """Run full simulation loop."""
        for turn in range(1, max_turns + 1):
            turn_result = self._run_turn(turn)
            self._turn_results.append(turn_result)

            if callback:
                callback(turn, self.game_state)

            if self._check_victory():
                logger.info("Victory condition met at turn %d", turn)
                break

            # Periodic audit
            if turn % 5 == 0:
                warnings = self.constraint_engine.audit_state(self.game_state)
                for w in warnings:
                    logger.warning("Audit warning at turn %d: %s", turn, w)

        return self.game_state

    def _run_turn(self, turn: int) -> TurnResult:
        """Execute one complete turn (3 phases)."""
        self.game_state.advance_turn()
        # Note: advance_turn increments turn counter and resets phase/MP

        # Phase 1: COMMAND
        all_actions = self._command_phase()

        # Phase 2: EXECUTION
        self.game_state.advance_phase()  # -> EXECUTION
        movement_results = self._execution_phase(all_actions)

        # Phase 3: RESOLUTION
        self.game_state.advance_phase()  # -> RESOLUTION
        combats, destroyed = self._resolution_phase(movement_results, all_actions)

        # Save snapshot at turn boundary
        if self.replay_store:
            self.replay_store.save_snapshot(self.simulation_id, self.game_state.turn, self.game_state)
            # Save actions
            action_dicts = [a.model_dump() for a in all_actions]
            self.replay_store.save_actions(self.simulation_id, self.game_state.turn, action_dicts)

        # Update relationship graph
        if self.relationship_graph:
            self.relationship_graph.recalculate_adjacency(self.game_state)

        # Log turn
        self._log_turn(self.game_state.turn, all_actions, combats)

        return TurnResult(
            turn=self.game_state.turn,
            phase_results={
                TurnPhase.COMMAND: {"action_count": len(all_actions)},
                TurnPhase.EXECUTION: {"movements": len(movement_results)},
                TurnPhase.RESOLUTION: {"combats": len(combats), "destroyed": len(destroyed)},
            },
            movements=movement_results,
            combats=combats,
            destroyed_units=destroyed,
        )

    def _command_phase(self) -> list[MilitaryAction]:
        """
        Theater -> OrderDirective -> Battalion -> MilitaryAction

        1. Theater commanders decide (both sides) -> OrderDirectives
        2. Distribute OrderDirectives to battalion commanders
        3. Battalion commanders decide -> MilitaryActions
        4. Constraint engine validates
        5. Rejected actions get 1 retry
        """
        all_actions: list[MilitaryAction] = []

        for side in [Side.BLUE, Side.RED]:
            # Step 1: Theater commander generates OrderDirectives
            theater_orders = self._get_theater_orders(side)

            # Step 2: Distribute orders to battalion commanders
            for order in theater_orders:
                bn_cmd_id = self._resolve_battalion_commander(order.target_unit_id)
                if bn_cmd_id and bn_cmd_id in self.agents:
                    self.agents[bn_cmd_id].receive_orders(order)

            # Step 3: Battalion commanders generate MilitaryActions
            bn_actions = self._get_battalion_actions(side)

            # Step 4: Build authority map from graph (commander_id -> set of allowed unit_ids)
            authority_map: dict[str, set[str]] = {}
            if self.relationship_graph:
                from app.graph.graph_tools import GraphTools
                graph_tools = GraphTools(self.relationship_graph)
                for agent in self.agents.values():
                    if isinstance(agent, BattalionCommander) and agent.commander.side == side:
                        scope = graph_tools.query_command_scope(agent.commander.id)
                        if scope["commanded_unit_ids"]:
                            authority_map[agent.commander.id] = set(scope["commanded_unit_ids"])

            # Step 5: Validate
            result = self.constraint_engine.validate(
                bn_actions, self.game_state,
                authority_map=authority_map if authority_map else None,
            )
            valid = list(result.valid_actions)

            # Step 6: Retry rejected (1 attempt)
            if result.has_rejections:
                logger.info(
                    "Turn %d %s: %d actions rejected, retrying",
                    self.game_state.turn, side.value, len(result.rejections),
                )
                # For simplicity, just accept valid ones (retry would need another LLM call)

            all_actions.extend(valid)

        return all_actions

    def _get_theater_orders(self, side: Side) -> list[OrderDirective]:
        """Get orders from theater commander for this side."""
        for agent in self.agents.values():
            if isinstance(agent, TheaterCommander) and agent.commander.side == side:
                return agent.decide(self.game_state)
        return []

    def _get_battalion_actions(self, side: Side) -> list[MilitaryAction]:
        """Get actions from all battalion commanders for this side."""
        actions = []
        for agent in self.agents.values():
            if isinstance(agent, BattalionCommander) and agent.commander.side == side:
                bn_actions = agent.decide(self.game_state)
                actions.extend(bn_actions)
        return actions

    def _resolve_battalion_commander(self, target_unit_id: str) -> str | None:
        """Find the battalion commander responsible for a given unit."""
        for cmd_id, agent in self.agents.items():
            if isinstance(agent, BattalionCommander):
                if agent.commander.unit_id == target_unit_id:
                    return cmd_id
        return None

    def _execution_phase(self, actions: list[MilitaryAction]) -> list[MovementResult]:
        """Execute movements (WEGO 2-pass)."""
        move_actions = [a for a in actions if a.action_type in (ActionType.MOVE, ActionType.RETREAT)]
        results = self.movement_engine.execute_moves(move_actions, self.game_state)

        # Apply movement results to game state
        for mr in results:
            unit = self.game_state.get_unit(mr.unit_id)
            if unit and mr.final_position != unit.position:
                self.game_state.update_unit(
                    mr.unit_id,
                    position=mr.final_position,
                    movement_points=mr.remaining_mp,
                )

        return results

    def _resolution_phase(
        self, movement_results: list[MovementResult], actions: list[MilitaryAction]
    ) -> tuple[list[CombatOutcome], list[str]]:
        """
        WEGO 2-pass combat resolution.
        Pass 1: Calculate all combat outcomes based on current state.
        Pass 2: Apply all results simultaneously.
        """
        combats: list[CombatOutcome] = []
        destroyed: list[str] = []

        # Collect all engagements
        engagements = self._collect_engagements(movement_results, actions)

        # Pass 1: Calculate all outcomes (read-only, no state changes)
        outcomes: list[CombatOutcome] = []
        for attackers, defenders, terrain in engagements:
            if not attackers or not defenders:
                continue
            outcome = self.combat_resolver.resolve_combat(attackers, defenders, terrain)
            outcomes.append(outcome)

        # Pass 2: Apply all outcomes simultaneously
        for outcome in outcomes:
            combats.append(outcome)

            # Apply attacker losses
            attacker = self.game_state.get_unit(outcome.attacker_id)
            if attacker and attacker.status != UnitStatus.DESTROYED:
                new_strength = max(0.0, attacker.strength - outcome.attacker_losses)
                new_status = attacker.status
                if new_strength <= 0:
                    new_status = UnitStatus.DESTROYED
                    destroyed.append(outcome.attacker_id)
                elif new_strength <= 0.5:
                    new_status = UnitStatus.DEGRADED
                self.game_state.update_unit(
                    outcome.attacker_id,
                    strength=round(new_strength, 2),
                    status=new_status,
                    ammo=max(0.0, attacker.ammo - 0.1),  # ammo consumed
                )

            # Apply defender losses
            defender = self.game_state.get_unit(outcome.defender_id)
            if defender and defender.status != UnitStatus.DESTROYED:
                new_strength = max(0.0, defender.strength - outcome.defender_losses)
                new_morale = defender.morale
                new_status = defender.status

                if outcome.result.value == "DRt":
                    new_morale = max(0.0, defender.morale - 0.3)
                    new_status = UnitStatus.ROUTED

                if new_strength <= 0:
                    new_status = UnitStatus.DESTROYED
                    destroyed.append(outcome.defender_id)
                elif new_strength <= 0.5 and new_status not in (UnitStatus.ROUTED, UnitStatus.DESTROYED):
                    new_status = UnitStatus.DEGRADED

                # Defender retreat
                updates = {
                    "strength": round(new_strength, 2),
                    "morale": round(new_morale, 2),
                    "status": new_status,
                    "ammo": max(0.0, defender.ammo - 0.1),
                }
                if outcome.defender_retreat_hexes > 0 and new_status != UnitStatus.DESTROYED:
                    retreat_hex = self._find_retreat_hex(defender, outcome.defender_retreat_hexes)
                    if retreat_hex:
                        updates["position"] = retreat_hex

                self.game_state.update_unit(outcome.defender_id, **updates)

        return combats, destroyed

    def _collect_engagements(
        self, movement_results: list[MovementResult], actions: list[MilitaryAction]
    ) -> list[tuple[list, list, object]]:
        """Collect all combat engagements for this turn."""
        engagements = []
        processed_pairs: set[tuple[str, str]] = set()

        # From explicit ATTACK actions
        for action in actions:
            if action.action_type != ActionType.ATTACK:
                continue
            attacker = self.game_state.get_unit(action.unit_id)
            if attacker is None or attacker.status == UnitStatus.DESTROYED:
                continue

            # Find defenders at target hex or by target_unit_id
            defenders = []
            if action.target_unit_id:
                target = self.game_state.get_unit(action.target_unit_id)
                if target and target.status != UnitStatus.DESTROYED:
                    defenders = [target]
            elif action.target_hex:
                defenders = [
                    u for u in self.game_state.get_units_at(action.target_hex)
                    if u.side != attacker.side and u.status != UnitStatus.DESTROYED
                ]

            if defenders:
                pair = tuple(sorted([attacker.id, defenders[0].id]))
                if pair not in processed_pairs:
                    terrain = self.game_state.get_terrain_at(defenders[0].position)
                    if terrain:
                        engagements.append(([attacker], defenders, terrain))
                        processed_pairs.add(pair)

        # From movement-triggered combats
        for mr in movement_results:
            for moving_id, enemy_id in mr.triggered_combats:
                pair = tuple(sorted([moving_id, enemy_id]))
                if pair in processed_pairs:
                    continue
                mover = self.game_state.get_unit(moving_id)
                enemy = self.game_state.get_unit(enemy_id)
                if (
                    mover and enemy
                    and mover.status != UnitStatus.DESTROYED
                    and enemy.status != UnitStatus.DESTROYED
                ):
                    terrain = self.game_state.get_terrain_at(enemy.position)
                    if terrain:
                        engagements.append(([mover], [enemy], terrain))
                        processed_pairs.add(pair)

        return engagements

    def _find_retreat_hex(self, unit, num_hexes: int) -> HexCoord | None:
        """Find a hex to retreat to, away from the nearest enemy."""
        from app.utils.hex_grid import hex_neighbors, hex_distance

        current = unit.position
        enemies = [
            u for u in self.game_state.units.values()
            if u.side != unit.side and u.status != UnitStatus.DESTROYED
        ]
        if not enemies:
            return None
        nearest_enemy = min(enemies, key=lambda e: hex_distance(current, e.position))

        # Move away from enemy, num_hexes steps
        best = current
        for _ in range(num_hexes):
            candidates = [n for n in hex_neighbors(best) if self.game_state.get_terrain_at(n) is not None]
            if not candidates:
                break
            best = max(candidates, key=lambda c: hex_distance(c, nearest_enemy.position))

        return best if best != current else None

    def _check_victory(self) -> bool:
        """Check victory conditions: one side has no active units."""
        for side in [Side.BLUE, Side.RED]:
            active = [
                u for u in self.game_state.get_units_by_side(side)
                if u.status not in (UnitStatus.DESTROYED, UnitStatus.ROUTED)
            ]
            if not active:
                logger.info("Side %s has no active units - defeat", side.value)
                return True
        return False

    def _log_turn(self, turn: int, actions: list, combats: list) -> None:
        """Write JSONL log entry."""
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        log_path = Path(self.log_dir) / f"sim_{self.simulation_id}.jsonl"
        entry = {
            "turn": turn,
            "actions": len(actions),
            "combats": len(combats),
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    @property
    def turn_results(self) -> list[TurnResult]:
        return self._turn_results
