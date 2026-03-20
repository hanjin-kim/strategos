from __future__ import annotations
from dataclasses import dataclass, field
from app.models.actions import MilitaryAction, ActionType
from app.models.domain import UnitStatus, TerrainType
from app.utils.hex_grid import hex_distance


@dataclass(frozen=True)
class ValidationResult:
    valid_actions: list[MilitaryAction]
    rejections: list[tuple[MilitaryAction, str]]  # (rejected action, reason)

    @property
    def has_rejections(self) -> bool:
        return len(self.rejections) > 0


class ConstraintEngine:
    """Validates all agent actions against game rules. Prevents numeric hallucination."""

    def validate(
        self,
        actions: list[MilitaryAction],
        game_state,
        authority_map: dict[str, set[str]] | None = None,
    ) -> ValidationResult:
        """Validate all actions. Return valid ones and rejections with reasons."""
        valid = []
        rejections = []
        seen_unit_ids: set[str] = set()

        for action in actions:
            # Check for duplicate unit actions
            if action.unit_id in seen_unit_ids:
                rejections.append((action, f"Duplicate action for unit {action.unit_id}"))
                continue

            reason = self._validate_action(action, game_state)
            if reason:
                rejections.append((action, reason))
                continue

            if authority_map:
                reason = self._validate_authority(action, authority_map)
                if reason:
                    rejections.append((action, reason))
                    continue

            valid.append(action)
            seen_unit_ids.add(action.unit_id)

        return ValidationResult(valid_actions=valid, rejections=rejections)

    def _validate_authority(self, action: MilitaryAction, authority_map: dict[str, set[str]]) -> str | None:
        allowed = authority_map.get(action.commander_id, set())
        if not allowed:
            return None  # No authority data, skip check
        if action.unit_id not in allowed:
            return f"Commander {action.commander_id} has no authority over unit {action.unit_id}"
        return None

    def _validate_action(self, action: MilitaryAction, game_state) -> str | None:
        """Return rejection reason or None if valid."""
        # 1. Unit exists
        unit = game_state.get_unit(action.unit_id)
        if unit is None:
            return f"Unit {action.unit_id} does not exist"

        # 2. Ownership check
        commander = game_state.commanders.get(action.commander_id)
        if commander is None:
            return f"Commander {action.commander_id} does not exist"
        if unit.side != commander.side:
            return f"Unit {action.unit_id} belongs to {unit.side.value}, not {commander.side.value}"

        # 3. Unit status check
        if unit.status == UnitStatus.DESTROYED:
            return f"Unit {action.unit_id} is destroyed"
        if unit.status == UnitStatus.ROUTED and action.action_type not in (ActionType.RETREAT, ActionType.DO_NOTHING):
            return f"Unit {action.unit_id} is routed, can only retreat or do nothing"

        # 4. DO_NOTHING and HOLD always valid
        if action.action_type in (ActionType.DO_NOTHING, ActionType.HOLD, ActionType.DEFEND):
            return None

        # 5. MOVE validation
        if action.action_type == ActionType.MOVE:
            return self._validate_move(action, unit, game_state)

        # 6. ATTACK validation
        if action.action_type == ActionType.ATTACK:
            return self._validate_attack(action, unit, game_state)

        # 7. RETREAT validation
        if action.action_type == ActionType.RETREAT:
            return self._validate_move(action, unit, game_state)  # same as move

        return None

    def _validate_move(self, action: MilitaryAction, unit, game_state) -> str | None:
        if action.target_hex is None:
            return "Move action requires target_hex"
        distance = hex_distance(unit.position, action.target_hex)
        if distance > unit.movement_points:
            return f"Insufficient movement points: need {distance}, have {unit.movement_points}"
        terrain = game_state.get_terrain_at(action.target_hex)
        if terrain and terrain.terrain_type == TerrainType.WATER:
            return "Cannot enter water hex"
        return None

    def _validate_attack(self, action: MilitaryAction, unit, game_state) -> str | None:
        if action.target_hex is None and action.target_unit_id is None:
            return "Attack action requires target_hex or target_unit_id"
        if unit.ammo < 0.1:
            return "Insufficient ammo for attack"
        # Check range
        if action.target_hex:
            distance = hex_distance(unit.position, action.target_hex)
            if distance > unit.effective_range:
                return f"Target out of range: distance {distance}, range {unit.effective_range}"
        if action.target_unit_id:
            target = game_state.get_unit(action.target_unit_id)
            if target is None:
                return f"Target unit {action.target_unit_id} does not exist"
            if target.side == unit.side:
                return "Cannot attack friendly unit"
            distance = hex_distance(unit.position, target.position)
            if distance > unit.effective_range:
                return f"Target out of range: distance {distance}, range {unit.effective_range}"
        return None

    def audit_state(self, game_state) -> list[str]:
        """Periodic sanity check (every 5 turns). Detect unrealistic state."""
        warnings = []
        for uid, unit in game_state.units.items():
            if unit.strength < 0:
                warnings.append(f"Unit {uid} has negative strength: {unit.strength}")
            if unit.morale < 0:
                warnings.append(f"Unit {uid} has negative morale: {unit.morale}")
            if unit.ammo < 0:
                warnings.append(f"Unit {uid} has negative ammo: {unit.ammo}")
            if unit.fuel < 0:
                warnings.append(f"Unit {uid} has negative fuel: {unit.fuel}")
        return warnings
