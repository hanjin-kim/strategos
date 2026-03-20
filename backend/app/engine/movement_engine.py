from __future__ import annotations

from app.models.domain import HexCoord, Unit, TerrainHex, TerrainType, UnitType, UnitStatus, Side
from app.models.actions import MilitaryAction, ActionType
from app.models.simulation import MovementResult
from app.utils.hex_grid import hex_astar, hex_distance, hex_neighbors, movement_cost_default


class MovementEngine:
    """WEGO 2-pass movement resolution.

    Pass 1: Calculate intended destinations for all units (based on current state).
    Pass 2: Resolve conflicts (same-hex collisions, cross-moves) then apply all at once.
    """

    def execute_moves(
        self,
        move_actions: list[MilitaryAction],
        game_state,  # GameState
    ) -> list[MovementResult]:
        """
        Execute all move actions simultaneously (WEGO).
        Returns list of MovementResults. Caller applies to GameState.
        """
        # Pass 1: Calculate intended paths and destinations
        intentions: list[tuple[MilitaryAction, list[HexCoord], int]] = []  # (action, path, mp_spent)

        for action in move_actions:
            if action.action_type not in (ActionType.MOVE, ActionType.RETREAT):
                continue
            unit = game_state.get_unit(action.unit_id)
            if unit is None or unit.status in (UnitStatus.DESTROYED,):
                continue
            if action.target_hex is None:
                continue

            path = self._calculate_path(unit, action.target_hex, game_state)
            if path is None or len(path) < 2:
                # Can't move, stay in place
                intentions.append((action, [unit.position], 0))
                continue

            # Walk along path spending movement points
            walkable_path, mp_spent = self._walk_path(unit, path, game_state)
            intentions.append((action, walkable_path, mp_spent))

        # Pass 2: Resolve conflicts
        results = self._resolve_conflicts(intentions, game_state)
        return results

    def _calculate_path(self, unit: Unit, target: HexCoord, game_state) -> list[HexCoord] | None:
        """A* pathfinding avoiding impassable terrain."""
        blocked = set()
        # Block hexes with enemy units (can't move through)
        for other in game_state.units.values():
            if other.side != unit.side and other.status != UnitStatus.DESTROYED:
                blocked.add(other.position)
        # Don't block the target even if enemy is there (triggers combat)
        blocked.discard(target)

        return hex_astar(
            start=unit.position,
            goal=target,
            terrain_map=game_state.terrain,
            cost_fn=lambda t: self._movement_cost_for_unit(unit, t),
            blocked=blocked,
        )

    def _walk_path(
        self, unit: Unit, path: list[HexCoord], game_state
    ) -> tuple[list[HexCoord], int]:
        """Walk along path spending movement points. Return (actual_path, mp_spent)."""
        actual_path = [path[0]]
        mp_spent = 0
        remaining = unit.movement_points

        for i in range(1, len(path)):
            terrain = game_state.get_terrain_at(path[i])
            if terrain is None:
                break
            cost = self._movement_cost_for_unit(unit, terrain)
            if cost > remaining:
                break
            remaining -= cost
            mp_spent += cost
            actual_path.append(path[i])

        return actual_path, mp_spent

    def _resolve_conflicts(
        self,
        intentions: list[tuple[MilitaryAction, list[HexCoord], int]],
        game_state,
    ) -> list[MovementResult]:
        """
        Resolve WEGO conflicts:
        1. If two units from different sides intend same hex -> both stay, trigger combat
        2. If two friendly units intend same hex -> first one moves, second stays
        3. Cross-moves (A->B, B->A same sides) -> both stay, trigger combat if enemies
        """
        # Map intended destination -> list of (action, path, mp_spent)
        dest_map: dict[HexCoord, list[tuple[MilitaryAction, list[HexCoord], int]]] = {}
        for action, path, mp_spent in intentions:
            dest = path[-1] if path else None
            if dest is not None:
                if dest not in dest_map:
                    dest_map[dest] = []
                dest_map[dest].append((action, path, mp_spent))

        results: list[MovementResult] = []
        cancelled: set[str] = set()  # unit_ids whose moves are cancelled

        # Check cross-moves (A->B where B->A)
        for action_a, path_a, _ in intentions:
            unit_a = game_state.get_unit(action_a.unit_id)
            if unit_a is None:
                continue
            dest_a = path_a[-1] if path_a else unit_a.position
            for action_b, path_b, _ in intentions:
                if action_a.unit_id == action_b.unit_id:
                    continue
                unit_b = game_state.get_unit(action_b.unit_id)
                if unit_b is None:
                    continue
                dest_b = path_b[-1] if path_b else unit_b.position
                # Cross-move: A goes to B's position, B goes to A's position
                if dest_a == unit_b.position and dest_b == unit_a.position:
                    if unit_a.side != unit_b.side:
                        # Enemy cross-move -> both cancelled, trigger combat
                        cancelled.add(action_a.unit_id)
                        cancelled.add(action_b.unit_id)

        # Check same-destination conflicts
        for dest, group in dest_map.items():
            if len(group) <= 1:
                continue
            sides = set()
            for action, _, _ in group:
                unit = game_state.get_unit(action.unit_id)
                if unit:
                    sides.add(unit.side)
            if len(sides) > 1:
                # Different sides -> all cancelled, trigger combat at destination
                for action, _, _ in group:
                    cancelled.add(action.unit_id)
            else:
                # Same side -> only first moves, rest cancelled
                for action, _, _ in group[1:]:
                    cancelled.add(action.unit_id)

        # Build results
        for action, path, mp_spent in intentions:
            unit = game_state.get_unit(action.unit_id)
            if unit is None:
                continue

            if action.unit_id in cancelled:
                # Movement cancelled - stay in place
                final_pos = unit.position
                actual_mp = 0
                actual_path = [unit.position]
            else:
                final_pos = path[-1] if path else unit.position
                actual_mp = mp_spent
                actual_path = path

            # Check for enemy contact at final position
            triggered = []
            for neighbor_hex in hex_neighbors(final_pos):
                for other in game_state.get_units_at(neighbor_hex):
                    if other.side != unit.side and other.status != UnitStatus.DESTROYED:
                        triggered.append((unit.id, other.id))

            results.append(MovementResult(
                unit_id=unit.id,
                path=[HexCoord(q=h.q, r=h.r) for h in actual_path],
                final_position=final_pos,
                movement_spent=actual_mp,
                remaining_mp=unit.movement_points - actual_mp,
                triggered_combats=triggered,
            ))

        return results

    @staticmethod
    def _movement_cost_for_unit(unit: Unit, terrain: TerrainHex) -> int:
        """Unit type-specific movement costs."""
        base_cost = movement_cost_default(terrain)
        # Armor has +1 cost in mountains
        if unit.unit_type == UnitType.ARMOR and terrain.terrain_type == TerrainType.MOUNTAIN:
            base_cost += 1
        return base_cost
