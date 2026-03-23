from __future__ import annotations
from typing import Any
from app.core.protocols import Space, InteractionResolver, MoverEngine, DomainConstraints, VictoryChecker, CommandPhaseOrchestrator
from app.utils.hex_grid import hex_neighbors, hex_distance
from app.models.domain import HexCoord, TerrainType, Side, UnitStatus


class MilitarySpace:
    """Adapts hex_grid functions to Space Protocol."""

    def __init__(self, terrain_map: dict):
        self._terrain = terrain_map

    def neighbors(self, pos: Any) -> list:
        if isinstance(pos, HexCoord):
            return [n for n in hex_neighbors(pos) if n in self._terrain]
        return []

    def distance(self, a: Any, b: Any) -> float:
        if isinstance(a, HexCoord) and isinstance(b, HexCoord):
            return float(hex_distance(a, b))
        return float('inf')

    def is_passable(self, pos: Any) -> bool:
        terrain = self._terrain.get(pos)
        if terrain is None:
            return False
        return terrain.terrain_type != TerrainType.WATER


class MilitaryInteractionResolver:
    """Adapts CombatResolver to InteractionResolver Protocol."""

    def __init__(self, combat_resolver):
        self._resolver = combat_resolver

    def resolve(self, actors: list, targets: list, context: dict) -> dict:
        terrain = context.get("terrain")
        cas_modifier = context.get("cas_modifier", 0.0)
        supply_status_map = context.get("supply_status_map")
        outcome = self._resolver.resolve_combat(
            actors, targets, terrain,
            cas_modifier=cas_modifier,
            supply_status_map=supply_status_map,
        )
        return {
            "outcome": outcome,
            "attacker_id": outcome.attacker_id,
            "defender_id": outcome.defender_id,
            "result": outcome.result.value,
            "attacker_losses": outcome.attacker_losses,
            "defender_losses": outcome.defender_losses,
        }


class MilitaryMover:
    """Adapts MovementEngine to MoverEngine Protocol."""

    def __init__(self, movement_engine):
        self._engine = movement_engine

    def execute_moves(self, actions: list, state: Any) -> list:
        return self._engine.execute_moves(actions, state)


class MilitaryConstraints:
    """Adapts ConstraintEngine to DomainConstraints Protocol."""

    def __init__(self, constraint_engine):
        self._engine = constraint_engine

    def validate(self, actions: list, state: Any, **kwargs) -> Any:
        return self._engine.validate(actions, state, **kwargs)


class MilitaryVictory:
    """Extracts victory check logic from TurnManager."""

    def check(self, state: Any) -> bool:
        for side in [Side.BLUE, Side.RED]:
            active = [
                u for u in state.get_units_by_side(side)
                if u.status not in (UnitStatus.DESTROYED, UnitStatus.ROUTED)
            ]
            if not active:
                return True
        return False


class MilitaryCommandOrchestrator:
    """Encapsulates the 3-tier Theater->Division->Battalion command flow."""

    def __init__(self, relationship_graph=None, constraint_engine=None):
        self._graph = relationship_graph
        self._constraint = constraint_engine

    def run_command_phase(self, state: Any, agents: dict) -> list:
        """Execute 3-tier command phase. Mirrors TurnManager._command_phase() logic."""
        from app.agents.theater_commander import TheaterCommander
        from app.agents.division_commander import DivisionCommander
        from app.agents.battalion_commander import BattalionCommander
        from app.models.domain import Side
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import logging

        logger = logging.getLogger(__name__)
        all_actions = []

        # Helper: parallel agent calls
        def call_parallel(agents_list, game_state):
            if not agents_list:
                return []
            if len(agents_list) == 1:
                return agents_list[0].decide(game_state)
            results = []
            with ThreadPoolExecutor(max_workers=min(len(agents_list), 6)) as ex:
                futures = {ex.submit(a.decide, game_state): a for a in agents_list}
                for f in as_completed(futures):
                    try:
                        results.extend(f.result(timeout=60))
                    except Exception as e:
                        logger.warning("Agent call failed: %s", e)
            return results

        # Step 1: Theater commanders (parallel)
        theater_agents = [a for a in agents.values() if isinstance(a, TheaterCommander)]
        theater_results = call_parallel(theater_agents, state)

        # Group theater orders by side
        theater_orders_by_side = {}
        for order in theater_results:
            issuer = next(
                (a for a in agents.values() if hasattr(a, 'commander') and a.commander.id == order.issuer_id),
                None,
            )
            if issuer:
                side = issuer.commander.side.value
                theater_orders_by_side.setdefault(side, []).append(order)

        # Step 2-3: Distribute to divisions, get division orders
        for side in [Side.BLUE, Side.RED]:
            side_orders = theater_orders_by_side.get(side.value, [])
            div_cmds = {
                cid: a for cid, a in agents.items()
                if isinstance(a, DivisionCommander) and a.commander.side == side
            }

            if div_cmds:
                for order in side_orders:
                    for div_agent in div_cmds.values():
                        if div_agent.graph_tools:
                            scope = div_agent.graph_tools.query_command_scope(div_agent.commander.id)
                            if order.target_unit_id in scope.get("commanded_unit_ids", []):
                                div_agent.receive_orders(order)
                                break
            else:
                # 2-tier fallback: distribute theater orders directly to battalions
                for order in side_orders:
                    for cid, agent in agents.items():
                        if isinstance(agent, BattalionCommander) and agent.commander.unit_id == order.target_unit_id:
                            agent.receive_orders(order)
                            break

        # Step 3: Division commanders (parallel)
        div_agents = [a for a in agents.values() if isinstance(a, DivisionCommander)]
        if div_agents:
            div_results = call_parallel(div_agents, state)
            for order in div_results:
                for cid, agent in agents.items():
                    if isinstance(agent, BattalionCommander) and agent.commander.unit_id == order.target_unit_id:
                        agent.receive_orders(order)
                        break

        # Step 4: Battalion commanders (parallel)
        bn_agents = [a for a in agents.values() if isinstance(a, BattalionCommander)]
        bn_actions = call_parallel(bn_agents, state)

        # Step 5: Validate per side
        for side in [Side.BLUE, Side.RED]:
            side_actions = [
                a for a in bn_actions
                if state.get_unit(a.unit_id) and state.get_unit(a.unit_id).side == side
            ]

            authority_map = {}
            if self._graph:
                from app.graph.graph_tools import GraphTools
                gt = GraphTools(self._graph)
                for agent in agents.values():
                    if isinstance(agent, BattalionCommander) and agent.commander.side == side:
                        scope = gt.query_command_scope(agent.commander.id)
                        if scope["commanded_unit_ids"]:
                            authority_map[agent.commander.id] = set(scope["commanded_unit_ids"])

            if self._constraint:
                result = self._constraint.validate(
                    side_actions, state,
                    authority_map=authority_map if authority_map else None,
                )
                all_actions.extend(list(result.valid_actions))
            else:
                all_actions.extend(side_actions)

        return all_actions
