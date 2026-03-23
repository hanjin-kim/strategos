from __future__ import annotations
from typing import Any
import random
from app.domains.business.models import MarketNode, CompetitionOutcome


class MarketSpace:
    """Market as a graph of connected segments. Implements Space Protocol."""

    def __init__(self, connections: dict[str, list[str]], terrains: dict[str, Any]):
        # connections: {"Korea:EV": ["China:EV", "Korea:ESS"], ...}
        self._connections = connections
        self._terrains = terrains

    def neighbors(self, pos: Any) -> list:
        if isinstance(pos, MarketNode):
            key = f"{pos.region}:{pos.segment}"
            neighbor_keys = self._connections.get(key, [])
            result = []
            for nk in neighbor_keys:
                parts = nk.split(":")
                if len(parts) == 2:
                    result.append(MarketNode(region=parts[0], segment=parts[1]))
            return result
        return []

    def distance(self, a: Any, b: Any) -> float:
        if isinstance(a, MarketNode) and isinstance(b, MarketNode):
            if a == b:
                return 0.0
            if f"{b.region}:{b.segment}" in self._connections.get(f"{a.region}:{a.segment}", []):
                return 1.0
            return 2.0  # Not directly connected
        return float('inf')

    def is_passable(self, pos: Any) -> bool:
        if isinstance(pos, MarketNode):
            key = f"{pos.region}:{pos.segment}"
            terrain = self._terrains.get(key)
            return terrain.entry_barrier < 0.95 if terrain else True
        return False


class MarketCompetitionResolver:
    """Resolves market competition. Implements InteractionResolver Protocol."""

    def __init__(self, rng_seed: int = 42):
        self.rng = random.Random(rng_seed)

    @staticmethod
    def _to_market_node(pos: Any) -> MarketNode:
        """Convert any position to MarketNode. Handles HexCoord fallback."""
        if isinstance(pos, MarketNode):
            return pos
        # HexCoord or other — create a generic market node
        if hasattr(pos, 'q') and hasattr(pos, 'r'):
            return MarketNode(region=f"region_{pos.q}", segment=f"seg_{pos.r}")
        return MarketNode(region="unknown", segment="unknown")

    def resolve(self, actors: list, targets: list, context: dict) -> dict:
        """Market share competition based on competitive power, brand, and randomness."""
        if not actors or not targets:
            return {"outcome": None}

        attacker = actors[0]
        defender = targets[0]

        # Competitive power comparison
        # Map: competitive_power=attack_power, brand_loyalty=defense_power, marketing_budget=ammo
        atk_power = getattr(attacker, 'competitive_power', None) or getattr(attacker, 'attack_power', 5.0)
        def_loyalty = getattr(defender, 'brand_loyalty', None) or getattr(defender, 'defense_power', 5.0)

        # Marketing budget boost
        atk_marketing = getattr(attacker, 'marketing_budget', None) or getattr(attacker, 'ammo', 0.5)

        # Calculate force ratio
        effective_attack = atk_power * (1.0 + atk_marketing * 0.3)
        effective_defense = def_loyalty * 1.2  # Defenders have inherent advantage

        ratio = effective_attack / max(effective_defense, 0.1)

        # Random factor
        roll = self.rng.random()

        # Determine share changes
        if ratio > 1.5 and roll > 0.3:
            atk_change = 0.1 * min(ratio - 1.0, 0.5)
            def_change = -atk_change
            narrative = (
                f"{getattr(attacker, 'name', attacker.id)} gains market share "
                f"from {getattr(defender, 'name', defender.id)}"
            )
        elif ratio > 1.0 and roll > 0.5:
            atk_change = 0.05
            def_change = -0.05
            narrative = f"Slight market shift toward {getattr(attacker, 'name', attacker.id)}"
        elif ratio < 0.7 and roll < 0.3:
            atk_change = -0.05
            def_change = 0.05
            narrative = f"{getattr(defender, 'name', defender.id)} strengthens market position"
        else:
            atk_change = 0.0
            def_change = 0.0
            narrative = "Market positions unchanged"

        return {
            "outcome": CompetitionOutcome(
                attacker_id=attacker.id,
                defender_id=defender.id,
                market_node=self._to_market_node(getattr(attacker, 'position', None)),
                attacker_share_change=round(atk_change, 3),
                defender_share_change=round(def_change, 3),
                narrative=narrative,
            ),
            "attacker_id": attacker.id,
            "defender_id": defender.id,
            "attacker_share_change": atk_change,
            "defender_share_change": def_change,
            "narrative": narrative,
        }


class BusinessMover:
    """Handles market entry/expansion. Implements MoverEngine Protocol."""

    def execute_moves(self, actions: list, state: Any) -> list:
        """Process EXPAND actions — move business unit to new market."""
        results = []
        for action in actions:
            if (
                hasattr(action, 'action_type')
                and action.action_type == "EXPAND"
                and hasattr(action, 'target')
                and action.target
            ):
                results.append({
                    "unit_id": (
                        action.entity_id
                        if hasattr(action, 'entity_id')
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
                if hasattr(action, 'entity_id')
                else getattr(action, 'unit_id', '')
            )
            unit = None
            if hasattr(state, 'get_unit'):
                unit = state.get_unit(unit_id)
            elif hasattr(state, 'get_entity'):
                unit = state.get_entity(unit_id)

            if unit and getattr(unit, 'status', 'ACTIVE') != 'BANKRUPT':
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
        """Victory if one side has all units BANKRUPT."""
        if not hasattr(state, 'units'):
            return False
        sides = set()
        active_sides = set()
        for u in state.units.values():
            side = u.side if isinstance(u.side, str) else u.side.value
            sides.add(side)
            status = u.status if isinstance(u.status, str) else u.status.value
            if status not in ("BANKRUPT", "DESTROYED"):
                active_sides.add(side)
        return len(sides) > 1 and len(active_sides) <= 1
