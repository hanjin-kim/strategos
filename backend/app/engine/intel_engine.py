from __future__ import annotations

from app.models.domain import HexCoord, Side, Unit, UnitStatus, TerrainType
from app.models.intel import (
    IntelLevel,
    IntelReport,
    VISIBILITY_TABLE,
    TERRAIN_VISIBILITY_MODIFIERS,
    ELEVATION_BONUS_THRESHOLD,
)
from app.utils.hex_grid import hex_spiral, hex_distance


class IntelEngine:
    """Fog-of-war engine: visibility calculation, intel tracking, degradation."""

    def __init__(self, visibility_table: dict[str, int] | None = None):
        self.visibility_table = visibility_table or VISIBILITY_TABLE

    def get_visibility_radius(self, unit: Unit, observer_elevation: int = 0) -> int:
        """Calculate visibility radius for a unit based on type and elevation."""
        base = self.visibility_table.get(unit.unit_type.value, 2)
        if observer_elevation >= ELEVATION_BONUS_THRESHOLD:
            base += 1
        return max(base, 0)

    def calculate_visibility(
        self,
        unit: Unit,
        terrain_map: dict[HexCoord, ...],
    ) -> set[HexCoord]:
        """Calculate visible hexes for a single unit, considering terrain."""
        observer_terrain = terrain_map.get(unit.position)
        observer_elevation = observer_terrain.elevation if observer_terrain else 0
        radius = self.get_visibility_radius(unit, observer_elevation)

        visible = set()
        for coord in hex_spiral(unit.position, radius):
            if coord not in terrain_map:
                continue
            visible.add(coord)
        return visible

    def calculate_side_visibility(
        self,
        units: list[Unit],
        terrain_map: dict[HexCoord, ...],
    ) -> set[HexCoord]:
        """Union of visibility for all units on a side."""
        visible = set()
        for unit in units:
            if unit.status in (UnitStatus.DESTROYED, UnitStatus.ROUTED):
                continue
            visible |= self.calculate_visibility(unit, terrain_map)
        return visible

    def is_hidden_by_terrain(
        self,
        target_hex: HexCoord,
        terrain_map: dict[HexCoord, ...],
    ) -> bool:
        """Check if a target hex has concealment (FOREST)."""
        terrain = terrain_map.get(target_hex)
        if terrain and terrain.terrain_type == TerrainType.FOREST:
            return True
        return False

    def detect_unit(
        self,
        observer: Unit,
        target: Unit,
        terrain_map: dict[HexCoord, ...],
    ) -> bool:
        """Can observer detect target? Forest targets require adjacency."""
        visible_hexes = self.calculate_visibility(observer, terrain_map)
        if target.position not in visible_hexes:
            return False
        if self.is_hidden_by_terrain(target.position, terrain_map):
            return hex_distance(observer.position, target.position) <= 1
        return True

    def update_intel(self, game_state, side: Side) -> dict[str, IntelReport]:
        """Update intel reports for one side. Returns dict of unit_id -> IntelReport."""
        own_units = [
            u for u in game_state.units.values()
            if u.side == side and u.status not in (UnitStatus.DESTROYED, UnitStatus.ROUTED)
        ]
        enemy_units = [
            u for u in game_state.units.values()
            if u.side != side and u.status != UnitStatus.DESTROYED
        ]

        # Get existing reports (preserve stale ones)
        existing = {}
        if hasattr(game_state, "intel_reports"):
            existing = game_state.intel_reports.get(side.value, {})

        reports: dict[str, IntelReport] = {}

        # Calculate combined visibility
        visible_hexes = self.calculate_side_visibility(own_units, game_state.terrain)

        for enemy in enemy_units:
            # Check if any own unit can detect this enemy
            detected = False
            for own_unit in own_units:
                if self.detect_unit(own_unit, enemy, game_state.terrain):
                    detected = True
                    break

            if detected:
                reports[enemy.id] = IntelReport(
                    unit_id=enemy.id,
                    last_seen_turn=game_state.turn,
                    last_known_position=enemy.position,
                    confidence=IntelLevel.CONFIRMED,
                    reported_strength=enemy.strength,
                    reported_type=enemy.unit_type.value,
                )
            elif enemy.id in existing:
                # Preserve old report (will be degraded later)
                reports[enemy.id] = existing[enemy.id]

        return reports

    def degrade_intel(
        self,
        intel_reports: dict[str, IntelReport],
        current_turn: int,
    ) -> dict[str, IntelReport]:
        """Degrade intel over time. CONFIRMED->ESTIMATED->UNKNOWN."""
        degraded = {}
        for uid, report in intel_reports.items():
            age = current_turn - report.last_seen_turn
            if age == 0:
                new_confidence = IntelLevel.CONFIRMED
            elif age <= 2:
                new_confidence = IntelLevel.ESTIMATED
            else:
                new_confidence = IntelLevel.UNKNOWN

            if new_confidence != report.confidence:
                degraded[uid] = report.model_copy(update={"confidence": new_confidence})
            else:
                degraded[uid] = report
        return degraded

    def filter_context_for_agent(self, game_state, commander) -> dict:
        """Build filtered enemy info for agent context based on intel."""
        side = commander.side
        reports = {}
        if hasattr(game_state, "intel_reports"):
            reports = game_state.intel_reports.get(side.value, {})

        own_units = [
            u for u in game_state.units.values()
            if u.side == side and u.status not in (UnitStatus.DESTROYED, UnitStatus.ROUTED)
        ]
        visible_hexes = self.calculate_side_visibility(own_units, game_state.terrain)

        known_enemy = []
        for uid, report in reports.items():
            if report.confidence == IntelLevel.CONFIRMED:
                unit = game_state.units.get(uid)
                if unit and unit.status != UnitStatus.DESTROYED:
                    known_enemy.append(unit)
            elif report.confidence == IntelLevel.ESTIMATED:
                known_enemy.append(
                    _make_estimated_unit(report)
                )
            # UNKNOWN: not included in context

        return {
            "own_units": own_units,
            "known_enemy": known_enemy,
            "visible_hexes": visible_hexes,
        }


def _make_estimated_unit(report: IntelReport):
    """Create a partial unit dict for estimated intel (not a real Unit)."""
    return {
        "id": report.unit_id,
        "type": report.reported_type,
        "position": {"q": report.last_known_position.q, "r": report.last_known_position.r},
        "strength": report.reported_strength,
        "confidence": "ESTIMATED",
    }
