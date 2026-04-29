from __future__ import annotations
import json
import logging
from openai import OpenAI
from app.narrative.commander_personality import CommanderPersonality, get_commander_personality
from app.models.simulation import TurnResult
from app.models.domain import Side, UnitStatus

logger = logging.getLogger(__name__)


class DialogueGenerator:
    """Generates in-character commander dialogue and staff briefings using LLM."""

    def __init__(self, llm_config: dict):
        self._client = None
        self._model = llm_config.get("model", "qwen-plus")
        api_key = llm_config.get("api_key", "")
        base_url = llm_config.get("base_url", "")
        if api_key:
            self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._personalities: dict[str, CommanderPersonality] = {}

    def set_personalities(self, player_side: str, scenario: str = "korean_peninsula") -> None:
        for side in ["BLUE", "RED"]:
            self._personalities[side] = get_commander_personality(side, scenario)
        self._player_side = player_side

    def generate_dialogue(
        self, turn_result: TurnResult, game_state, player_side: str
    ) -> dict:
        """Generate enemy dialogue + staff briefing for a turn.

        Returns: {
            "enemy_dialogue": [{"speaker": str, "text": str, "tone": str}],
            "staff_briefing": str,
            "event_reactions": [str],
        }
        """
        if self._client is None:
            return self._fallback_dialogue(turn_result, game_state, player_side)

        enemy_side = "RED" if player_side == "BLUE" else "BLUE"
        enemy_persona = self._personalities.get(enemy_side)
        friendly_persona = self._personalities.get(player_side)

        context = self._build_dialogue_context(turn_result, game_state, player_side)

        prompt = (
            f"## SITUATION\n{json.dumps(context, default=str)}\n\n"
            f"## ENEMY COMMANDER\n"
            f"Name: {enemy_persona.name if enemy_persona else 'Enemy Commander'}\n"
            f"Traits: {', '.join(enemy_persona.traits) if enemy_persona else 'unknown'}\n"
            f"Style: {enemy_persona.speech_style if enemy_persona else 'formal'}\n\n"
            f"## FRIENDLY STAFF\n"
            f"Commander: {friendly_persona.name if friendly_persona else 'Our Commander'}\n\n"
            "## OUTPUT (JSON)\n"
            "Generate:\n"
            '1. "enemy_dialogue": 1-2 intercepted enemy comms (in-character reactions to this turn)\n'
            '2. "staff_briefing": 2-3 sentence friendly staff briefing (addressed as "Sir")\n'
            '3. "event_reactions": short reactions to major events (if any)\n'
            "Keep each piece under 100 words. Be dramatic but concise.\n"
            '{"enemy_dialogue": [{"speaker": "name", "text": "...", "tone": "defiant|frustrated|confident|desperate"}], '
            '"staff_briefing": "...", "event_reactions": ["..."]}'
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=512,
            )
            text = response.choices[0].message.content
            return self._parse_dialogue(text, turn_result, game_state, player_side)
        except Exception as e:
            logger.warning("Dialogue generation failed: %s", e)
            return self._fallback_dialogue(turn_result, game_state, player_side)

    def _system_prompt(self) -> str:
        return (
            "You are a creative writer for a military wargame. "
            "Generate in-character dialogue for commanders reacting to battlefield events. "
            "Enemy comms are 'intercepted transmissions' — tense, emotional, revealing character. "
            "Staff briefings are professional military reports addressed to the player as 'Sir'. "
            "Output valid JSON only."
        )

    def _build_dialogue_context(self, turn_result, game_state, player_side) -> dict:
        enemy_side = "RED" if player_side == "BLUE" else "BLUE"
        blue_units = [u for u in game_state.units.values() if u.side == Side.BLUE and u.status != UnitStatus.DESTROYED]
        red_units = [u for u in game_state.units.values() if u.side == Side.RED and u.status != UnitStatus.DESTROYED]

        player_units = blue_units if player_side == "BLUE" else red_units
        enemy_units = red_units if player_side == "BLUE" else blue_units

        return {
            "turn": turn_result.turn,
            "combats": len(turn_result.combats),
            "destroyed": turn_result.destroyed_units,
            "player_units_active": len(player_units),
            "enemy_units_active": len(enemy_units),
            "player_avg_strength": round(sum(u.strength for u in player_units) / max(len(player_units), 1), 2),
            "enemy_avg_strength": round(sum(u.strength for u in enemy_units) / max(len(enemy_units), 1), 2),
            "combat_details": [
                {
                    "attacker": c.attacker_id,
                    "defender": c.defender_id,
                    "result": c.result.value,
                    "attacker_losses": round(c.attacker_losses, 2),
                    "defender_losses": round(c.defender_losses, 2),
                }
                for c in turn_result.combats
            ],
        }

    def _parse_dialogue(self, text, turn_result, game_state, player_side) -> dict:
        try:
            clean = text.strip()
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0]
            elif "```" in clean:
                clean = clean.split("```")[1].split("```")[0]
            data = json.loads(clean)
            return {
                "enemy_dialogue": data.get("enemy_dialogue", []),
                "staff_briefing": data.get("staff_briefing", ""),
                "event_reactions": data.get("event_reactions", []),
            }
        except Exception:
            return self._fallback_dialogue(turn_result, game_state, player_side)

    def _fallback_dialogue(self, turn_result, game_state, player_side) -> dict:
        enemy_side = "RED" if player_side == "BLUE" else "BLUE"
        enemy_persona = self._personalities.get(enemy_side)
        speaker = enemy_persona.name if enemy_persona else f"{enemy_side} Commander"

        dialogue = []
        briefing_parts = [f"Sir, Turn {turn_result.turn} report:"]

        if turn_result.combats:
            dialogue.append({
                "speaker": speaker,
                "text": f"They engaged {len(turn_result.combats)} of our positions. We will not yield.",
                "tone": "defiant",
            })
            briefing_parts.append(f"{len(turn_result.combats)} engagements this turn.")

        if turn_result.destroyed_units:
            briefing_parts.append(f"{len(turn_result.destroyed_units)} unit(s) destroyed.")

        if not turn_result.combats and not turn_result.destroyed_units:
            dialogue.append({
                "speaker": speaker,
                "text": "All quiet. They are biding their time. Stay sharp.",
                "tone": "cautious",
            })
            briefing_parts.append("No significant contact.")

        enemy_units = [
            u for u in game_state.units.values()
            if u.side == Side(enemy_side) and u.status != UnitStatus.DESTROYED
        ]
        player_units = [
            u for u in game_state.units.values()
            if u.side == Side(player_side) and u.status != UnitStatus.DESTROYED
        ]
        briefing_parts.append(
            f"We have {len(player_units)} active units; enemy has {len(enemy_units)}."
        )

        return {
            "enemy_dialogue": dialogue,
            "staff_briefing": " ".join(briefing_parts),
            "event_reactions": [f"Unit {uid} lost" for uid in turn_result.destroyed_units],
        }
