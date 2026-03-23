"""Tests for SupplyEngine — Sprint 3: supply line calculation, interdiction, degradation."""
from __future__ import annotations

import pytest

from app.models.domain import (
    HexCoord, Side, Unit, UnitType, UnitSize, UnitStatus,
    TerrainHex, TerrainType,
)
from app.models.supply import SupplyLevel, SupplyStatus
from app.engine.supply_engine import SupplyEngine, SUPPLY_DISTANCE_THRESHOLD
from app.engine.game_state import GameState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_unit(
    uid: str = "u1",
    side: Side = Side.BLUE,
    unit_type: UnitType = UnitType.INFANTRY,
    pos: tuple[int, int] = (5, 5),
    strength: float = 1.0,
    morale: float = 0.8,
    attack_power: float = 10.0,
    ammo: float = 1.0,
    fuel: float = 1.0,
    status: UnitStatus = UnitStatus.ACTIVE,
) -> Unit:
    return Unit(
        id=uid, name=uid, side=side, unit_type=unit_type, size=UnitSize.BATTALION,
        position=HexCoord(q=pos[0], r=pos[1]),
        strength=strength, morale=morale, movement_points=2, max_movement_points=2,
        attack_power=attack_power, defense_power=10.0, effective_range=1,
        ammo=ammo, fuel=fuel, status=status,
    )


def _make_flat_map(width: int = 20, height: int = 20) -> dict[HexCoord, TerrainHex]:
    terrain = {}
    for q in range(width):
        for r in range(height):
            coord = HexCoord(q=q, r=r)
            terrain[coord] = TerrainHex(coord=coord, terrain_type=TerrainType.PLAIN, elevation=0)
    return terrain


def _make_game_state(
    units: list[Unit] | None = None,
    terrain: dict[HexCoord, TerrainHex] | None = None,
    supply_status: dict[str, SupplyStatus] | None = None,
    turn: int = 1,
) -> GameState:
    gs = GameState()
    gs.turn = turn
    gs.terrain = terrain or _make_flat_map()
    for u in (units or []):
        gs.units[u.id] = u
    gs.supply_status = supply_status or {}
    return gs


# ---------------------------------------------------------------------------
# HQ always FULL
# ---------------------------------------------------------------------------

class TestHQAlwaysFull:
    def test_hq_unit_is_always_full(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(5, 5))
        gs = _make_game_state(units=[hq])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["hq1"].level == SupplyLevel.FULL

    def test_hq_unit_has_zero_turns_without_supply(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(5, 5))
        gs = _make_game_state(units=[hq])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["hq1"].turns_without_supply == 0

    def test_hq_unit_has_zero_route_length(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(5, 5))
        gs = _make_game_state(units=[hq])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["hq1"].supply_route_length == 0

    def test_multiple_hq_units_all_full(self):
        hq1 = _make_unit("hq1", unit_type=UnitType.HQ, pos=(2, 2))
        hq2 = _make_unit("hq2", side=Side.RED, unit_type=UnitType.HQ, pos=(10, 10))
        gs = _make_game_state(units=[hq1, hq2])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["hq1"].level == SupplyLevel.FULL
        assert result["hq2"].level == SupplyLevel.FULL


# ---------------------------------------------------------------------------
# Unit connected to HQ -> FULL
# ---------------------------------------------------------------------------

class TestConnectedToHQ:
    def test_unit_adjacent_to_hq_is_full(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(5, 5))
        unit = _make_unit("u1", pos=(5, 6))
        gs = _make_game_state(units=[hq, unit])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["u1"].level == SupplyLevel.FULL

    def test_unit_close_to_hq_is_full(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(0, 0))
        unit = _make_unit("u1", pos=(4, 0))
        gs = _make_game_state(units=[hq, unit])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["u1"].level == SupplyLevel.FULL
        assert result["u1"].turns_without_supply == 0

    def test_unit_connected_route_length_recorded(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(0, 0))
        unit = _make_unit("u1", pos=(3, 0))
        gs = _make_game_state(units=[hq, unit])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["u1"].supply_route_length == 3


# ---------------------------------------------------------------------------
# No path to HQ -> CUT_OFF
# ---------------------------------------------------------------------------

class TestNoPathToHQ:
    def test_unit_with_no_hq_is_cut_off(self):
        unit = _make_unit("u1", pos=(5, 5))
        gs = _make_game_state(units=[unit])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["u1"].level == SupplyLevel.CUT_OFF

    def test_unit_enemy_hq_does_not_supply(self):
        # RED HQ should not supply BLUE unit
        red_hq = _make_unit("hq_red", side=Side.RED, unit_type=UnitType.HQ, pos=(5, 6))
        blue_unit = _make_unit("u1", side=Side.BLUE, pos=(5, 5))
        gs = _make_game_state(units=[red_hq, blue_unit])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["u1"].level == SupplyLevel.CUT_OFF

    def test_cut_off_increments_turns_without_supply(self):
        unit = _make_unit("u1", pos=(5, 5))
        prev_status = SupplyStatus(unit_id="u1", level=SupplyLevel.CUT_OFF, turns_without_supply=2)
        gs = _make_game_state(units=[unit], supply_status={"u1": prev_status})
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["u1"].turns_without_supply == 3

    def test_destroyed_hq_does_not_supply(self):
        destroyed_hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(5, 6), status=UnitStatus.DESTROYED)
        unit = _make_unit("u1", pos=(5, 5))
        gs = _make_game_state(units=[destroyed_hq, unit])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["u1"].level == SupplyLevel.CUT_OFF


# ---------------------------------------------------------------------------
# Long path (>8 hexes) -> REDUCED
# ---------------------------------------------------------------------------

class TestLongPathReduced:
    def test_path_over_threshold_is_reduced(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(0, 0))
        # Place unit 10 hexes away (q=10 is distance 10 from q=0)
        unit = _make_unit("u1", pos=(10, 0))
        gs = _make_game_state(units=[hq, unit])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["u1"].level == SupplyLevel.REDUCED

    def test_path_exactly_at_threshold_is_full(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(0, 0))
        unit = _make_unit("u1", pos=(8, 0))
        gs = _make_game_state(units=[hq, unit])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["u1"].level == SupplyLevel.FULL

    def test_path_one_over_threshold_is_reduced(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(0, 0))
        unit = _make_unit("u1", pos=(9, 0))
        gs = _make_game_state(units=[hq, unit])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["u1"].level == SupplyLevel.REDUCED


# ---------------------------------------------------------------------------
# Enemy on supply path -> CUT_OFF (interdiction)
# ---------------------------------------------------------------------------

class TestInterdiction:
    def test_enemy_on_path_causes_cut_off(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(0, 0))
        unit = _make_unit("u1", pos=(4, 0))
        # Enemy sits between unit and HQ
        enemy = _make_unit("e1", side=Side.RED, pos=(2, 0))
        gs = _make_game_state(units=[hq, unit, enemy])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["u1"].level == SupplyLevel.CUT_OFF

    def test_check_interdiction_returns_hex(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(0, 0))
        unit = _make_unit("u1", pos=(4, 0))
        enemy = _make_unit("e1", side=Side.RED, pos=(2, 0))
        gs = _make_game_state(units=[hq, unit, enemy])
        engine = SupplyEngine()
        path = engine.trace_supply_path(unit, gs)
        assert path is not None
        interdiction = engine.check_interdiction(path, gs, Side.BLUE)
        assert interdiction == HexCoord(q=2, r=0)

    def test_check_interdiction_no_enemy_returns_none(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(0, 0))
        unit = _make_unit("u1", pos=(4, 0))
        gs = _make_game_state(units=[hq, unit])
        engine = SupplyEngine()
        path = engine.trace_supply_path(unit, gs)
        assert path is not None
        result = engine.check_interdiction(path, gs, Side.BLUE)
        assert result is None

    def test_destroyed_enemy_does_not_interdict(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(0, 0))
        unit = _make_unit("u1", pos=(4, 0))
        dead_enemy = _make_unit("e1", side=Side.RED, pos=(2, 0), status=UnitStatus.DESTROYED)
        gs = _make_game_state(units=[hq, unit, dead_enemy])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["u1"].level == SupplyLevel.FULL


# ---------------------------------------------------------------------------
# apply_supply_effects
# ---------------------------------------------------------------------------

class TestApplySupplyEffects:
    def test_full_supply_no_effect(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(5, 5))
        unit = _make_unit("u1", pos=(5, 6), attack_power=10.0, ammo=1.0, fuel=1.0)
        gs = _make_game_state(units=[hq, unit])
        engine = SupplyEngine()
        gs.supply_status = engine.calculate_supply_status(gs)
        effects = engine.apply_supply_effects(gs)
        # No effects for FULL supply
        assert not any(e["unit_id"] == "u1" for e in effects)
        assert gs.units["u1"].attack_power == 10.0

    def test_reduced_supply_attack_power_multiplier(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(0, 0))
        unit = _make_unit("u1", pos=(10, 0), attack_power=10.0)
        gs = _make_game_state(units=[hq, unit])
        engine = SupplyEngine()
        gs.supply_status = engine.calculate_supply_status(gs)
        assert gs.supply_status["u1"].level == SupplyLevel.REDUCED
        engine.apply_supply_effects(gs)
        assert abs(gs.units["u1"].attack_power - 8.0) < 0.001

    def test_cut_off_attack_power_halved(self):
        unit = _make_unit("u1", pos=(5, 5), attack_power=10.0)
        cut_off_status = SupplyStatus(unit_id="u1", level=SupplyLevel.CUT_OFF, turns_without_supply=1)
        gs = _make_game_state(units=[unit], supply_status={"u1": cut_off_status})
        engine = SupplyEngine()
        engine.apply_supply_effects(gs)
        assert abs(gs.units["u1"].attack_power - 5.0) < 0.001

    def test_cut_off_ammo_drain(self):
        unit = _make_unit("u1", pos=(5, 5), ammo=0.5)
        cut_off_status = SupplyStatus(unit_id="u1", level=SupplyLevel.CUT_OFF, turns_without_supply=1)
        gs = _make_game_state(units=[unit], supply_status={"u1": cut_off_status})
        engine = SupplyEngine()
        engine.apply_supply_effects(gs)
        assert abs(gs.units["u1"].ammo - 0.4) < 0.001

    def test_cut_off_fuel_drain(self):
        unit = _make_unit("u1", pos=(5, 5), fuel=0.5)
        cut_off_status = SupplyStatus(unit_id="u1", level=SupplyLevel.CUT_OFF, turns_without_supply=1)
        gs = _make_game_state(units=[unit], supply_status={"u1": cut_off_status})
        engine = SupplyEngine()
        engine.apply_supply_effects(gs)
        assert abs(gs.units["u1"].fuel - 0.4) < 0.001

    def test_cut_off_3_turns_morale_drain(self):
        unit = _make_unit("u1", pos=(5, 5), morale=0.8)
        cut_off_status = SupplyStatus(unit_id="u1", level=SupplyLevel.CUT_OFF, turns_without_supply=3)
        gs = _make_game_state(units=[unit], supply_status={"u1": cut_off_status})
        engine = SupplyEngine()
        engine.apply_supply_effects(gs)
        assert abs(gs.units["u1"].morale - 0.7) < 0.001

    def test_cut_off_2_turns_no_morale_drain(self):
        unit = _make_unit("u1", pos=(5, 5), morale=0.8)
        cut_off_status = SupplyStatus(unit_id="u1", level=SupplyLevel.CUT_OFF, turns_without_supply=2)
        gs = _make_game_state(units=[unit], supply_status={"u1": cut_off_status})
        engine = SupplyEngine()
        engine.apply_supply_effects(gs)
        assert abs(gs.units["u1"].morale - 0.8) < 0.001

    def test_clamping_ammo_does_not_go_below_zero(self):
        unit = _make_unit("u1", pos=(5, 5), ammo=0.05)
        cut_off_status = SupplyStatus(unit_id="u1", level=SupplyLevel.CUT_OFF, turns_without_supply=1)
        gs = _make_game_state(units=[unit], supply_status={"u1": cut_off_status})
        engine = SupplyEngine()
        engine.apply_supply_effects(gs)
        assert gs.units["u1"].ammo == 0.0

    def test_clamping_fuel_does_not_go_below_zero(self):
        unit = _make_unit("u1", pos=(5, 5), fuel=0.05)
        cut_off_status = SupplyStatus(unit_id="u1", level=SupplyLevel.CUT_OFF, turns_without_supply=1)
        gs = _make_game_state(units=[unit], supply_status={"u1": cut_off_status})
        engine = SupplyEngine()
        engine.apply_supply_effects(gs)
        assert gs.units["u1"].fuel == 0.0

    def test_clamping_morale_does_not_go_below_zero(self):
        unit = _make_unit("u1", pos=(5, 5), morale=0.05)
        cut_off_status = SupplyStatus(unit_id="u1", level=SupplyLevel.CUT_OFF, turns_without_supply=3)
        gs = _make_game_state(units=[unit], supply_status={"u1": cut_off_status})
        engine = SupplyEngine()
        engine.apply_supply_effects(gs)
        assert gs.units["u1"].morale == 0.0

    def test_effects_returns_list_of_dicts(self):
        unit = _make_unit("u1", pos=(5, 5))
        cut_off_status = SupplyStatus(unit_id="u1", level=SupplyLevel.CUT_OFF, turns_without_supply=1)
        gs = _make_game_state(units=[unit], supply_status={"u1": cut_off_status})
        engine = SupplyEngine()
        effects = engine.apply_supply_effects(gs)
        assert isinstance(effects, list)
        assert len(effects) == 1
        assert effects[0]["unit_id"] == "u1"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_game_state_returns_empty_dict(self):
        gs = _make_game_state()
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result == {}

    def test_destroyed_units_skipped(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(5, 5))
        dead_unit = _make_unit("u1", pos=(5, 6), status=UnitStatus.DESTROYED)
        gs = _make_game_state(units=[hq, dead_unit])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert "u1" not in result

    def test_routed_units_skipped(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(5, 5))
        routed_unit = _make_unit("u1", pos=(5, 6), status=UnitStatus.ROUTED)
        gs = _make_game_state(units=[hq, routed_unit])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert "u1" not in result

    def test_unit_at_same_position_as_hq_is_full(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(5, 5))
        unit = _make_unit("u1", pos=(5, 5))
        gs = _make_game_state(units=[hq, unit])
        engine = SupplyEngine()
        result = engine.calculate_supply_status(gs)
        assert result["u1"].level == SupplyLevel.FULL

    def test_apply_effects_empty_supply_status(self):
        unit = _make_unit("u1", pos=(5, 5))
        gs = _make_game_state(units=[unit])
        engine = SupplyEngine()
        effects = engine.apply_supply_effects(gs)
        assert effects == []


# ---------------------------------------------------------------------------
# Snapshot serialization
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_supply_status_in_snapshot(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(5, 5))
        unit = _make_unit("u1", pos=(5, 6))
        gs = _make_game_state(units=[hq, unit])
        engine = SupplyEngine()
        gs.supply_status = engine.calculate_supply_status(gs)
        snap = gs.to_snapshot()
        assert "supply_status" in snap
        assert "u1" in snap["supply_status"]
        assert snap["supply_status"]["u1"]["level"] == "FULL"

    def test_snapshot_roundtrip_with_supply_status(self):
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(0, 0))
        unit = _make_unit("u1", pos=(10, 0))  # REDUCED (10 hexes > threshold of 8)
        gs = _make_game_state(units=[hq, unit])
        engine = SupplyEngine()
        gs.supply_status = engine.calculate_supply_status(gs)
        snap = gs.to_snapshot()
        restored = GameState.from_snapshot(snap)
        assert "u1" in restored.supply_status
        assert restored.supply_status["u1"].level == SupplyLevel.REDUCED

    def test_backward_compat_snapshot_without_supply_status(self):
        """Snapshots missing supply_status key default to empty dict."""
        hq = _make_unit("hq1", unit_type=UnitType.HQ, pos=(5, 5))
        unit = _make_unit("u1", pos=(5, 6))
        gs = _make_game_state(units=[hq, unit])
        snap = gs.to_snapshot()
        # Simulate old snapshot without supply_status key
        snap.pop("supply_status", None)
        restored = GameState.from_snapshot(snap)
        assert restored.supply_status == {}
