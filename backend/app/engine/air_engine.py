from __future__ import annotations

import random
from app.models.air import AirMission, AirMissionType, SortiePool, AirAsset
from app.models.domain import HexCoord, Side, UnitType, UnitStatus
from app.utils.hex_grid import hex_distance

# Priority order for mission type allocation
_MISSION_PRIORITY: dict[AirMissionType, int] = {
    AirMissionType.AIR_SUPERIORITY: 0,
    AirMissionType.CAS: 1,
    AirMissionType.INTERDICTION: 2,
    AirMissionType.RECON: 3,
}


class AirEngine:
    """Air mission resolution: sortie allocation, air combat, CAS, interdiction, recon."""

    def __init__(self, rng_seed: int | None = None):
        self.rng = random.Random(rng_seed)

    def allocate_missions(
        self,
        missions: list[AirMission],
        pool: SortiePool,
    ) -> tuple[list[AirMission], list[AirMission]]:
        """Allocate missions from sortie pool. Returns (allocated, rejected).
        Priority: AIR_SUPERIORITY > CAS > INTERDICTION > RECON.
        Reject missions that exceed remaining sorties."""
        sorted_missions = sorted(missions, key=lambda m: _MISSION_PRIORITY.get(m.mission_type, 99))
        allocated: list[AirMission] = []
        rejected: list[AirMission] = []
        remaining = pool.remaining_sorties
        for mission in sorted_missions:
            if remaining > 0:
                allocated.append(mission)
                remaining -= 1
            else:
                rejected.append(mission)
        return allocated, rejected

    def resolve_air_superiority(
        self,
        blue_missions: list[AirMission],
        red_missions: list[AirMission],
        blue_assets: dict[str, AirAsset],
        red_assets: dict[str, AirAsset],
    ) -> tuple[float, float]:
        """Resolve air superiority contest. Returns (blue_superiority, red_superiority) where each is 0.0~1.0.
        Based on total attack_power of AIR_SUPERIORITY missions per side.
        Winner gets higher value. If no missions: 0.5/0.5."""
        blue_power = sum(
            blue_assets[m.asset_id].attack_power
            for m in blue_missions
            if m.mission_type == AirMissionType.AIR_SUPERIORITY and m.asset_id in blue_assets
        )
        red_power = sum(
            red_assets[m.asset_id].attack_power
            for m in red_missions
            if m.mission_type == AirMissionType.AIR_SUPERIORITY and m.asset_id in red_assets
        )
        total = blue_power + red_power
        if total == 0.0:
            return 0.5, 0.5
        blue_sup = blue_power / total
        red_sup = red_power / total
        return blue_sup, red_sup

    def resolve_air_missions(
        self,
        missions: list[AirMission],
        game_state,
        assets: dict[str, AirAsset],
    ) -> list[AirMission]:
        """WEGO 2-pass resolution:
        Pass 1: Resolve AIR_SUPERIORITY first -> determines air_superiority values
        Pass 2: Resolve CAS/INTERDICTION/RECON with air_superiority affecting success
        Check air defense (SAM/AAA units within 2 hexes of target) for each mission.
        """
        if not missions:
            return []

        # Determine this side from the first mission (all missions share a side)
        side = missions[0].side

        # Pass 1: resolve AIR_SUPERIORITY missions
        blue_missions = [m for m in missions if m.side == Side.BLUE]
        red_missions = [m for m in missions if m.side == Side.RED]
        blue_assets_map = {aid: a for aid, a in assets.items() if a.side == Side.BLUE}
        red_assets_map = {aid: a for aid, a in assets.items() if a.side == Side.RED}

        blue_sup, red_sup = self.resolve_air_superiority(
            blue_missions, red_missions, blue_assets_map, red_assets_map
        )
        air_superiority = blue_sup if side == Side.BLUE else red_sup

        resolved: list[AirMission] = []

        for mission in missions:
            asset = assets.get(mission.asset_id)
            if asset is None:
                resolved.append(mission.model_copy(update={"result": "ABORTED"}))
                continue

            if mission.mission_type == AirMissionType.AIR_SUPERIORITY:
                # AIR_SUPERIORITY missions succeed based on winning the contest
                if air_superiority >= 0.5:
                    resolved.append(mission.model_copy(update={"result": "SUCCESS"}))
                else:
                    resolved.append(mission.model_copy(update={"result": "INTERCEPTED"}))
                continue

            # Pass 2: CAS / INTERDICTION / RECON — check air defense
            success = self.check_air_defense(mission, game_state, asset)
            if not success:
                resolved.append(mission.model_copy(update={"result": "INTERCEPTED"}))
                continue

            if mission.mission_type == AirMissionType.RECON:
                resolved.append(mission.model_copy(update={"result": "SUCCESS"}))
            elif mission.mission_type == AirMissionType.CAS:
                resolved.append(mission.model_copy(update={"result": "SUCCESS"}))
            elif mission.mission_type == AirMissionType.INTERDICTION:
                resolved.append(mission.model_copy(update={"result": "SUCCESS"}))
            else:
                resolved.append(mission.model_copy(update={"result": "SUCCESS"}))

        return resolved

    def check_air_defense(self, mission: AirMission, game_state, asset: AirAsset) -> bool:
        """Check if mission is intercepted by SAM/AAA.
        SAM (AIR_DEFENSE type) within 2 hexes: 60% intercept chance * (1 - defense_against_sam)
        Returns True if mission succeeds (not intercepted)."""
        target_hex = mission.target_hex
        if target_hex is None:
            return True

        for unit in game_state.units.values():
            if unit.status in (UnitStatus.DESTROYED, UnitStatus.ROUTED):
                continue
            if unit.unit_type not in (UnitType.AIR_DEFENSE, UnitType.SAM, UnitType.AAA):
                continue
            dist = hex_distance(unit.position, target_hex)
            if dist <= 2:
                intercept_chance = 0.6 * (1.0 - asset.defense_against_sam)
                if self.rng.random() < intercept_chance:
                    return False
        return True

    def get_cas_modifier(
        self,
        target_hex: HexCoord,
        successful_missions: list[AirMission],
    ) -> float:
        """CAS modifier for ground combat at target_hex.
        Each successful CAS at this hex adds 0.15 * air_superiority.
        Max modifier: 0.5."""
        # Determine air_superiority from the pool stored in missions; default 0.5 if unavailable
        # We use 1.0 as the air_superiority multiplier since it is baked in externally
        cas_count = sum(
            1
            for m in successful_missions
            if m.mission_type == AirMissionType.CAS
            and m.result == "SUCCESS"
            and m.target_hex == target_hex
        )
        modifier = cas_count * 0.15
        return min(modifier, 0.5)

    def apply_interdiction(self, mission: AirMission) -> dict:
        """Interdiction effect description. Does not directly modify state.
        Returns {"target_hex": ..., "effect": "movement_cost_increase"}."""
        target = None
        if mission.target_hex is not None:
            target = {"q": mission.target_hex.q, "r": mission.target_hex.r}
        return {
            "target_hex": target,
            "effect": "movement_cost_increase",
        }
