from __future__ import annotations
import os
from app.domains.business.state import BusinessState
from app.domains.business.agents import BusinessAgent, BusinessCEO
from app.domains.business.engines import (
    MarketSpace, MarketCompetitionResolver, BusinessMover,
    BusinessConstraints, BusinessVictory,
)
from app.domains.business.orchestrator import BusinessCommandOrchestrator
from app.prompts.business_doctrine import BUSINESS_DOCTRINE


class BusinessDomainFactory:
    """Factory for business domain. ZERO military imports."""

    def create_state(self, scenario: dict) -> BusinessState:
        return BusinessState(scenario)

    def create_engines(self, scenario: dict, params: dict | None = None) -> dict:
        rng_seed = params.get("rng_seed", 42) if params else 42

        # Build market connections and data from scenario
        connections: dict[str, list[str]] = {}
        market_data: dict[str, dict] = {}
        for market in scenario.get("markets", []):
            key = f"{market['region']}:{market['segment']}"
            connections[key] = market.get("connections", [])
            market_data[key] = market

        constraints = BusinessConstraints()

        return {
            "space": MarketSpace(connections, market_data),
            "interaction_resolver": MarketCompetitionResolver(rng_seed=rng_seed),
            "mover": BusinessMover(),
            "constraints": constraints,
            "victory_checker": BusinessVictory(),
            "command_orchestrator": BusinessCommandOrchestrator(constraint_validator=constraints),
        }

    def create_agents(self, scenario: dict, params: dict | None = None) -> dict:
        state = self.create_state(scenario)

        use_llm = params.get("use_llm", False) if params else False
        llm_config: dict = {"api_key": "", "base_url": "", "model": ""}
        if use_llm:
            try:
                llm_config = {
                    "api_key": os.environ.get("LLM_API_KEY", ""),
                    "base_url": os.environ.get("LLM_BASE_URL", ""),
                    "model": os.environ.get("LLM_MODEL_NAME", "qwen-plus"),
                }
            except Exception:
                pass

        doctrine = (
            params.get("doctrine_override", BUSINESS_DOCTRINE)
            if params else BUSINESS_DOCTRINE
        )

        agents: dict = {}
        for cmd_id, cmd_data in state.commanders.items():
            if cmd_data["rank"] in ("Theater", "CEO"):
                agents[cmd_id] = BusinessCEO(cmd_data, llm_config, doctrine=doctrine)
            else:
                agents[cmd_id] = BusinessAgent(cmd_data, llm_config, doctrine=doctrine)
        return agents
