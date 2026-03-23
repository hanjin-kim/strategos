from __future__ import annotations
import random
import uuid
from app.models.domain import Unit, UnitStatus, HexCoord
from app.models.actions import MilitaryAction, ActionType, OrderDirective, MissionType
from app.utils.hex_grid import hex_distance, hex_neighbors


class RuleBasedFallback:
    """Deterministic rule-based AI fallback when LLM fails.

    Priority rules:
    1. If ROUTED -> RETREAT (away from nearest enemy)
    2. If enemy adjacent -> DEFEND
    3. If superior orders ATTACK -> MOVE toward objective_hex (or nearest enemy)
    4. If superior orders DEFEND -> DEFEND at current position
    5. If superior orders WITHDRAW -> RETREAT toward objective_hex
    6. Default -> HOLD
    """

    def decide(
        self,
        commander_id: str,
        unit: Unit,
        game_state,  # GameState
        superior_orders: OrderDirective | None = None,
        rng: random.Random | None = None,
        personality_traits: dict[str, float] | None = None,
    ) -> list[MilitaryAction]:
        """Generate fallback actions for a single unit."""
        if unit.status == UnitStatus.DESTROYED:
            return []

        # Rule 1: Routed units retreat
        if unit.status == UnitStatus.ROUTED:
            return [self._make_retreat(commander_id, unit, game_state)]

        # Rule 2: Enemy adjacent -> defend (personality: aggression may override to ATTACK)
        enemies = game_state.get_adjacent_enemies(unit.id)
        if enemies:
            if (
                personality_traits is not None
                and rng is not None
                and personality_traits.get("aggression", 0.0) > 0.3
                and rng.random() < personality_traits["aggression"]
            ):
                return [self._make_action(commander_id, unit, ActionType.ATTACK,
                                          target_unit_id=enemies[0].id)]
            return [self._make_action(commander_id, unit, ActionType.DEFEND)]

        # Rule 3-5: Follow superior orders if present
        if superior_orders:
            return self._follow_orders(commander_id, unit, superior_orders, game_state)

        # Rule 6: Default hold (personality: caution may trigger RETREAT if weak)
        if (
            personality_traits is not None
            and rng is not None
            and personality_traits.get("caution", 0.0) > 0.7
            and unit.strength < 0.5
        ):
            retreat_hex = self._find_retreat_hex(unit, game_state)
            if retreat_hex:
                return [self._make_action(commander_id, unit, ActionType.RETREAT,
                                          target_hex=retreat_hex)]

        return [self._make_action(commander_id, unit, ActionType.HOLD)]

    def _follow_orders(
        self,
        commander_id: str,
        unit: Unit,
        orders: OrderDirective,
        game_state,
    ) -> list[MilitaryAction]:
        if orders.mission == MissionType.ATTACK:
            target = orders.objective_hex
            if target is None:
                # No objective, find nearest enemy
                target = self._find_nearest_enemy_hex(unit, game_state)
            if target and target != unit.position:
                return [self._make_action(commander_id, unit, ActionType.MOVE, target_hex=target)]
            return [self._make_action(commander_id, unit, ActionType.HOLD)]

        if orders.mission == MissionType.DEFEND:
            return [self._make_action(commander_id, unit, ActionType.DEFEND)]

        if orders.mission in (MissionType.WITHDRAW, MissionType.DELAY):
            target = orders.objective_hex
            if target and target != unit.position:
                return [self._make_action(commander_id, unit, ActionType.RETREAT, target_hex=target)]
            return [self._make_action(commander_id, unit, ActionType.HOLD)]

        if orders.mission == MissionType.RESERVE:
            return [self._make_action(commander_id, unit, ActionType.HOLD)]

        return [self._make_action(commander_id, unit, ActionType.HOLD)]

    def _make_action(
        self,
        commander_id: str,
        unit: Unit,
        action_type: ActionType,
        target_hex: HexCoord | None = None,
        target_unit_id: str | None = None,
    ) -> MilitaryAction:
        return MilitaryAction(
            action_id=str(uuid.uuid4()),
            turn=0,  # Will be set by caller
            commander_id=commander_id,
            unit_id=unit.id,
            action_type=action_type,
            target_hex=target_hex,
            target_unit_id=target_unit_id,
            priority=3,
            reasoning="Rule-based fallback",
        )

    def _make_retreat(self, commander_id: str, unit: Unit, game_state) -> MilitaryAction:
        """Retreat away from nearest enemy."""
        retreat_hex = self._find_retreat_hex(unit, game_state)
        if retreat_hex:
            return self._make_action(commander_id, unit, ActionType.RETREAT, target_hex=retreat_hex)
        return self._make_action(commander_id, unit, ActionType.HOLD)

    def _find_nearest_enemy_hex(self, unit: Unit, game_state) -> HexCoord | None:
        """Find position of nearest enemy unit."""
        enemies = [
            u for u in game_state.units.values()
            if u.side != unit.side and u.status != UnitStatus.DESTROYED
        ]
        if not enemies:
            return None
        nearest = min(enemies, key=lambda e: hex_distance(unit.position, e.position))
        return nearest.position

    def _find_retreat_hex(self, unit: Unit, game_state) -> HexCoord | None:
        """Find best hex to retreat to (away from nearest enemy, on map, not occupied by enemy)."""
        nearest_enemy_pos = self._find_nearest_enemy_hex(unit, game_state)
        if nearest_enemy_pos is None:
            return None

        best_hex = None
        best_dist = -1
        for neighbor in hex_neighbors(unit.position):
            # Must be on map
            if game_state.get_terrain_at(neighbor) is None:
                continue
            # Must not have enemy
            enemies_at = [
                u for u in game_state.get_units_at(neighbor)
                if u.side != unit.side and u.status != UnitStatus.DESTROYED
            ]
            if enemies_at:
                continue
            dist = hex_distance(neighbor, nearest_enemy_pos)
            if dist > best_dist:
                best_dist = dist
                best_hex = neighbor

        return best_hex
