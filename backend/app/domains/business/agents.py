from __future__ import annotations
import json
import uuid
import random
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


class BusinessAgent:
    """Business unit head agent. Uses market graph, not hex grid.

    Replaces BattalionCommander for business domain.
    No military imports.
    """

    MAX_FAILURES = 3

    def __init__(self, commander: dict, llm_config: dict,
                 state=None, doctrine: str = ""):
        self.commander = commander  # dict, not Commander model
        self.commander_id = commander["id"]
        self.side = commander["side"]
        self.unit_id = commander.get("unit_id", "")
        self.rank = commander.get("rank", "Manager")
        self.personality = commander.get("personality_traits", {})
        self._doctrine = doctrine
        self._client = None
        self._model = llm_config.get("model", "qwen-plus")
        self._failures = 0
        self._fallback_mode = False
        self._rng = random.Random(hash(self.commander_id))
        self._cached_system_prompt: str | None = None  # L1+L2 cache
        self._current_order = None

        api_key = llm_config.get("api_key", "")
        if api_key:
            self._client = OpenAI(
                api_key=api_key,
                base_url=llm_config.get("base_url", ""),
            )

    def decide(self, state) -> list:
        """Make business decisions. Returns list of BusinessAction instances."""
        unit = state.get_unit(self.unit_id)
        if not unit or unit.status == "BANKRUPT":
            return []

        if self._fallback_mode or self._client is None:
            return self._fallback_decide(state, unit)

        # LLM path
        try:
            context = self._build_context(state, unit)
            system_prompt = self._get_cached_system_prompt(state)
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(context, default=str)},
                ],
                temperature=0.3,
                max_tokens=1024,
            )
            return self._parse_response(response.choices[0].message.content, state)
        except Exception as e:
            logger.warning("BusinessAgent %s LLM failed: %s", self.commander_id, e)
            self._failures += 1
            if self._failures >= self.MAX_FAILURES:
                self._fallback_mode = True
            return self._fallback_decide(state, unit)

    def receive_orders(self, order) -> None:
        """Receive strategic directive from CEO/VP."""
        self._current_order = order

    def _get_cached_system_prompt(self, state=None) -> str:
        """L1 doctrine + L2 persona + market structure. Cached after first call."""
        if self._cached_system_prompt is not None:
            return self._cached_system_prompt

        l1 = self._doctrine or ""
        l2 = self._build_persona()

        # L2 market structure (doesn't change within a simulation)
        if state and hasattr(state, "market_map") and state.market_map:
            segments = list(state.market_map.keys())
            l2 += f"\n\n## MARKET STRUCTURE\nSegments: {', '.join(segments)}\n"
            own_units = state.get_units_by_side(self.side) if hasattr(state, "get_units_by_side") else []
            if own_units:
                unit_list = ", ".join(
                    f"{u.id}({u.position.region}:{u.position.segment})"
                    for u in own_units if hasattr(u.position, "region")
                )
                l2 += f"Your units: {unit_list}\n"

        self._cached_system_prompt = l1 + "\n" + l2
        return self._cached_system_prompt

    def _build_persona(self) -> str:
        return (
            f"You are {self.commander['name']}, {self.rank} at {self.side}.\n"
            f"You manage business unit '{self.unit_id}'.\n"
            f"Decide: COMPETE (attack competitor), DEFEND (protect market share), "
            f"EXPAND (enter new market), INVEST_RD (boost R&D), or HOLD.\n"
            f'Output JSON: {{"action_type": "...", "target_competitor_id": "...", "reasoning": "..."}}'
        )

    def _build_context(self, state, unit) -> dict:
        """L3 dynamic context only — changes every turn."""
        competitors = (
            state.get_adjacent_competitors(self.unit_id)
            if hasattr(state, "get_adjacent_competitors")
            else []
        )
        return {
            "turn": state.turn,
            "my_unit": {
                "id": unit.id, "name": unit.name,
                "market_share": getattr(unit, "market_share", 0),
                "competitive_power": getattr(unit, "competitive_power", 0),
                "brand_loyalty": getattr(unit, "brand_loyalty", 0),
                "marketing_budget": getattr(unit, "marketing_budget", 0),
                "cash_reserves": getattr(unit, "cash_reserves", 0),
                "rd_capability": getattr(unit, "rd_capability", 0),
                "position": (
                    f"{unit.position.region}:{unit.position.segment}"
                    if hasattr(unit.position, "region") else str(unit.position)
                ),
            },
            "competitors": [{
                "id": c.id, "name": c.name,
                "market_share": getattr(c, "market_share", 0),
                "competitive_power": getattr(c, "competitive_power", 0),
                "position": (
                    f"{c.position.region}:{c.position.segment}"
                    if hasattr(c.position, "region") else str(c.position)
                ),
            } for c in competitors],
            "orders_from_ceo": self._current_order if self._current_order else None,
        }

    def _fallback_decide(self, state, unit) -> list:
        """Rule-based business decisions using market graph."""
        from app.domains.business.models import BusinessAction

        # Find competitors in same/adjacent markets
        competitors: list = []
        if hasattr(state, "get_adjacent_competitors"):
            competitors = state.get_adjacent_competitors(self.unit_id)
        elif hasattr(state, "get_competitors"):
            competitors = state.get_competitors(self.unit_id)

        aggression = self.personality.get("aggression", 0.5)

        if not competitors:
            # No competition visible — HOLD or INVEST_RD
            if unit.rd_capability < 0.7 and self._rng.random() < 0.4:
                return [BusinessAction(
                    action_id=str(uuid.uuid4()), turn=state.turn,
                    commander_id=self.commander_id, entity_id=self.unit_id,
                    action_type="INVEST_RD", reasoning="No competitors, investing in R&D",
                )]
            return [BusinessAction(
                action_id=str(uuid.uuid4()), turn=state.turn,
                commander_id=self.commander_id, entity_id=self.unit_id,
                action_type="HOLD", reasoning="Maintaining market position",
            )]

        # Has competitors — pick highest market share target
        target = max(competitors, key=lambda c: c.market_share)

        if aggression > 0.3 and self._rng.random() < aggression:
            return [BusinessAction(
                action_id=str(uuid.uuid4()), turn=state.turn,
                commander_id=self.commander_id, entity_id=self.unit_id,
                action_type="COMPETE", target=target.position,
                target_competitor_id=target.id,
                intensity=min(1.0, aggression + 0.2),
                reasoning=(
                    f"Competing against {target.name} in "
                    f"{target.position.region}:{target.position.segment}"
                ),
            )]
        else:
            return [BusinessAction(
                action_id=str(uuid.uuid4()), turn=state.turn,
                commander_id=self.commander_id, entity_id=self.unit_id,
                action_type="DEFEND", reasoning="Defending market position",
            )]

    def _parse_response(self, text: str, state) -> list:
        from app.domains.business.models import BusinessAction
        try:
            clean = text.strip()
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0]
            data = json.loads(clean)
            if not isinstance(data, list):
                data = [data]
            return [BusinessAction(
                action_id=str(uuid.uuid4()), turn=state.turn,
                commander_id=self.commander_id, entity_id=self.unit_id,
                action_type=item.get("action_type", "HOLD"),
                target_competitor_id=item.get("target_competitor_id"),
                reasoning=item.get("reasoning", ""),
            ) for item in data]
        except Exception:
            unit = state.get_unit(self.unit_id)
            return self._fallback_decide(state, unit)


class BusinessCEO(BusinessAgent):
    """CEO-level agent. Sets strategic direction for all own business units."""

    def _build_persona(self) -> str:
        return (
            f"You are {self.commander['name']}, CEO of {self.side}.\n"
            f"Set overall corporate strategy.\n"
            f"Output JSON array of directives for each business unit:\n"
            f'[{{"target_unit_id": "...", "mission": "COMPETE|DEFEND|EXPAND|INVEST_RD|HOLD", '
            f'"reasoning": "..."}}]'
        )

    def _fallback_decide(self, state, unit) -> list:
        """CEO fallback: issue DEFEND to all own units."""
        own_units = state.get_units_by_side(self.side)
        # Return directive dicts (not BusinessAction — CEO issues orders, not actions)
        return [
            {"target_unit_id": u.id, "mission": "DEFEND", "reasoning": "Maintain positions"}
            for u in own_units
            if u.status != "BANKRUPT" and u.id != self.unit_id
        ]
