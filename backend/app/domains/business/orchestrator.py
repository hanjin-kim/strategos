from __future__ import annotations
from typing import Any
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class BusinessCommandOrchestrator:
    """Business command phase: CEO sets strategy, BU heads execute. No military imports."""

    def __init__(self, constraint_validator=None):
        self._constraints = constraint_validator

    def run_command_phase(self, state: Any, agents: dict) -> list:
        from app.domains.business.agents import BusinessCEO, BusinessAgent

        all_actions: list = []

        # Step 1: CEO agents set strategy
        ceo_agents = [a for a in agents.values() if isinstance(a, BusinessCEO)]
        ceo_directives: list = []
        for ceo in ceo_agents:
            try:
                directives = ceo.decide(state)
                ceo_directives.extend(directives)
            except Exception as e:
                logger.warning("CEO failed: %s", e)

        # Step 2: Distribute CEO directives to BU heads
        bu_agents = [
            a for a in agents.values()
            if isinstance(a, BusinessAgent) and not isinstance(a, BusinessCEO)
        ]
        for directive in ceo_directives:
            if isinstance(directive, dict):
                target_uid = directive.get("target_unit_id", "")
                for agent in bu_agents:
                    if agent.unit_id == target_uid:
                        agent.receive_orders(directive)
                        break

        # Step 3: All BU heads decide in parallel
        if len(bu_agents) > 1:
            with ThreadPoolExecutor(max_workers=min(len(bu_agents), 8)) as ex:
                futures = {ex.submit(a.decide, state): a for a in bu_agents}
                for f in as_completed(futures):
                    try:
                        all_actions.extend(f.result(timeout=60))
                    except Exception as e:
                        logger.warning("BU agent failed: %s", e)
        elif bu_agents:
            all_actions.extend(bu_agents[0].decide(state))

        # Step 4: Validate
        if self._constraints:
            result = self._constraints.validate(all_actions, state)
            if hasattr(result, "valid_actions"):
                return list(result.valid_actions)

        return all_actions
