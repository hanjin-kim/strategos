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
            "Your role: Execute tactical actions based on orders from your superior.\n"
            "Output: JSON array of actions for your unit(s). Each action:\n"
            '{"unit_id": "your_unit_id", "action_type": "MOVE|ATTACK|DEFEND|RETREAT|HOLD", '
            '"target_hex": {"q": N, "r": N} or null, "target_unit_id": "enemy_id" or null, '
            '"priority": 1-5, "reasoning": "..."}\n'
            "You may only command units under your direct control."
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

        system_prompt = self._build_persona()
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
