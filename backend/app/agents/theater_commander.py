from __future__ import annotations
import json
import uuid
import logging
from app.agents.base_commander import BaseCommander
from app.models.actions import OrderDirective, MissionType
from app.models.domain import HexCoord, UnitStatus

logger = logging.getLogger(__name__)


class TheaterCommander(BaseCommander):
    """Theater-level commander. Issues OrderDirectives to subordinate battalions."""

    def _build_persona(self) -> str:
        return (
            f"You are {self.commander.name}, Theater Commander for {self.commander.side.value} forces.\n"
            "COMMAND AUTHORITY: You issue mission orders ONLY to units listed in 'controlled_units'.\n"
            "You MUST NOT issue orders to units not in your command authority.\n"
            "Output: JSON array of mission orders for your controlled units. Each order:\n"
            '{"target_unit_id": "unit_id_from_controlled_units", '
            '"mission": "ATTACK|DEFEND|DELAY|RESERVE|WITHDRAW", '
            '"objective_hex": {"q": N, "r": N} or null, "priority": 1-5, "reasoning": "..."}\n'
        )

    def decide(self, game_state) -> list[OrderDirective]:
        """Generate OrderDirectives for subordinate units."""
        # If in fallback mode, issue DEFEND to all subordinates
        if self._fallback_mode:
            return self._fallback_orders(game_state)

        visible = self._apply_fog_of_war(game_state)
        graph_ctx = self._query_graph()
        context = self._build_context(visible, graph_ctx, game_state)

        system_prompt = self._build_cached_system_prompt()
        user_message = json.dumps(context, ensure_ascii=False)

        response = self._call_llm(system_prompt, user_message)
        if response:
            orders = self._parse_orders(response, game_state.turn)
            if orders:
                self._update_memory(game_state.turn, context, orders)
                return orders

        # Parse failed, try fallback
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            self._fallback_mode = True
        return self._fallback_orders(game_state)

    def _parse_orders(self, llm_response: str, turn: int) -> list[OrderDirective]:
        """Parse LLM response into OrderDirective list."""
        try:
            text = llm_response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)
            if not isinstance(data, list):
                data = [data]

            orders = []
            for item in data:
                obj_hex = None
                if item.get("objective_hex"):
                    obj_hex = HexCoord(q=item["objective_hex"]["q"], r=item["objective_hex"]["r"])
                order = OrderDirective(
                    order_id=str(uuid.uuid4()),
                    turn=turn,
                    issuer_id=self.commander.id,
                    target_unit_id=item["target_unit_id"],
                    mission=MissionType(item["mission"]),
                    objective_hex=obj_hex,
                    priority=item.get("priority", 3),
                    constraints=item.get("constraints", []),
                    reasoning=item.get("reasoning", ""),
                )
                orders.append(order)
            self._consecutive_failures = 0
            return orders
        except Exception as e:
            logger.warning("Failed to parse theater orders: %s", e)
            return []

    def _fallback_orders(self, game_state) -> list[OrderDirective]:
        """Fallback: DEFEND all subordinate units."""
        orders = []
        my_units = game_state.get_units_by_side(self.commander.side)
        for unit in my_units:
            if unit.status != UnitStatus.DESTROYED:
                orders.append(OrderDirective(
                    order_id=str(uuid.uuid4()),
                    turn=game_state.turn,
                    issuer_id=self.commander.id,
                    target_unit_id=unit.id,
                    mission=MissionType.DEFEND,
                    objective_hex=unit.position,
                    priority=3,
                    reasoning="Fallback: defend current position",
                ))
        return orders
