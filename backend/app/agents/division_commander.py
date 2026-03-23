from __future__ import annotations
import json
import uuid
import logging
from app.agents.base_commander import BaseCommander
from app.models.actions import OrderDirective, MissionType
from app.models.domain import HexCoord

logger = logging.getLogger(__name__)


class DivisionCommander(BaseCommander):
    """Division-level commander. Receives OrderDirective from Theater,
    translates into more specific OrderDirectives for subordinate Battalions."""

    def decide(self, game_state) -> list[OrderDirective]:
        """Generate orders for subordinate battalions."""
        if self._fallback_mode:
            return self._fallback_orders(game_state)

        visible_state = self._apply_fog_of_war(game_state)
        graph_context = self._query_graph()
        context = self._build_context(visible_state, graph_context, game_state)

        system_prompt = self._build_cached_system_prompt()
        user_message = json.dumps(context, default=str)

        response = self._call_llm(system_prompt, user_message)
        if response is None:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                self._fallback_mode = True
            return self._fallback_orders(game_state)

        orders = self._parse_order_directives(response, game_state.turn)
        self._update_memory(game_state.turn, context, orders)
        return orders

    def _build_persona(self) -> str:
        controlled = ""
        if self.graph_tools:
            scope = self.graph_tools.query_command_scope(self.commander.id)
            controlled = ", ".join(scope.get("commanded_unit_ids", []))
        return (
            f"You are {self.commander.name}, Division Commander for {self.commander.side.value} forces.\n"
            f"You receive mission orders from Theater Command and translate them into specific orders for your battalions.\n"
            f"COMMAND AUTHORITY: You issue orders ONLY to units: [{controlled}]\n"
            f"SITUATIONAL AWARENESS: 'friendly_units' shows other units you can see but NOT command.\n"
            f"Consider terrain, supply status, intel, and enemy positions when distributing missions.\n"
            f"Output: JSON array of orders for your battalions:\n"
            f'[{{"target_unit_id": "...", "mission": "ATTACK|DEFEND|DELAY|RESERVE|WITHDRAW", '
            f'"objective_hex": {{"q": N, "r": N}} or null, "priority": 1-5, '
            f'"constraints": ["..."], "reasoning": "..."}}]'
        )

    def _parse_order_directives(self, llm_response: str, turn: int) -> list[OrderDirective]:
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

            # Get allowed scope
            allowed_ids: set[str] = set()
            if self.graph_tools:
                scope = self.graph_tools.query_command_scope(self.commander.id)
                allowed_ids = set(scope.get("commanded_unit_ids", []))

            orders = []
            for item in data:
                target_uid = item.get("target_unit_id", "")
                if allowed_ids and target_uid not in allowed_ids:
                    continue  # Skip out-of-scope orders

                obj_hex = None
                if item.get("objective_hex"):
                    obj_hex = HexCoord(q=item["objective_hex"]["q"], r=item["objective_hex"]["r"])

                order = OrderDirective(
                    order_id=str(uuid.uuid4()),
                    turn=turn,
                    issuer_id=self.commander.id,
                    target_unit_id=target_uid,
                    mission=MissionType(item.get("mission", "DEFEND")),
                    objective_hex=obj_hex,
                    priority=item.get("priority", 3),
                    constraints=item.get("constraints", []),
                    reasoning=item.get("reasoning", ""),
                )
                orders.append(order)

            self._consecutive_failures = 0
            return orders
        except Exception as e:
            logger.warning("Failed to parse Division orders for %s: %s", self.commander.id, e)
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                self._fallback_mode = True
            return self._fallback_orders(game_state=None)

    def _fallback_orders(self, game_state) -> list[OrderDirective]:
        """Fallback: issue DEFEND orders to all controlled units."""
        if not self.graph_tools:
            return []
        scope = self.graph_tools.query_command_scope(self.commander.id)
        orders = []
        for uid in scope.get("commanded_unit_ids", []):
            orders.append(OrderDirective(
                order_id=str(uuid.uuid4()),
                turn=game_state.turn if game_state else 0,
                issuer_id=self.commander.id,
                target_unit_id=uid,
                mission=MissionType.DEFEND,
                priority=3,
                reasoning="Fallback: defend in place",
            ))
        return orders
