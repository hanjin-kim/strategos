from __future__ import annotations

from app.models.domain import HexCoord, Side, Unit, Commander, TerrainHex, Force, UnitStatus
from app.models.intel import IntelReport
from app.models.supply import SupplyStatus
from app.models.simulation import TurnPhase
from app.utils.hex_grid import hex_neighbors


class GameState:
    """In-memory game state. Mutable within turns, snapshot at boundaries."""

    def __init__(self, scenario_data: dict | None = None):
        self.turn: int = 0
        self.phase: TurnPhase = TurnPhase.COMMAND
        self.units: dict[str, Unit] = {}
        self.terrain: dict[HexCoord, TerrainHex] = {}
        self.commanders: dict[str, Commander] = {}
        self.forces: dict[Side, Force] = {}
        self.combat_log: list = []
        self.intel_reports: dict[str, dict[str, object]] = {}  # side_value -> {unit_id -> IntelReport}
        self.supply_status: dict[str, object] = {}  # unit_id -> SupplyStatus
        self.air_assets: dict[str, object] = {}  # asset_id -> AirAsset
        self.sortie_pools: dict[str, object] = {}  # side_value -> SortiePool
        if scenario_data:
            self._load_scenario(scenario_data)

    # --- Query methods ---
    def get_unit(self, unit_id: str) -> Unit | None:
        return self.units.get(unit_id)

    def get_units_by_side(self, side: Side) -> list[Unit]:
        return [u for u in self.units.values() if u.side == side]

    def get_terrain_at(self, coord: HexCoord) -> TerrainHex | None:
        return self.terrain.get(coord)

    def get_units_at(self, coord: HexCoord) -> list[Unit]:
        return [u for u in self.units.values() if u.position == coord]

    def get_adjacent_enemies(self, unit_id: str) -> list[Unit]:
        unit = self.units.get(unit_id)
        if not unit:
            return []
        adjacent_hexes = set(hex_neighbors(unit.position))
        return [
            u for u in self.units.values()
            if u.side != unit.side
            and u.position in adjacent_hexes
            and u.status not in (UnitStatus.DESTROYED, UnitStatus.ROUTED)
        ]

    # --- Mutation methods (within turn) ---
    def update_unit(self, unit_id: str, **changes) -> None:
        """Replace unit with updated copy. Unit is frozen, so we use model_copy."""
        old = self.units[unit_id]
        self.units[unit_id] = old.model_copy(update=changes)

    def remove_unit(self, unit_id: str) -> None:
        """Mark unit as DESTROYED (don't delete from dict for logging)."""
        if unit_id in self.units:
            self.update_unit(unit_id, status=UnitStatus.DESTROYED)

    def advance_phase(self) -> None:
        phases = [TurnPhase.COMMAND, TurnPhase.EXECUTION, TurnPhase.RESOLUTION]
        idx = phases.index(self.phase)
        if idx < len(phases) - 1:
            self.phase = phases[idx + 1]

    def advance_turn(self) -> None:
        self.turn += 1
        self.phase = TurnPhase.COMMAND
        # Reset movement points for all active units
        for uid, unit in self.units.items():
            if unit.status == UnitStatus.ACTIVE:
                self.units[uid] = unit.model_copy(update={"movement_points": unit.max_movement_points})
        # Reset sortie pools each turn
        for side_val, pool in self.sortie_pools.items():
            if hasattr(pool, 'model_copy'):
                self.sortie_pools[side_val] = pool.model_copy(
                    update={"remaining_sorties": pool.total_sorties}
                )

    # --- Snapshot (turn boundary) ---
    def to_snapshot(self) -> dict:
        """Serialize entire state to JSON-compatible dict."""
        intel_data = {}
        for side_val, reports in self.intel_reports.items():
            intel_data[side_val] = {
                uid: r.model_dump() if hasattr(r, "model_dump") else r
                for uid, r in reports.items()
            }
        supply_data = {
            uid: s.model_dump() if hasattr(s, "model_dump") else s
            for uid, s in self.supply_status.items()
        }
        air_assets_data = {
            aid: a.model_dump() if hasattr(a, "model_dump") else a
            for aid, a in self.air_assets.items()
        }
        sortie_pools_data = {
            sv: p.model_dump() if hasattr(p, "model_dump") else p
            for sv, p in self.sortie_pools.items()
        }
        return {
            "turn": self.turn,
            "phase": self.phase.value,
            "units": {uid: u.model_dump() for uid, u in self.units.items()},
            "terrain": {f"{c.q},{c.r}": t.model_dump() for c, t in self.terrain.items()},
            "commanders": {cid: c.model_dump() for cid, c in self.commanders.items()},
            "forces": {s.value: f.model_dump() for s, f in self.forces.items()},
            "intel_reports": intel_data,
            "supply_status": supply_data,
            "air_assets": air_assets_data,
            "sortie_pools": sortie_pools_data,
        }

    @classmethod
    def from_snapshot(cls, data: dict) -> GameState:
        """Restore state from snapshot dict."""
        state = cls()
        state.turn = data["turn"]
        state.phase = TurnPhase(data["phase"])
        state.units = {uid: Unit.model_validate(u) for uid, u in data["units"].items()}
        state.terrain = {}
        for key, t in data["terrain"].items():
            q, r = key.split(",")
            coord = HexCoord(q=int(q), r=int(r))
            state.terrain[coord] = TerrainHex.model_validate(t)
        state.commanders = {cid: Commander.model_validate(c) for cid, c in data["commanders"].items()}
        state.forces = {Side(s): Force.model_validate(f) for s, f in data["forces"].items()}
        state.intel_reports = {}
        for side_val, reports in data.get("intel_reports", {}).items():
            state.intel_reports[side_val] = {
                uid: IntelReport.model_validate(r) for uid, r in reports.items()
            }
        state.supply_status = {
            uid: SupplyStatus.model_validate(s)
            for uid, s in data.get("supply_status", {}).items()
        }
        from app.models.air import AirAsset, SortiePool
        state.air_assets = {
            aid: AirAsset.model_validate(a)
            for aid, a in data.get("air_assets", {}).items()
        }
        state.sortie_pools = {
            sv: SortiePool.model_validate(p)
            for sv, p in data.get("sortie_pools", {}).items()
        }
        return state

    # --- Scenario loading ---
    def _load_scenario(self, data: dict) -> None:
        """Load scenario JSON into state."""
        # Load terrain (map.hexes)
        if "map" in data:
            for hex_data in data["map"].get("hexes", []):
                coord = HexCoord(q=hex_data["q"], r=hex_data["r"])
                self.terrain[coord] = TerrainHex(
                    coord=coord,
                    terrain_type=hex_data["terrain"],
                    elevation=hex_data.get("elevation", 0),
                    movement_cost=hex_data.get("movement_cost", 1),
                    defense_modifier=hex_data.get("defense_modifier", 1.0),
                    name=hex_data.get("name"),
                )

        # Load forces, units, commanders
        for side_str, force_data in data.get("forces", {}).items():
            side = Side(side_str)
            unit_ids = []
            commander_ids = []

            for unit_data in force_data.get("units", []):
                pos = unit_data["position"]
                unit = Unit(
                    id=unit_data["id"],
                    name=unit_data["name"],
                    side=side,
                    unit_type=unit_data["type"],
                    size=unit_data["size"],
                    position=HexCoord(q=pos["q"], r=pos["r"]),
                    strength=unit_data.get("strength", 1.0),
                    morale=unit_data.get("morale", 0.8),
                    movement_points=unit_data.get("max_movement_points", 2),
                    max_movement_points=unit_data.get("max_movement_points", 2),
                    attack_power=unit_data.get("attack_power", 10.0),
                    defense_power=unit_data.get("defense_power", 10.0),
                    effective_range=unit_data.get("effective_range", 1),
                    ammo=unit_data.get("ammo", 1.0),
                    fuel=unit_data.get("fuel", 1.0),
                    status=UnitStatus.ACTIVE,
                    parent_unit_id=unit_data.get("parent_unit_id"),
                    subordinate_ids=unit_data.get("subordinate_ids", []),
                )
                self.units[unit.id] = unit
                unit_ids.append(unit.id)

            for cmd_data in force_data.get("commanders", []):
                cmd = Commander(
                    id=cmd_data["id"],
                    name=cmd_data["name"],
                    side=side,
                    rank=cmd_data["rank"],
                    unit_id=cmd_data["unit_id"],
                    personality_traits=cmd_data.get("personality_traits", {}),
                )
                self.commanders[cmd.id] = cmd
                commander_ids.append(cmd.id)

            self.forces[side] = Force(
                side=side,
                name=force_data.get("name", side.value),
                commander_ids=commander_ids,
                unit_ids=unit_ids,
            )

        # Load air assets
        for side_str, force_data in data.get("forces", {}).items():
            side = Side(side_str)
            if "air_assets" in force_data:
                from app.models.air import AirAsset, SortiePool, AirMissionType
                for asset_data in force_data["air_assets"].get("assets", []):
                    asset = AirAsset(
                        id=asset_data["id"],
                        name=asset_data["name"],
                        side=side,
                        asset_type=asset_data["asset_type"],
                        missions_capable=[AirMissionType(m) for m in asset_data["missions_capable"]],
                        sortie_count=asset_data["sortie_count"],
                        attack_power=asset_data["attack_power"],
                        defense_against_sam=asset_data["defense_against_sam"],
                    )
                    self.air_assets[asset.id] = asset
                total = force_data["air_assets"].get("total_sorties_per_turn", 0)
                self.sortie_pools[side.value] = SortiePool(
                    side=side,
                    total_sorties=total,
                    remaining_sorties=total,
                )
