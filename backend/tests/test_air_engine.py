from __future__ import annotations

import pytest
from app.models.air import AirAsset, AirMission, AirMissionType, SortiePool
from app.models.domain import HexCoord, Side, UnitType, UnitSize, UnitStatus
from app.models.domain import Unit
from app.engine.air_engine import AirEngine
from app.engine.game_state import GameState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_asset(
    asset_id: str = "f16-1",
    side: Side = Side.BLUE,
    attack_power: float = 10.0,
    defense_against_sam: float = 0.3,
    missions_capable: list[AirMissionType] | None = None,
) -> AirAsset:
    if missions_capable is None:
        missions_capable = [AirMissionType.CAS, AirMissionType.AIR_SUPERIORITY]
    return AirAsset(
        id=asset_id,
        name="F-16",
        side=side,
        asset_type="F-16",
        missions_capable=missions_capable,
        sortie_count=2,
        attack_power=attack_power,
        defense_against_sam=defense_against_sam,
    )


def _make_mission(
    mission_id: str = "m1",
    side: Side = Side.BLUE,
    mission_type: AirMissionType = AirMissionType.CAS,
    asset_id: str = "f16-1",
    target_hex: HexCoord | None = None,
    result: str = "",
) -> AirMission:
    return AirMission(
        mission_id=mission_id,
        turn=1,
        side=side,
        mission_type=mission_type,
        asset_id=asset_id,
        target_hex=target_hex,
        result=result,
    )


def _make_pool(
    side: Side = Side.BLUE,
    total: int = 5,
    remaining: int = 5,
    air_sup: float = 0.5,
) -> SortiePool:
    return SortiePool(side=side, total_sorties=total, remaining_sorties=remaining, air_superiority=air_sup)


def _make_unit(
    unit_id: str,
    side: Side,
    unit_type: UnitType,
    position: HexCoord,
    status: UnitStatus = UnitStatus.ACTIVE,
) -> Unit:
    return Unit(
        id=unit_id,
        name=unit_id,
        side=side,
        unit_type=unit_type,
        size=UnitSize.BATTALION,
        position=position,
        strength=1.0,
        morale=0.8,
        movement_points=4,
        max_movement_points=4,
        attack_power=5.0,
        defense_power=5.0,
        effective_range=1,
        ammo=1.0,
        fuel=1.0,
        status=status,
    )


def _empty_state() -> GameState:
    return GameState()


# ---------------------------------------------------------------------------
# Sortie pool allocation
# ---------------------------------------------------------------------------

class TestSortieAllocation:
    def test_allocate_within_budget(self):
        engine = AirEngine(rng_seed=42)
        missions = [_make_mission(f"m{i}") for i in range(3)]
        pool = _make_pool(remaining=5)
        allocated, rejected = engine.allocate_missions(missions, pool)
        assert len(allocated) == 3
        assert len(rejected) == 0

    def test_allocate_exact_budget(self):
        engine = AirEngine(rng_seed=42)
        missions = [_make_mission(f"m{i}") for i in range(5)]
        pool = _make_pool(remaining=5)
        allocated, rejected = engine.allocate_missions(missions, pool)
        assert len(allocated) == 5
        assert len(rejected) == 0

    def test_allocate_exceed_budget(self):
        engine = AirEngine(rng_seed=42)
        missions = [_make_mission(f"m{i}") for i in range(7)]
        pool = _make_pool(remaining=3)
        allocated, rejected = engine.allocate_missions(missions, pool)
        assert len(allocated) == 3
        assert len(rejected) == 4

    def test_allocate_zero_sorties_rejects_all(self):
        engine = AirEngine(rng_seed=42)
        missions = [_make_mission(f"m{i}") for i in range(3)]
        pool = _make_pool(remaining=0)
        allocated, rejected = engine.allocate_missions(missions, pool)
        assert len(allocated) == 0
        assert len(rejected) == 3

    def test_allocate_empty_missions(self):
        engine = AirEngine(rng_seed=42)
        pool = _make_pool(remaining=5)
        allocated, rejected = engine.allocate_missions([], pool)
        assert allocated == []
        assert rejected == []

    def test_priority_order_air_sup_first(self):
        engine = AirEngine(rng_seed=42)
        m_recon = _make_mission("m_recon", mission_type=AirMissionType.RECON)
        m_cas = _make_mission("m_cas", mission_type=AirMissionType.CAS)
        m_airsup = _make_mission("m_airsup", mission_type=AirMissionType.AIR_SUPERIORITY)
        m_inter = _make_mission("m_inter", mission_type=AirMissionType.INTERDICTION)
        pool = _make_pool(remaining=2)
        allocated, rejected = engine.allocate_missions([m_recon, m_cas, m_airsup, m_inter], pool)
        assert len(allocated) == 2
        mission_types = {m.mission_type for m in allocated}
        assert AirMissionType.AIR_SUPERIORITY in mission_types
        assert AirMissionType.CAS in mission_types

    def test_priority_cas_before_interdiction(self):
        engine = AirEngine(rng_seed=42)
        m_inter = _make_mission("m_inter", mission_type=AirMissionType.INTERDICTION)
        m_cas = _make_mission("m_cas", mission_type=AirMissionType.CAS)
        pool = _make_pool(remaining=1)
        allocated, rejected = engine.allocate_missions([m_inter, m_cas], pool)
        assert len(allocated) == 1
        assert allocated[0].mission_type == AirMissionType.CAS

    def test_priority_interdiction_before_recon(self):
        engine = AirEngine(rng_seed=42)
        m_recon = _make_mission("m_recon", mission_type=AirMissionType.RECON)
        m_inter = _make_mission("m_inter", mission_type=AirMissionType.INTERDICTION)
        pool = _make_pool(remaining=1)
        allocated, rejected = engine.allocate_missions([m_recon, m_inter], pool)
        assert len(allocated) == 1
        assert allocated[0].mission_type == AirMissionType.INTERDICTION


# ---------------------------------------------------------------------------
# Air superiority resolution
# ---------------------------------------------------------------------------

class TestAirSuperiority:
    def test_no_missions_returns_equal(self):
        engine = AirEngine(rng_seed=42)
        blue_sup, red_sup = engine.resolve_air_superiority([], [], {}, {})
        assert blue_sup == 0.5
        assert red_sup == 0.5

    def test_blue_stronger(self):
        engine = AirEngine(rng_seed=42)
        blue_asset = _make_asset("b1", Side.BLUE, attack_power=20.0)
        red_asset = _make_asset("r1", Side.RED, attack_power=10.0)
        blue_missions = [_make_mission("bm1", Side.BLUE, AirMissionType.AIR_SUPERIORITY, "b1")]
        red_missions = [_make_mission("rm1", Side.RED, AirMissionType.AIR_SUPERIORITY, "r1")]
        blue_sup, red_sup = engine.resolve_air_superiority(
            blue_missions, red_missions, {"b1": blue_asset}, {"r1": red_asset}
        )
        assert blue_sup > red_sup
        assert abs(blue_sup + red_sup - 1.0) < 1e-9

    def test_red_stronger(self):
        engine = AirEngine(rng_seed=42)
        blue_asset = _make_asset("b1", Side.BLUE, attack_power=5.0)
        red_asset = _make_asset("r1", Side.RED, attack_power=15.0)
        blue_missions = [_make_mission("bm1", Side.BLUE, AirMissionType.AIR_SUPERIORITY, "b1")]
        red_missions = [_make_mission("rm1", Side.RED, AirMissionType.AIR_SUPERIORITY, "r1")]
        blue_sup, red_sup = engine.resolve_air_superiority(
            blue_missions, red_missions, {"b1": blue_asset}, {"r1": red_asset}
        )
        assert red_sup > blue_sup

    def test_equal_power_returns_half(self):
        engine = AirEngine(rng_seed=42)
        blue_asset = _make_asset("b1", Side.BLUE, attack_power=10.0)
        red_asset = _make_asset("r1", Side.RED, attack_power=10.0)
        blue_missions = [_make_mission("bm1", Side.BLUE, AirMissionType.AIR_SUPERIORITY, "b1")]
        red_missions = [_make_mission("rm1", Side.RED, AirMissionType.AIR_SUPERIORITY, "r1")]
        blue_sup, red_sup = engine.resolve_air_superiority(
            blue_missions, red_missions, {"b1": blue_asset}, {"r1": red_asset}
        )
        assert abs(blue_sup - 0.5) < 1e-9
        assert abs(red_sup - 0.5) < 1e-9

    def test_only_blue_missions(self):
        engine = AirEngine(rng_seed=42)
        blue_asset = _make_asset("b1", Side.BLUE, attack_power=10.0)
        blue_missions = [_make_mission("bm1", Side.BLUE, AirMissionType.AIR_SUPERIORITY, "b1")]
        blue_sup, red_sup = engine.resolve_air_superiority(
            blue_missions, [], {"b1": blue_asset}, {}
        )
        assert blue_sup == 1.0
        assert red_sup == 0.0

    def test_non_air_sup_missions_not_counted(self):
        engine = AirEngine(rng_seed=42)
        blue_asset = _make_asset("b1", Side.BLUE, attack_power=10.0)
        blue_missions = [_make_mission("bm1", Side.BLUE, AirMissionType.CAS, "b1")]
        blue_sup, red_sup = engine.resolve_air_superiority(
            blue_missions, [], {"b1": blue_asset}, {}
        )
        # CAS missions don't count, so no air superiority missions -> 0.5/0.5
        assert blue_sup == 0.5
        assert red_sup == 0.5


# ---------------------------------------------------------------------------
# CAS modifier
# ---------------------------------------------------------------------------

class TestCasModifier:
    def test_no_cas_missions(self):
        engine = AirEngine(rng_seed=42)
        target = HexCoord(q=0, r=0)
        modifier = engine.get_cas_modifier(target, [])
        assert modifier == 0.0

    def test_one_cas_success(self):
        engine = AirEngine(rng_seed=42)
        target = HexCoord(q=0, r=0)
        m = _make_mission("m1", mission_type=AirMissionType.CAS, target_hex=target, result="SUCCESS")
        modifier = engine.get_cas_modifier(target, [m])
        assert abs(modifier - 0.15) < 1e-9

    def test_two_cas_success(self):
        engine = AirEngine(rng_seed=42)
        target = HexCoord(q=0, r=0)
        m1 = _make_mission("m1", mission_type=AirMissionType.CAS, target_hex=target, result="SUCCESS")
        m2 = _make_mission("m2", mission_type=AirMissionType.CAS, target_hex=target, result="SUCCESS")
        modifier = engine.get_cas_modifier(target, [m1, m2])
        assert abs(modifier - 0.30) < 1e-9

    def test_cas_capped_at_half(self):
        engine = AirEngine(rng_seed=42)
        target = HexCoord(q=0, r=0)
        missions = [
            _make_mission(f"m{i}", mission_type=AirMissionType.CAS, target_hex=target, result="SUCCESS")
            for i in range(10)
        ]
        modifier = engine.get_cas_modifier(target, missions)
        assert modifier == 0.5

    def test_cas_wrong_hex_not_counted(self):
        engine = AirEngine(rng_seed=42)
        target = HexCoord(q=0, r=0)
        other = HexCoord(q=5, r=5)
        m = _make_mission("m1", mission_type=AirMissionType.CAS, target_hex=other, result="SUCCESS")
        modifier = engine.get_cas_modifier(target, [m])
        assert modifier == 0.0

    def test_cas_intercepted_not_counted(self):
        engine = AirEngine(rng_seed=42)
        target = HexCoord(q=0, r=0)
        m = _make_mission("m1", mission_type=AirMissionType.CAS, target_hex=target, result="INTERCEPTED")
        modifier = engine.get_cas_modifier(target, [m])
        assert modifier == 0.0


# ---------------------------------------------------------------------------
# SAM intercept / air defense
# ---------------------------------------------------------------------------

class TestAirDefense:
    def test_no_sam_mission_succeeds(self):
        engine = AirEngine(rng_seed=0)
        state = _empty_state()
        target = HexCoord(q=5, r=5)
        asset = _make_asset(defense_against_sam=0.0)
        mission = _make_mission(target_hex=target)
        # Without any SAM units, always succeeds
        results = [engine.check_air_defense(mission, state, asset) for _ in range(20)]
        assert all(results)

    def test_sam_within_2_hex_can_intercept(self):
        engine = AirEngine(rng_seed=12345)
        state = _empty_state()
        target = HexCoord(q=0, r=0)
        sam_unit = _make_unit("sam-1", Side.RED, UnitType.AIR_DEFENSE, HexCoord(q=1, r=0))
        state.units["sam-1"] = sam_unit
        asset = _make_asset(defense_against_sam=0.0)  # 60% intercept
        mission = _make_mission(target_hex=target)
        outcomes = [engine.check_air_defense(mission, state, asset) for _ in range(100)]
        # With 60% intercept, should fail some of the time
        assert False in outcomes

    def test_high_evasion_asset_rarely_intercepted(self):
        engine = AirEngine(rng_seed=42)
        state = _empty_state()
        target = HexCoord(q=0, r=0)
        sam_unit = _make_unit("sam-1", Side.RED, UnitType.AIR_DEFENSE, HexCoord(q=0, r=1))
        state.units["sam-1"] = sam_unit
        asset = _make_asset(defense_against_sam=1.0)  # 0% intercept
        mission = _make_mission(target_hex=target)
        outcomes = [engine.check_air_defense(mission, state, asset) for _ in range(20)]
        assert all(outcomes)

    def test_sam_beyond_2_hex_no_intercept(self):
        engine = AirEngine(rng_seed=42)
        state = _empty_state()
        target = HexCoord(q=0, r=0)
        sam_unit = _make_unit("sam-1", Side.RED, UnitType.AIR_DEFENSE, HexCoord(q=3, r=0))
        state.units["sam-1"] = sam_unit
        asset = _make_asset(defense_against_sam=0.0)
        mission = _make_mission(target_hex=target)
        outcomes = [engine.check_air_defense(mission, state, asset) for _ in range(20)]
        assert all(outcomes)

    def test_destroyed_sam_no_intercept(self):
        engine = AirEngine(rng_seed=42)
        state = _empty_state()
        target = HexCoord(q=0, r=0)
        sam_unit = _make_unit("sam-1", Side.RED, UnitType.AIR_DEFENSE, HexCoord(q=1, r=0), UnitStatus.DESTROYED)
        state.units["sam-1"] = sam_unit
        asset = _make_asset(defense_against_sam=0.0)
        mission = _make_mission(target_hex=target)
        outcomes = [engine.check_air_defense(mission, state, asset) for _ in range(20)]
        assert all(outcomes)

    def test_sam_unit_type_intercepts(self):
        engine = AirEngine(rng_seed=12345)
        state = _empty_state()
        target = HexCoord(q=0, r=0)
        sam_unit = _make_unit("sam-1", Side.RED, UnitType.SAM, HexCoord(q=1, r=0))
        state.units["sam-1"] = sam_unit
        asset = _make_asset(defense_against_sam=0.0)
        mission = _make_mission(target_hex=target)
        outcomes = [engine.check_air_defense(mission, state, asset) for _ in range(100)]
        assert False in outcomes

    def test_aaa_unit_type_intercepts(self):
        engine = AirEngine(rng_seed=12345)
        state = _empty_state()
        target = HexCoord(q=0, r=0)
        aaa_unit = _make_unit("aaa-1", Side.RED, UnitType.AAA, HexCoord(q=0, r=1))
        state.units["aaa-1"] = aaa_unit
        asset = _make_asset(defense_against_sam=0.0)
        mission = _make_mission(target_hex=target)
        outcomes = [engine.check_air_defense(mission, state, asset) for _ in range(100)]
        assert False in outcomes

    def test_no_target_hex_always_succeeds(self):
        engine = AirEngine(rng_seed=42)
        state = _empty_state()
        sam_unit = _make_unit("sam-1", Side.RED, UnitType.AIR_DEFENSE, HexCoord(q=0, r=0))
        state.units["sam-1"] = sam_unit
        asset = _make_asset(defense_against_sam=0.0)
        mission = _make_mission(target_hex=None)
        outcomes = [engine.check_air_defense(mission, state, asset) for _ in range(20)]
        assert all(outcomes)


# ---------------------------------------------------------------------------
# Interdiction
# ---------------------------------------------------------------------------

class TestInterdiction:
    def test_interdiction_effect_with_target(self):
        engine = AirEngine(rng_seed=42)
        target = HexCoord(q=3, r=-2)
        mission = _make_mission(mission_type=AirMissionType.INTERDICTION, target_hex=target)
        effect = engine.apply_interdiction(mission)
        assert effect["effect"] == "movement_cost_increase"
        assert effect["target_hex"] == {"q": 3, "r": -2}

    def test_interdiction_effect_without_target(self):
        engine = AirEngine(rng_seed=42)
        mission = _make_mission(mission_type=AirMissionType.INTERDICTION, target_hex=None)
        effect = engine.apply_interdiction(mission)
        assert effect["effect"] == "movement_cost_increase"
        assert effect["target_hex"] is None


# ---------------------------------------------------------------------------
# Determinism with seed
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_seed_same_results(self):
        state = _empty_state()
        target = HexCoord(q=0, r=0)
        sam_unit = _make_unit("sam-1", Side.RED, UnitType.AIR_DEFENSE, HexCoord(q=1, r=0))
        state.units["sam-1"] = sam_unit
        asset = _make_asset(defense_against_sam=0.3)
        mission = _make_mission(target_hex=target)

        engine1 = AirEngine(rng_seed=999)
        engine2 = AirEngine(rng_seed=999)

        results1 = [engine1.check_air_defense(mission, state, asset) for _ in range(20)]
        results2 = [engine2.check_air_defense(mission, state, asset) for _ in range(20)]
        assert results1 == results2

    def test_different_seeds_may_differ(self):
        state = _empty_state()
        target = HexCoord(q=0, r=0)
        sam_unit = _make_unit("sam-1", Side.RED, UnitType.AIR_DEFENSE, HexCoord(q=1, r=0))
        state.units["sam-1"] = sam_unit
        asset = _make_asset(defense_against_sam=0.3)
        mission = _make_mission(target_hex=target)

        engine1 = AirEngine(rng_seed=1)
        engine2 = AirEngine(rng_seed=2)

        results1 = [engine1.check_air_defense(mission, state, asset) for _ in range(30)]
        results2 = [engine2.check_air_defense(mission, state, asset) for _ in range(30)]
        # With different seeds and probabilistic intercept, results may differ
        # We just verify both produce valid booleans
        assert all(isinstance(r, bool) for r in results1)
        assert all(isinstance(r, bool) for r in results2)


# ---------------------------------------------------------------------------
# Full mission resolution pipeline
# ---------------------------------------------------------------------------

class TestFullResolution:
    def test_empty_missions_returns_empty(self):
        engine = AirEngine(rng_seed=42)
        state = _empty_state()
        assert engine.resolve_air_missions([], state, {}) == []

    def test_air_sup_succeeds_when_dominant(self):
        engine = AirEngine(rng_seed=42)
        state = _empty_state()
        asset = _make_asset("b1", Side.BLUE, attack_power=20.0)
        mission = _make_mission("m1", Side.BLUE, AirMissionType.AIR_SUPERIORITY, "b1")
        results = engine.resolve_air_missions([mission], state, {"b1": asset})
        assert len(results) == 1
        assert results[0].result == "SUCCESS"

    def test_cas_success_without_sam(self):
        engine = AirEngine(rng_seed=42)
        state = _empty_state()
        asset = _make_asset("b1", Side.BLUE, attack_power=10.0)
        target = HexCoord(q=3, r=3)
        mission = _make_mission("m1", Side.BLUE, AirMissionType.CAS, "b1", target_hex=target)
        results = engine.resolve_air_missions([mission], state, {"b1": asset})
        assert len(results) == 1
        assert results[0].result == "SUCCESS"

    def test_missing_asset_aborts_mission(self):
        engine = AirEngine(rng_seed=42)
        state = _empty_state()
        mission = _make_mission("m1", Side.BLUE, AirMissionType.CAS, "nonexistent")
        results = engine.resolve_air_missions([mission], state, {})
        assert len(results) == 1
        assert results[0].result == "ABORTED"

    def test_recon_succeeds_without_sam(self):
        engine = AirEngine(rng_seed=42)
        state = _empty_state()
        asset = _make_asset("b1", Side.BLUE)
        target = HexCoord(q=1, r=1)
        mission = _make_mission("m1", Side.BLUE, AirMissionType.RECON, "b1", target_hex=target)
        results = engine.resolve_air_missions([mission], state, {"b1": asset})
        assert len(results) == 1
        assert results[0].result == "SUCCESS"

    def test_interdiction_succeeds_without_sam(self):
        engine = AirEngine(rng_seed=42)
        state = _empty_state()
        asset = _make_asset("b1", Side.BLUE)
        target = HexCoord(q=2, r=-1)
        mission = _make_mission("m1", Side.BLUE, AirMissionType.INTERDICTION, "b1", target_hex=target)
        results = engine.resolve_air_missions([mission], state, {"b1": asset})
        assert len(results) == 1
        assert results[0].result == "SUCCESS"

    def test_cas_can_be_intercepted_by_sam(self):
        # Use seed that causes intercept with 60% chance and 0 evasion
        engine = AirEngine(rng_seed=12345)
        state = _empty_state()
        target = HexCoord(q=0, r=0)
        sam_unit = _make_unit("sam-1", Side.RED, UnitType.AIR_DEFENSE, HexCoord(q=1, r=0))
        state.units["sam-1"] = sam_unit
        asset = _make_asset("b1", Side.BLUE, defense_against_sam=0.0)
        # Run many missions; some should be intercepted
        intercepted = 0
        for i in range(30):
            mission = _make_mission(f"m{i}", Side.BLUE, AirMissionType.CAS, "b1", target_hex=target)
            results = engine.resolve_air_missions([mission], state, {"b1": asset})
            if results[0].result == "INTERCEPTED":
                intercepted += 1
        assert intercepted > 0
