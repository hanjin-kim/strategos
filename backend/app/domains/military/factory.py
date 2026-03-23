from __future__ import annotations
from typing import Any
from app.engine.game_state import GameState
from app.engine.combat_resolver import CombatResolver
from app.engine.movement_engine import MovementEngine
from app.engine.constraint_engine import ConstraintEngine
from app.engine.intel_engine import IntelEngine
from app.engine.supply_engine import SupplyEngine
from app.engine.air_engine import AirEngine
from app.agents.theater_commander import TheaterCommander
from app.agents.division_commander import DivisionCommander
from app.agents.battalion_commander import BattalionCommander
from app.graph.relationship_graph import RelationshipGraph
from app.graph.graph_tools import GraphTools
from app.domains.military.adapters import (
    MilitarySpace, MilitaryInteractionResolver, MilitaryMover,
    MilitaryConstraints, MilitaryVictory, MilitaryCommandOrchestrator,
)


class MilitaryDomainFactory:
    """Factory for military domain engines and agents."""

    def create_state(self, scenario: dict) -> GameState:
        return GameState(scenario)

    def create_engines(self, scenario: dict, params: dict | None = None) -> dict:
        rng_seed = params.get("rng_seed", 42) if params else 42

        game_state = self.create_state(scenario)
        combat_resolver = CombatResolver(rng_seed=rng_seed)
        movement_engine = MovementEngine()
        constraint_engine = ConstraintEngine()
        intel_engine = IntelEngine()
        supply_engine = SupplyEngine()
        air_engine = AirEngine(rng_seed=rng_seed + 1000)

        relationship_graph = RelationshipGraph()
        relationship_graph.load_from_scenario(scenario, game_state)

        return {
            "game_state": game_state,
            "space": MilitarySpace(game_state.terrain),
            "interaction_resolver": MilitaryInteractionResolver(combat_resolver),
            "mover": MilitaryMover(movement_engine),
            "constraints": MilitaryConstraints(constraint_engine),
            "victory_checker": MilitaryVictory(),
            "command_orchestrator": MilitaryCommandOrchestrator(relationship_graph, constraint_engine),
            # Raw engines for TurnManager backward compat
            "combat_resolver": combat_resolver,
            "movement_engine": movement_engine,
            "constraint_engine": constraint_engine,
            "intel_engine": intel_engine,
            "supply_engine": supply_engine,
            "air_engine": air_engine,
            "relationship_graph": relationship_graph,
        }

    def create_agents(self, scenario: dict, params: dict | None = None) -> dict:
        """Create agents for military scenario."""
        game_state = self.create_state(scenario)

        # Setup graph
        relationship_graph = RelationshipGraph()
        relationship_graph.load_from_scenario(scenario, game_state)
        graph_tools = GraphTools(relationship_graph)

        # LLM config
        use_llm = params.get("use_llm", False) if params else False
        llm_config = {"api_key": "", "base_url": "", "model": ""}
        if use_llm:
            try:
                from app.config import get_settings
                settings = get_settings()
                llm_config = {
                    "api_key": settings.LLM_API_KEY,
                    "base_url": settings.LLM_BASE_URL,
                    "model": settings.LLM_MODEL_NAME,
                }
            except Exception:
                pass

        doctrine = params.get("doctrine_override") if params else None
        agents = {}
        for cmd_id, commander in game_state.commanders.items():
            kwargs = {"graph_tools": graph_tools}
            if doctrine:
                kwargs["doctrine_override"] = doctrine
            if commander.rank == "Theater":
                agents[cmd_id] = TheaterCommander(commander, llm_config, **kwargs)
            elif commander.rank == "Division":
                agents[cmd_id] = DivisionCommander(commander, llm_config, **kwargs)
            else:
                agents[cmd_id] = BattalionCommander(commander, llm_config, **kwargs)
        return agents
