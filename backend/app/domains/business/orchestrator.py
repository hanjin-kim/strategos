from __future__ import annotations
from typing import Any
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class BusinessCommandOrchestrator:
    """Flat business command phase: CEO directs, all BU heads execute independently.

    Unlike military 3-tier (Theater->Division->Battalion), business uses:
    1. CEO sets strategic directives (Theater agent)
    2. All BU heads receive directives and decide independently (parallel)
    3. No Division layer needed (optional VP passthrough)
    """

    def __init__(self, constraint_validator=None):
        self._constraints = constraint_validator

    def run_command_phase(self, state: Any, agents: dict) -> list:
        from app.agents.theater_commander import TheaterCommander
        from app.agents.division_commander import DivisionCommander
        from app.agents.battalion_commander import BattalionCommander

        all_actions = []

        # Step 1: CEO/Theater agents set strategy (parallel across companies)
        theater_agents = [a for a in agents.values() if isinstance(a, TheaterCommander)]
        theater_orders = []
        for agent in theater_agents:
            try:
                orders = agent.decide(state)
                theater_orders.extend(orders)
            except Exception as e:
                logger.warning("Theater agent failed: %s", e)

        # Step 2: Distribute orders to BU heads
        # VP passthrough (if Division exists)
        division_agents = [a for a in agents.values() if isinstance(a, DivisionCommander)]
        if division_agents:
            for order in theater_orders:
                for div in division_agents:
                    theater_side = next(
                        (a.commander.side for a in theater_agents if a.commander.id == order.issuer_id),
                        None,
                    )
                    if div.commander.side == theater_side:
                        div.receive_orders(order)
            div_orders = []
            for div in division_agents:
                try:
                    div_orders.extend(div.decide(state))
                except Exception as e:
                    logger.warning("Division agent failed: %s", e)
            for order in div_orders:
                for cid, agent in agents.items():
                    if isinstance(agent, BattalionCommander) and agent.commander.unit_id == order.target_unit_id:
                        agent.receive_orders(order)
        else:
            for order in theater_orders:
                for cid, agent in agents.items():
                    if isinstance(agent, BattalionCommander) and agent.commander.unit_id == order.target_unit_id:
                        agent.receive_orders(order)

        # Step 3: All BU heads decide in parallel
        bn_agents = [a for a in agents.values() if isinstance(a, BattalionCommander)]
        if len(bn_agents) > 1:
            with ThreadPoolExecutor(max_workers=min(len(bn_agents), 8)) as ex:
                futures = {ex.submit(a.decide, state): a for a in bn_agents}
                for f in as_completed(futures):
                    try:
                        all_actions.extend(f.result(timeout=60))
                    except Exception as e:
                        logger.warning("BU head failed: %s", e)
        elif bn_agents:
            all_actions.extend(bn_agents[0].decide(state))

        # Step 4: Validate
        if self._constraints:
            result = self._constraints.validate(all_actions, state)
            return list(result.valid_actions)

        return all_actions
