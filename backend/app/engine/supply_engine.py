from __future__ import annotations

from app.models.domain import HexCoord, Side, UnitStatus, UnitType
from app.models.supply import SupplyLevel, SupplyStatus
from app.utils.hex_grid import hex_astar

SUPPLY_DISTANCE_THRESHOLD = 8


class SupplyEngine:
    """Supply line calculation, interdiction detection, degradation effects."""

    def calculate_supply_status(self, game_state, graph=None) -> dict[str, SupplyStatus]:
        """Calculate supply status for all active units.

        - HQ units are always FULL
        - Other units: trace path to nearest friendly HQ via hex_astar
        - If no path exists or path crosses enemy-occupied hex: CUT_OFF
        - If path > 8 hexes: REDUCED
        - Otherwise: FULL
        """
        result: dict[str, SupplyStatus] = {}

        for unit in game_state.units.values():
            if unit.status in (UnitStatus.DESTROYED, UnitStatus.ROUTED):
                continue

            # HQ units are always fully supplied
            if unit.unit_type == UnitType.HQ:
                result[unit.id] = SupplyStatus(
                    unit_id=unit.id,
                    level=SupplyLevel.FULL,
                    turns_without_supply=0,
                    supply_route_length=0,
                )
                continue

            # Get existing supply status (for turns_without_supply tracking)
            existing = game_state.supply_status.get(unit.id)
            prev_turns_without = existing.turns_without_supply if existing else 0

            path = self.trace_supply_path(unit, game_state)

            if path is None:
                # No path to any HQ
                result[unit.id] = SupplyStatus(
                    unit_id=unit.id,
                    level=SupplyLevel.CUT_OFF,
                    turns_without_supply=prev_turns_without + 1,
                    supply_route_length=0,
                )
                continue

            # Check interdiction
            interdiction_hex = self.check_interdiction(path, game_state, unit.side)
            if interdiction_hex is not None:
                result[unit.id] = SupplyStatus(
                    unit_id=unit.id,
                    level=SupplyLevel.CUT_OFF,
                    turns_without_supply=prev_turns_without + 1,
                    supply_route_length=len(path) - 1,
                )
                continue

            route_length = len(path) - 1

            if route_length > SUPPLY_DISTANCE_THRESHOLD:
                level = SupplyLevel.REDUCED
                new_turns_without = prev_turns_without + 1
            else:
                level = SupplyLevel.FULL
                new_turns_without = 0

            result[unit.id] = SupplyStatus(
                unit_id=unit.id,
                level=level,
                turns_without_supply=new_turns_without,
                supply_route_length=route_length,
            )

        return result

    def check_interdiction(
        self,
        supply_path: list[HexCoord],
        game_state,
        side: Side,
    ) -> HexCoord | None:
        """Check if any enemy unit sits on the supply path. Returns interdiction hex or None."""
        # Build set of enemy-occupied hexes (skip first hex which is the unit itself)
        enemy_positions: set[HexCoord] = set()
        for unit in game_state.units.values():
            if unit.side != side and unit.status not in (UnitStatus.DESTROYED, UnitStatus.ROUTED):
                enemy_positions.add(unit.position)

        for hex_coord in supply_path[1:]:  # skip start (the unit's own hex)
            if hex_coord in enemy_positions:
                return hex_coord

        return None

    def apply_supply_effects(self, game_state) -> list[dict]:
        """Apply supply effects to units based on their supply_status.

        Effects:
        - FULL: no effect
        - REDUCED: attack_power *= 0.8 (applied via model_copy)
        - CUT_OFF: attack_power *= 0.5, ammo -= 0.1/turn, fuel -= 0.1/turn
        - CUT_OFF 3+ turns: morale -= 0.1/turn additional
        Returns list of effect descriptions for logging.
        """
        effects: list[dict] = []

        for unit_id, supply_status in game_state.supply_status.items():
            unit = game_state.units.get(unit_id)
            if unit is None:
                continue
            if unit.status in (UnitStatus.DESTROYED, UnitStatus.ROUTED):
                continue
            if supply_status.level == SupplyLevel.FULL:
                continue

            changes: dict = {}

            if supply_status.level == SupplyLevel.REDUCED:
                changes["attack_power"] = unit.attack_power * 0.8
                effects.append({
                    "unit_id": unit_id,
                    "effect": "REDUCED",
                    "attack_power": changes["attack_power"],
                })

            elif supply_status.level == SupplyLevel.CUT_OFF:
                changes["attack_power"] = unit.attack_power * 0.5
                changes["ammo"] = max(0.0, unit.ammo - 0.1)
                changes["fuel"] = max(0.0, unit.fuel - 0.1)

                if supply_status.turns_without_supply >= 3:
                    changes["morale"] = max(0.0, unit.morale - 0.1)

                effects.append({
                    "unit_id": unit_id,
                    "effect": "CUT_OFF",
                    "turns_without_supply": supply_status.turns_without_supply,
                    **{k: v for k, v in changes.items()},
                })

            if changes:
                game_state.update_unit(unit_id, **changes)

        return effects

    def trace_supply_path(self, unit, game_state) -> list[HexCoord] | None:
        """Find shortest path from unit to nearest friendly HQ using hex_astar."""
        hq_units = [
            u for u in game_state.units.values()
            if u.side == unit.side
            and u.unit_type == UnitType.HQ
            and u.status not in (UnitStatus.DESTROYED, UnitStatus.ROUTED)
        ]

        if not hq_units:
            return None

        best_path: list[HexCoord] | None = None

        for hq in hq_units:
            if hq.position == unit.position:
                return [unit.position]

            path = hex_astar(
                start=unit.position,
                goal=hq.position,
                terrain_map=game_state.terrain,
            )
            if path is not None:
                if best_path is None or len(path) < len(best_path):
                    best_path = path

        return best_path
