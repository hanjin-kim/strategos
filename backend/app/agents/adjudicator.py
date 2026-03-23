from __future__ import annotations
import json
import logging
from openai import OpenAI
from app.models.narrative import TurnNarrative
from app.models.simulation import TurnResult
from app.models.domain import Side, UnitStatus

logger = logging.getLogger(__name__)


class Adjudicator:
    """Turn narrative generator. NOT a BaseCommander subclass."""

    def __init__(self, llm_config: dict):
        self._client = None
        self._model = llm_config.get("model", "qwen-plus")
        api_key = llm_config.get("api_key", "")
        base_url = llm_config.get("base_url", "")
        if api_key:
            self._client = OpenAI(api_key=api_key, base_url=base_url)

    def generate_narrative(self, turn_result: TurnResult, game_state) -> TurnNarrative:
        """Generate narrative for a completed turn."""
        if self._client is None:
            return self._fallback_narrative(turn_result, game_state)

        prompt = self._build_narrative_prompt(turn_result, game_state)
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=1024,
            )
            text = response.choices[0].message.content
            return self._parse_narrative(text, turn_result.turn)
        except Exception as e:
            logger.warning("Adjudicator LLM call failed: %s", e)
            return self._fallback_narrative(turn_result, game_state)

    def _system_prompt(self) -> str:
        return (
            "You are a military correspondent reporting on a wargame simulation. "
            "Write concise, dramatic battle reports. "
            "Output JSON: {\"summary\": \"...\", \"combat_reports\": [\"...\"], "
            "\"movement_summary\": \"...\", \"strategic_analysis\": \"...\", "
            "\"key_events\": [\"...\"]}"
        )

    def _build_narrative_prompt(self, turn_result: TurnResult, game_state) -> str:
        """Build context for narrative generation."""
        blue_units = [u for u in game_state.units.values() if u.side == Side.BLUE and u.status != UnitStatus.DESTROYED]
        red_units = [u for u in game_state.units.values() if u.side == Side.RED and u.status != UnitStatus.DESTROYED]

        context = {
            "turn": turn_result.turn,
            "movements": len(turn_result.movements),
            "combats": len(turn_result.combats),
            "destroyed_units": turn_result.destroyed_units,
            "blue_active": len(blue_units),
            "red_active": len(red_units),
            "blue_avg_strength": round(sum(u.strength for u in blue_units) / max(len(blue_units), 1), 2),
            "red_avg_strength": round(sum(u.strength for u in red_units) / max(len(red_units), 1), 2),
            "combat_details": [
                {"attacker": c.attacker_id, "defender": c.defender_id,
                 "result": c.result.value, "attacker_losses": c.attacker_losses,
                 "defender_losses": c.defender_losses}
                for c in turn_result.combats
            ],
        }
        return json.dumps(context, default=str)

    def _parse_narrative(self, text: str, turn: int) -> TurnNarrative:
        """Parse LLM response into TurnNarrative."""
        try:
            clean = text.strip()
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0]
            elif "```" in clean:
                clean = clean.split("```")[1].split("```")[0]
            data = json.loads(clean)
            return TurnNarrative(
                turn=turn,
                summary=data.get("summary", ""),
                combat_reports=data.get("combat_reports", []),
                movement_summary=data.get("movement_summary", ""),
                strategic_analysis=data.get("strategic_analysis", ""),
                key_events=data.get("key_events", []),
            )
        except Exception:
            return TurnNarrative(turn=turn, summary=text[:500])

    def _fallback_narrative(self, turn_result: TurnResult, game_state) -> TurnNarrative:
        """Rule-based narrative when LLM is unavailable."""
        combats = turn_result.combats
        movements = turn_result.movements
        destroyed = turn_result.destroyed_units

        summary_parts = [f"Turn {turn_result.turn}:"]
        if movements:
            summary_parts.append(f"{len(movements)} units moved.")
        if combats:
            summary_parts.append(f"{len(combats)} engagements occurred.")
        if destroyed:
            summary_parts.append(f"{len(destroyed)} units destroyed.")
        if not movements and not combats:
            summary_parts.append("A quiet turn with no significant action.")

        combat_reports = []
        for c in combats:
            combat_reports.append(
                f"{c.attacker_id} attacked {c.defender_id}: "
                f"Result {c.result.value}, "
                f"attacker losses {c.attacker_losses:.0%}, "
                f"defender losses {c.defender_losses:.0%}"
            )

        key_events = [f"Unit {uid} destroyed" for uid in destroyed]

        blue_active = len([u for u in game_state.units.values() if u.side == Side.BLUE and u.status != UnitStatus.DESTROYED])
        red_active = len([u for u in game_state.units.values() if u.side == Side.RED and u.status != UnitStatus.DESTROYED])
        analysis = f"BLUE: {blue_active} active units. RED: {red_active} active units."
        if blue_active > red_active:
            analysis += " BLUE holds numerical advantage."
        elif red_active > blue_active:
            analysis += " RED holds numerical advantage."
        else:
            analysis += " Forces are evenly matched."

        return TurnNarrative(
            turn=turn_result.turn,
            summary=" ".join(summary_parts),
            combat_reports=combat_reports,
            movement_summary=f"{len(movements)} movement(s) executed." if movements else "No movement.",
            strategic_analysis=analysis,
            key_events=key_events,
        )
