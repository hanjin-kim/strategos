from __future__ import annotations
from typing import Any
import random
from app.domains.business.models import MarketNode, CompetitionOutcome


class MarketSpace:
    """Market as a graph of connected segments. Implements Space Protocol."""

    def __init__(self, connections: dict[str, list[str]], market_data: dict = None):
        self._connections = connections
        self._market_data = market_data or {}

    def neighbors(self, pos: Any) -> list:
        if isinstance(pos, MarketNode):
            key = f"{pos.region}:{pos.segment}"
            return [
                MarketNode(region=p.split(":")[0], segment=p.split(":")[1])
                for p in self._connections.get(key, [])
                if ":" in p
            ]
        return []

    def distance(self, a: Any, b: Any) -> float:
        if isinstance(a, MarketNode) and isinstance(b, MarketNode):
            if a == b:
                return 0.0
            key_a = f"{a.region}:{a.segment}"
            if f"{b.region}:{b.segment}" in self._connections.get(key_a, []):
                return 1.0
            return 2.0
        return float("inf")

    def is_passable(self, pos: Any) -> bool:
        if isinstance(pos, MarketNode):
            key = f"{pos.region}:{pos.segment}"
            data = self._market_data.get(key, {})
            return data.get("entry_barrier", 0) < 0.95
        return False


class MarketCompetitionResolver:
    """Resolves market competition. NO military imports."""

    def __init__(self, rng_seed: int = 42):
        self.rng = random.Random(rng_seed)

    def resolve(self, actors: list, targets: list, context: dict) -> dict:
        """Market share competition based on competitive_power, brand_loyalty, marketing_budget."""
        if not actors or not targets:
            return {"outcome": None}

        attacker = actors[0]
        defender = targets[0]

        # Read business fields directly
        atk_power = getattr(attacker, "competitive_power", 10.0)
        def_loyalty = getattr(defender, "brand_loyalty", 10.0)
        atk_marketing = getattr(attacker, "marketing_budget", 0.5)
        atk_rd = getattr(attacker, "rd_capability", 0.5)

        # Effective competitive strength
        effective_attack = atk_power * (1.0 + atk_marketing * 0.3 + atk_rd * 0.2)
        effective_defense = def_loyalty * 1.2

        ratio = effective_attack / max(effective_defense, 0.1)
        roll = self.rng.random()

        if ratio > 1.5 and roll > 0.3:
            share_shift = 0.08 * min(ratio - 1.0, 0.5)
            narrative = f"{getattr(attacker, 'name', attacker.id)} captures market share"
        elif ratio > 1.0 and roll > 0.4:
            share_shift = 0.04
            narrative = f"Slight market shift toward {getattr(attacker, 'name', attacker.id)}"
        elif ratio < 0.7 and roll < 0.3:
            share_shift = -0.04
            narrative = f"{getattr(defender, 'name', defender.id)} strengthens position"
        else:
            share_shift = 0.0
            narrative = "Market positions unchanged"

        # Marketing budget consumed
        budget_drain = 0.05 if share_shift != 0 else 0.02

        outcome = CompetitionOutcome(
            attacker_id=attacker.id,
            defender_id=defender.id,
            market_node=(
                attacker.position
                if isinstance(getattr(attacker, "position", None), MarketNode)
                else MarketNode(region="unknown", segment="unknown")
            ),
            attacker_share_change=round(share_shift, 4),
            defender_share_change=round(-share_shift, 4),
            narrative=narrative,
        )

        return {
            "outcome": outcome,
            "attacker_id": attacker.id,
            "defender_id": defender.id,
            "attacker_share_change": round(share_shift, 4),
            "defender_share_change": round(-share_shift, 4),
            "attacker_budget_drain": budget_drain,
            "narrative": narrative,
        }


class BusinessMover:
    """Handles market entry/expansion. Implements MoverEngine Protocol."""

    def execute_moves(self, actions: list, state: Any) -> list:
        """Process EXPAND actions — move business unit to new market."""
        results = []
        for action in actions:
            if (
                hasattr(action, "action_type")
                and action.action_type == "EXPAND"
                and hasattr(action, "target")
                and action.target
            ):
                results.append({
                    "unit_id": (
                        action.entity_id
                        if hasattr(action, "entity_id")
                        else action.unit_id
                    ),
                    "final_position": action.target,
                    "remaining_mp": 0,
                    "success": True,
                })
        return results


class BusinessConstraints:
    """Validates business actions. Implements DomainConstraints Protocol."""

    def validate(self, actions: list, state: Any, **kwargs) -> Any:
        """Basic validation: unit exists and is active."""
        valid = []
        rejected = []
        for action in actions:
            unit_id = (
                action.entity_id
                if hasattr(action, "entity_id")
                else getattr(action, "unit_id", "")
            )
            unit = None
            if hasattr(state, "get_unit"):
                unit = state.get_unit(unit_id)
            elif hasattr(state, "get_entity"):
                unit = state.get_entity(unit_id)

            if unit and getattr(unit, "status", "ACTIVE") != "BANKRUPT":
                valid.append(action)
            else:
                rejected.append(action)

        class Result:
            def __init__(self, v, r):
                self.valid_actions = v
                self.rejections = r
                self.has_rejections = len(r) > 0

        return Result(valid, rejected)


class BusinessVictory:
    """Check if competition has a decisive winner. Implements VictoryChecker Protocol."""

    def check(self, state: Any) -> bool:
        """Victory if one side has all units BANKRUPT/DESTROYED."""
        if not hasattr(state, "units"):
            return False
        sides: set[str] = set()
        active_sides: set[str] = set()
        for u in state.units.values():
            side = u.side if isinstance(u.side, str) else str(u.side)
            sides.add(side)
            status = u.status if isinstance(u.status, str) else str(u.status)
            if status not in ("BANKRUPT", "DESTROYED"):
                active_sides.add(side)
        return len(sides) > 1 and len(active_sides) <= 1
