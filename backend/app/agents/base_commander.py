from __future__ import annotations
import json
import uuid
import logging
from openai import OpenAI
from app.models.domain import Commander, Unit, Side, UnitStatus, HexCoord
from app.models.actions import MilitaryAction, ActionType, OrderDirective
from app.memory.rolling_memory import RollingMemory
from app.graph.graph_tools import GraphTools
from app.utils.hex_grid import hex_neighbors

logger = logging.getLogger(__name__)


class BaseCommander:
    """Base class for all commander agents. OODA loop + graph queries + rolling memory."""

    MAX_CONSECUTIVE_FAILURES = 3

    def __init__(
        self,
        commander: Commander,
        llm_config: dict,  # {"api_key", "base_url", "model", "temperature"}
        graph_tools: GraphTools | None = None,
        memory_window: int = 10,
    ):
        self.commander = commander
        self.memory = RollingMemory(window=memory_window)
        self.graph_tools = graph_tools
        self._current_orders: OrderDirective | None = None
        self._consecutive_failures = 0
        self._fallback_mode = False
        self._client = None
        self._model = llm_config.get("model", "qwen-plus")
        self._temperature = llm_config.get("temperature", 0.0)

        # Initialize OpenAI client
        api_key = llm_config.get("api_key", "")
        base_url = llm_config.get("base_url", "")
        if api_key:
            self._client = OpenAI(api_key=api_key, base_url=base_url)

    def decide(self, game_state) -> list:
        """Main decision method. Override in subclasses for specific behavior."""
        raise NotImplementedError

    def receive_orders(self, orders: OrderDirective) -> None:
        """Receive orders from superior commander."""
        self._current_orders = orders

    def _get_superior_orders(self) -> OrderDirective | None:
        return self._current_orders

    def _apply_fog_of_war(self, game_state) -> dict:
        """Phase 1 simplified fog: own units + enemies within 2 hexes of any own unit."""
        my_side = self.commander.side
        own_units = game_state.get_units_by_side(my_side)

        # Collect hexes visible to our units (within 2 hex radius)
        visible_hexes = set()
        for unit in own_units:
            visible_hexes.add(unit.position)
            for n1 in hex_neighbors(unit.position):
                visible_hexes.add(n1)
                for n2 in hex_neighbors(n1):
                    visible_hexes.add(n2)

        known_enemy = []
        for unit in game_state.units.values():
            if unit.side != my_side and unit.position in visible_hexes and unit.status != UnitStatus.DESTROYED:
                known_enemy.append(unit)

        return {
            "own_units": own_units,
            "known_enemy": known_enemy,
            "visible_hexes": visible_hexes,
        }

    def _build_context(self, visible_state: dict, graph_context: dict, game_state) -> dict:
        """Build JSON context for LLM prompt."""
        own_units_data = []
        for u in visible_state["own_units"]:
            if u.status != UnitStatus.DESTROYED:
                own_units_data.append({
                    "id": u.id, "name": u.name, "type": u.unit_type.value,
                    "position": {"q": u.position.q, "r": u.position.r},
                    "strength": u.strength, "morale": u.morale,
                    "movement_points": u.movement_points, "ammo": u.ammo,
                    "status": u.status.value,
                })

        enemy_data = []
        for u in visible_state["known_enemy"]:
            enemy_data.append({
                "id": u.id, "name": u.name, "type": u.unit_type.value,
                "position": {"q": u.position.q, "r": u.position.r},
                "strength": u.strength,
            })

        orders_ctx = None
        if self._current_orders:
            orders_ctx = self._current_orders.to_battalion_context()

        return {
            "turn": game_state.turn,
            "commander": {"id": self.commander.id, "name": self.commander.name, "rank": self.commander.rank},
            "orders_from_superior": orders_ctx,
            "own_units": own_units_data,
            "known_enemy": enemy_data,
            "relationships": graph_context,
            "recent_memory": self.memory.to_context_string(),
        }

    def _query_graph(self) -> dict:
        """Query relationship graph for situation awareness."""
        if not self.graph_tools:
            return {}
        unit_id = self.commander.unit_id
        return {
            "supply_chain": self.graph_tools.query_supply_chain(unit_id),
            "command_chain": self.graph_tools.query_command_chain(unit_id),
            "nearby": self.graph_tools.query_nearby_units(unit_id),
        }

    def _call_llm(self, system_prompt: str, user_message: str) -> str | None:
        """Call LLM and return raw response text. Returns None on failure."""
        if self._client is None:
            return None
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=self._temperature,
                max_tokens=2048,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning("LLM call failed for %s: %s", self.commander.id, e)
            return None

    def _parse_actions(self, llm_response: str, turn: int) -> list[MilitaryAction]:
        """Parse LLM JSON response into MilitaryAction list. Returns empty on failure."""
        try:
            # Try to extract JSON from response
            text = llm_response.strip()
            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)
            if not isinstance(data, list):
                data = [data]

            actions = []
            for item in data:
                action = MilitaryAction(
                    action_id=str(uuid.uuid4()),
                    turn=turn,
                    commander_id=self.commander.id,
                    unit_id=item["unit_id"],
                    action_type=ActionType(item["action_type"]),
                    target_hex=HexCoord(q=item["target_hex"]["q"], r=item["target_hex"]["r"]) if item.get("target_hex") else None,
                    target_unit_id=item.get("target_unit_id"),
                    priority=item.get("priority", 3),
                    reasoning=item.get("reasoning", ""),
                )
                actions.append(action)
            self._consecutive_failures = 0
            return actions
        except Exception as e:
            logger.warning("Failed to parse LLM response for %s: %s", self.commander.id, e)
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                self._fallback_mode = True
                logger.warning("Commander %s entering fallback mode after %d failures", self.commander.id, self._consecutive_failures)
            return []

    def _build_persona(self) -> str:
        """Build system prompt. Override in subclasses."""
        return f"You are {self.commander.name}, a {self.commander.rank} commander for {self.commander.side.value} force."

    def _update_memory(self, turn: int, context: dict, actions: list) -> None:
        """Save turn record to rolling memory."""
        summary = f"Turn {turn}: {len(actions)} actions issued"
        action_dicts = []
        for a in actions:
            if isinstance(a, MilitaryAction):
                action_dicts.append({"action_type": a.action_type.value, "unit_id": a.unit_id})
            elif isinstance(a, OrderDirective):
                action_dicts.append({"mission": a.mission.value, "target": a.target_unit_id})
            else:
                action_dicts.append({"type": str(type(a))})
        self.memory.add(turn, summary, action_dicts)
