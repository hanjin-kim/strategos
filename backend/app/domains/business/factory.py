from __future__ import annotations
from typing import Any
from app.domains.business.engines import (
    MarketSpace, MarketCompetitionResolver, BusinessMover,
    BusinessConstraints, BusinessVictory,
)
from app.engine.game_state import GameState
from app.agents.theater_commander import TheaterCommander
from app.agents.division_commander import DivisionCommander
from app.agents.battalion_commander import BattalionCommander
from app.graph.relationship_graph import RelationshipGraph
from app.graph.graph_tools import GraphTools
from app.domains.business.orchestrator import BusinessCommandOrchestrator


class BusinessDomainFactory:
    """Factory for business competition domain."""

    def create_state(self, scenario: dict) -> Any:
        """Create game state from business scenario.
        Reuses GameState — business units map to military Unit fields."""
        return GameState(scenario)

    def create_engines(self, scenario: dict, params: dict | None = None) -> dict:
        rng_seed = params.get("rng_seed", 42) if params else 42

        state = self.create_state(scenario)

        # Build market connections from scenario
        connections = scenario.get("market_connections", {})
        terrains: dict = {}

        relationship_graph = RelationshipGraph()
        relationship_graph.load_from_scenario(scenario, state)

        from app.engine.constraint_engine import ConstraintEngine
        from app.engine.movement_engine import MovementEngine
        from app.engine.combat_resolver import CombatResolver
        from app.engine.intel_engine import IntelEngine
        from app.engine.supply_engine import SupplyEngine
        from app.engine.air_engine import AirEngine

        constraint_engine = ConstraintEngine()
        business_constraints = BusinessConstraints()

        return {
            "game_state": state,
            "space": MarketSpace(connections, terrains),
            "interaction_resolver": MarketCompetitionResolver(rng_seed=rng_seed),
            "mover": BusinessMover(),
            "constraints": business_constraints,
            "victory_checker": BusinessVictory(),
            "command_orchestrator": BusinessCommandOrchestrator(constraint_validator=business_constraints),
            # Raw engines kept for backward compat with tests that check these keys
            "combat_resolver": CombatResolver(rng_seed=rng_seed),
            "movement_engine": MovementEngine(),
            "constraint_engine": constraint_engine,
            "intel_engine": IntelEngine(),
            "supply_engine": SupplyEngine(),
            "air_engine": AirEngine(rng_seed=rng_seed + 1000),
            "relationship_graph": relationship_graph,
        }

    def create_agents(self, scenario: dict, params: dict | None = None) -> dict:
        """Create agents with business doctrine."""
        state = self.create_state(scenario)

        relationship_graph = RelationshipGraph()
        relationship_graph.load_from_scenario(scenario, state)
        graph_tools = GraphTools(relationship_graph)

        use_llm = params.get("use_llm", False) if params else False
        llm_config: dict = {"api_key": "", "base_url": "", "model": ""}
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

        from app.prompts.business_doctrine import BUSINESS_DOCTRINE
        doctrine = params.get("doctrine_override", BUSINESS_DOCTRINE) if params else BUSINESS_DOCTRINE

        agents = {}
        for cmd_id, commander in state.commanders.items():
            kwargs: dict = {"graph_tools": graph_tools, "doctrine_override": doctrine}
            if commander.rank == "Theater":
                agents[cmd_id] = TheaterCommander(commander, llm_config, **kwargs)
            elif commander.rank == "Division":
                agents[cmd_id] = DivisionCommander(commander, llm_config, **kwargs)
            else:
                agents[cmd_id] = BattalionCommander(commander, llm_config, **kwargs)
        return agents
