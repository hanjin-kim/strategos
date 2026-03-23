from __future__ import annotations
import json
import logging
from app.agents.base_commander import BaseCommander
from app.agents.rule_based_fallback import RuleBasedFallback
from app.models.actions import MilitaryAction

logger = logging.getLogger(__name__)


class BattalionCommander(BaseCommander):
    """Battalion-level commander. Converts OrderDirectives into tactical MilitaryActions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fallback_ai = RuleBasedFallback()

    def _build_persona(self) -> str:
        return (
            f"You are {self.commander.name}, Battalion Commander for {self.commander.side.value} forces.\n"
            f"COMMAND AUTHORITY: You command ONLY unit '{self.commander.unit_id}'. "
            "You MUST NOT issue orders for any other unit.\n"
            "SITUATIONAL AWARENESS: You can see friendly_units for coordination, "
            "but you cannot command them.\n"
            "Output: JSON array with exactly ONE action for YOUR unit:\n"
            '{"unit_id": "YOUR_UNIT_ID", "action_type": "MOVE|ATTACK|DEFEND|RETREAT|HOLD", '
            '"target_hex": {"q": N, "r": N} or null, "target_unit_id": "enemy_id" or null, '
            '"priority": 1-5, "reasoning": "..."}\n'
        )

    def decide(self, game_state) -> list[MilitaryAction]:
        """Generate tactical MilitaryActions."""
        unit = game_state.get_unit(self.commander.unit_id)
        if unit is None or unit.status.value == "DESTROYED":
            return []

        # If in fallback mode, use rule-based AI
        if self._fallback_mode:
            actions = self._fallback_ai.decide(
                self.commander.id, unit, game_state, self._current_orders
            )
            self._update_memory(game_state.turn, {}, actions)
            return actions

        visible = self._apply_fog_of_war(game_state)
        graph_ctx = self._query_graph()
        context = self._build_context(visible, graph_ctx, game_state)

        system_prompt = self._build_cached_system_prompt()
        user_message = json.dumps(context, ensure_ascii=False)

        response = self._call_llm(system_prompt, user_message)
        if response:
            actions = self._parse_actions(response, game_state.turn)
            if actions:
                self._update_memory(game_state.turn, context, actions)
                return actions

        # LLM failed, use fallback
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            self._fallback_mode = True
            logger.warning("Battalion %s entering permanent fallback mode", self.commander.id)

        actions = self._fallback_ai.decide(
            self.commander.id, unit, game_state, self._current_orders
        )
        self._update_memory(game_state.turn, {}, actions)
        return actions
