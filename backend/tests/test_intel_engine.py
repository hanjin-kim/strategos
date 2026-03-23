"""Tests for IntelEngine — Sprint 1: visibility, detection, intel degradation."""
from __future__ import annotations

import pytest

from app.models.domain import (
    HexCoord, Side, Unit, UnitType, UnitSize, UnitStatus,
    TerrainHex, TerrainType, Commander, Force,
)
from app.models.intel import IntelLevel, IntelReport, VISIBILITY_TABLE
from app.engine.intel_engine import IntelEngine
from app.engine.game_state import GameState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_unit(
    uid: str = "u1",
    side: Side = Side.BLUE,
    unit_type: UnitType = UnitType.INFANTRY,
    pos: tuple[int, int] = (5, 5),
    strength: float = 1.0,
    status: UnitStatus = UnitStatus.ACTIVE,
) -> Unit:
    return Unit(
        id=uid, name=uid, side=side, unit_type=unit_type, size=UnitSize.BATTALION,
        position=HexCoord(q=pos[0], r=pos[1]),
        strength=strength, morale=0.8, movement_points=2, max_movement_points=2,
        attack_power=10.0, defense_power=10.0, effective_range=1,
        ammo=1.0, fuel=1.0, status=status,
    )


def _make_terrain(
    coords: list[tuple[int, int]],
    terrain_type: TerrainType = TerrainType.PLAIN,
    elevation: int = 0,
) -> dict[HexCoord, TerrainHex]:
    result = {}
    for q, r in coords:
        coord = HexCoord(q=q, r=r)
        result[coord] = TerrainHex(
            coord=coord, terrain_type=terrain_type, elevation=elevation,
        )
    return result


def _make_flat_map(width: int = 15, height: int = 12) -> dict[HexCoord, TerrainHex]:
    """Create a flat PLAIN terrain map."""
    terrain = {}
    for q in range(width):
        for r in range(height):
            coord = HexCoord(q=q, r=r)
            terrain[coord] = TerrainHex(coord=coord, terrain_type=TerrainType.PLAIN, elevation=0)
    return terrain


def _make_game_state(
    blue_units: list[Unit] | None = None,
    red_units: list[Unit] | None = None,
    terrain: dict[HexCoord, TerrainHex] | None = None,
    turn: int = 1,
) -> GameState:
    gs = GameState()
    gs.turn = turn
    gs.terrain = terrain or _make_flat_map()
    for u in (blue_units or []):
        gs.units[u.id] = u
    for u in (red_units or []):
        gs.units[u.id] = u
    gs.intel_reports = {}
    return gs


# ---------------------------------------------------------------------------
# Visibility radius tests
# ---------------------------------------------------------------------------

class TestVisibilityRadius:
    def test_infantry_base_radius(self):
        engine = IntelEngine()
        unit = _make_unit(unit_type=UnitType.INFANTRY)
        assert engine.get_visibility_radius(unit) == 2

    def test_recon_extended_radius(self):
        engine = IntelEngine()
        unit = _make_unit(unit_type=UnitType.RECON)
        assert engine.get_visibility_radius(unit) == 4

    def test_artillery_short_radius(self):
        engine = IntelEngine()
        unit = _make_unit(unit_type=UnitType.ARTILLERY)
        assert engine.get_visibility_radius(unit) == 1

    def test_hq_radius(self):
        engine = IntelEngine()
        unit = _make_unit(unit_type=UnitType.HQ)
        assert engine.get_visibility_radius(unit) == 3

    def test_elevation_bonus(self):
        engine = IntelEngine()
        unit = _make_unit(unit_type=UnitType.INFANTRY)
        assert engine.get_visibility_radius(unit, observer_elevation=400) == 3

    def test_no_elevation_bonus_below_threshold(self):
        engine = IntelEngine()
        unit = _make_unit(unit_type=UnitType.INFANTRY)
        assert engine.get_visibility_radius(unit, observer_elevation=200) == 2

    def test_custom_visibility_table(self):
        engine = IntelEngine(visibility_table={"INFANTRY": 5})
        unit = _make_unit(unit_type=UnitType.INFANTRY)
        assert engine.get_visibility_radius(unit) == 5

    def test_unknown_type_defaults_to_2(self):
        engine = IntelEngine(visibility_table={})
        unit = _make_unit(unit_type=UnitType.INFANTRY)
        assert engine.get_visibility_radius(unit) == 2


# ---------------------------------------------------------------------------
# Visibility calculation tests
# ---------------------------------------------------------------------------

class TestVisibilityCalculation:
    def test_basic_visibility_set(self):
        engine = IntelEngine()
        unit = _make_unit(pos=(5, 5))
        terrain = _make_flat_map()
        visible = engine.calculate_visibility(unit, terrain)
        assert HexCoord(q=5, r=5) in visible  # own position
        assert HexCoord(q=6, r=5) in visible  # adjacent
        assert HexCoord(q=7, r=5) in visible  # 2 hexes away

    def test_recon_sees_further(self):
        engine = IntelEngine()
        infantry = _make_unit(uid="inf", unit_type=UnitType.INFANTRY, pos=(5, 5))
        recon = _make_unit(uid="rec", unit_type=UnitType.RECON, pos=(5, 5))
        terrain = _make_flat_map()
        inf_vis = engine.calculate_visibility(infantry, terrain)
        rec_vis = engine.calculate_visibility(recon, terrain)
        assert len(rec_vis) > len(inf_vis)

    def test_off_map_hexes_excluded(self):
        engine = IntelEngine()
        unit = _make_unit(pos=(0, 0))
        terrain = _make_flat_map(width=3, height=3)
        visible = engine.calculate_visibility(unit, terrain)
        assert HexCoord(q=-1, r=0) not in visible  # off map

    def test_elevation_extends_visibility(self):
        engine = IntelEngine()
        unit = _make_unit(pos=(5, 5))
        terrain = _make_flat_map()
        terrain[HexCoord(q=5, r=5)] = TerrainHex(
            coord=HexCoord(q=5, r=5), terrain_type=TerrainType.MOUNTAIN, elevation=400,
        )
        visible = engine.calculate_visibility(unit, terrain)
        # Should see radius 3 (2 base + 1 elevation bonus)
        assert HexCoord(q=8, r=5) in visible

    def test_side_visibility_union(self):
        engine = IntelEngine()
        u1 = _make_unit(uid="u1", pos=(2, 2))
        u2 = _make_unit(uid="u2", pos=(8, 8))
        terrain = _make_flat_map()
        combined = engine.calculate_side_visibility([u1, u2], terrain)
        assert HexCoord(q=2, r=2) in combined
        assert HexCoord(q=8, r=8) in combined

    def test_destroyed_units_dont_see(self):
        engine = IntelEngine()
        u1 = _make_unit(uid="u1", pos=(5, 5), status=UnitStatus.DESTROYED)
        terrain = _make_flat_map()
        visible = engine.calculate_side_visibility([u1], terrain)
        assert len(visible) == 0

    def test_routed_units_dont_see(self):
        engine = IntelEngine()
        u1 = _make_unit(uid="u1", pos=(5, 5), status=UnitStatus.ROUTED)
        terrain = _make_flat_map()
        visible = engine.calculate_side_visibility([u1], terrain)
        assert len(visible) == 0


# ---------------------------------------------------------------------------
# Forest concealment tests
# ---------------------------------------------------------------------------

class TestForestConcealment:
    def test_forest_hides_unit(self):
        engine = IntelEngine()
        terrain = _make_flat_map()
        forest_coord = HexCoord(q=7, r=5)
        terrain[forest_coord] = TerrainHex(
            coord=forest_coord, terrain_type=TerrainType.FOREST, elevation=0,
        )
        assert engine.is_hidden_by_terrain(forest_coord, terrain)

    def test_plain_does_not_hide(self):
        engine = IntelEngine()
        terrain = _make_flat_map()
        assert not engine.is_hidden_by_terrain(HexCoord(q=5, r=5), terrain)

    def test_detect_forest_unit_adjacent(self):
        engine = IntelEngine()
        observer = _make_unit(uid="obs", pos=(6, 5))
        target = _make_unit(uid="tgt", side=Side.RED, pos=(7, 5))
        terrain = _make_flat_map()
        terrain[HexCoord(q=7, r=5)] = TerrainHex(
            coord=HexCoord(q=7, r=5), terrain_type=TerrainType.FOREST,
        )
        assert engine.detect_unit(observer, target, terrain)

    def test_no_detect_forest_unit_far(self):
        engine = IntelEngine()
        observer = _make_unit(uid="obs", pos=(5, 5))
        target = _make_unit(uid="tgt", side=Side.RED, pos=(7, 5))
        terrain = _make_flat_map()
        terrain[HexCoord(q=7, r=5)] = TerrainHex(
            coord=HexCoord(q=7, r=5), terrain_type=TerrainType.FOREST,
        )
        # Distance is 2 — beyond adjacency for forest
        assert not engine.detect_unit(observer, target, terrain)


# ---------------------------------------------------------------------------
# Intel update tests
# ---------------------------------------------------------------------------

class TestUpdateIntel:
    def test_confirmed_intel_for_visible_enemy(self):
        engine = IntelEngine()
        blue = _make_unit(uid="b1", side=Side.BLUE, pos=(5, 5))
        red = _make_unit(uid="r1", side=Side.RED, pos=(6, 5), strength=0.9)
        gs = _make_game_state(blue_units=[blue], red_units=[red], turn=3)
        reports = engine.update_intel(gs, Side.BLUE)
        assert "r1" in reports
        assert reports["r1"].confidence == IntelLevel.CONFIRMED
        assert reports["r1"].reported_strength == 0.9
        assert reports["r1"].last_seen_turn == 3

    def test_no_intel_for_far_enemy(self):
        engine = IntelEngine()
        blue = _make_unit(uid="b1", side=Side.BLUE, pos=(0, 0))
        red = _make_unit(uid="r1", side=Side.RED, pos=(10, 10))
        gs = _make_game_state(blue_units=[blue], red_units=[red])
        reports = engine.update_intel(gs, Side.BLUE)
        assert "r1" not in reports

    def test_preserves_stale_reports(self):
        engine = IntelEngine()
        blue = _make_unit(uid="b1", side=Side.BLUE, pos=(0, 0))
        red = _make_unit(uid="r1", side=Side.RED, pos=(10, 10))
        gs = _make_game_state(blue_units=[blue], red_units=[red], turn=5)
        # Pre-seed a stale report
        old_report = IntelReport(
            unit_id="r1", last_seen_turn=3,
            last_known_position=HexCoord(q=9, r=9),
            confidence=IntelLevel.ESTIMATED,
            reported_strength=0.8, reported_type="INFANTRY",
        )
        gs.intel_reports = {Side.BLUE.value: {"r1": old_report}}
        reports = engine.update_intel(gs, Side.BLUE)
        assert "r1" in reports
        assert reports["r1"].last_seen_turn == 3  # preserved old

    def test_destroyed_enemy_excluded(self):
        engine = IntelEngine()
        blue = _make_unit(uid="b1", side=Side.BLUE, pos=(5, 5))
        red = _make_unit(uid="r1", side=Side.RED, pos=(6, 5), status=UnitStatus.DESTROYED)
        gs = _make_game_state(blue_units=[blue], red_units=[red])
        reports = engine.update_intel(gs, Side.BLUE)
        assert "r1" not in reports

    def test_both_sides_independent(self):
        engine = IntelEngine()
        blue = _make_unit(uid="b1", side=Side.BLUE, pos=(5, 5))
        red = _make_unit(uid="r1", side=Side.RED, pos=(6, 5))
        gs = _make_game_state(blue_units=[blue], red_units=[red])
        blue_reports = engine.update_intel(gs, Side.BLUE)
        red_reports = engine.update_intel(gs, Side.RED)
        assert "r1" in blue_reports
        assert "b1" in red_reports

    def test_multiple_own_units_detect(self):
        engine = IntelEngine()
        b1 = _make_unit(uid="b1", side=Side.BLUE, pos=(5, 5))
        b2 = _make_unit(uid="b2", side=Side.BLUE, pos=(7, 5))
        red = _make_unit(uid="r1", side=Side.RED, pos=(6, 5))
        gs = _make_game_state(blue_units=[b1, b2], red_units=[red])
        reports = engine.update_intel(gs, Side.BLUE)
        assert "r1" in reports
        assert reports["r1"].confidence == IntelLevel.CONFIRMED


# ---------------------------------------------------------------------------
# Intel degradation tests
# ---------------------------------------------------------------------------

class TestDegradeIntel:
    def test_confirmed_stays_at_turn_0(self):
        engine = IntelEngine()
        reports = {
            "r1": IntelReport(
                unit_id="r1", last_seen_turn=5,
                last_known_position=HexCoord(q=6, r=5),
                confidence=IntelLevel.CONFIRMED,
                reported_strength=1.0, reported_type="INFANTRY",
            ),
        }
        result = engine.degrade_intel(reports, current_turn=5)
        assert result["r1"].confidence == IntelLevel.CONFIRMED

    def test_degrades_to_estimated_after_1_turn(self):
        engine = IntelEngine()
        reports = {
            "r1": IntelReport(
                unit_id="r1", last_seen_turn=3,
                last_known_position=HexCoord(q=6, r=5),
                confidence=IntelLevel.CONFIRMED,
                reported_strength=1.0, reported_type="INFANTRY",
            ),
        }
        result = engine.degrade_intel(reports, current_turn=4)
        assert result["r1"].confidence == IntelLevel.ESTIMATED

    def test_stays_estimated_at_2_turns(self):
        engine = IntelEngine()
        reports = {
            "r1": IntelReport(
                unit_id="r1", last_seen_turn=3,
                last_known_position=HexCoord(q=6, r=5),
                confidence=IntelLevel.ESTIMATED,
                reported_strength=1.0, reported_type="INFANTRY",
            ),
        }
        result = engine.degrade_intel(reports, current_turn=5)
        assert result["r1"].confidence == IntelLevel.ESTIMATED

    def test_degrades_to_unknown_after_3_turns(self):
        engine = IntelEngine()
        reports = {
            "r1": IntelReport(
                unit_id="r1", last_seen_turn=1,
                last_known_position=HexCoord(q=6, r=5),
                confidence=IntelLevel.ESTIMATED,
                reported_strength=1.0, reported_type="INFANTRY",
            ),
        }
        result = engine.degrade_intel(reports, current_turn=4)
        assert result["r1"].confidence == IntelLevel.UNKNOWN

    def test_empty_reports(self):
        engine = IntelEngine()
        result = engine.degrade_intel({}, current_turn=5)
        assert result == {}


# ---------------------------------------------------------------------------
# Context filtering tests
# ---------------------------------------------------------------------------

class TestFilterContext:
    def test_confirmed_enemy_full_info(self):
        engine = IntelEngine()
        blue = _make_unit(uid="b1", side=Side.BLUE, pos=(5, 5))
        red = _make_unit(uid="r1", side=Side.RED, pos=(6, 5), strength=0.7)
        gs = _make_game_state(blue_units=[blue], red_units=[red], turn=1)
        gs.intel_reports = {
            Side.BLUE.value: {
                "r1": IntelReport(
                    unit_id="r1", last_seen_turn=1,
                    last_known_position=HexCoord(q=6, r=5),
                    confidence=IntelLevel.CONFIRMED,
                    reported_strength=0.7, reported_type="INFANTRY",
                ),
            },
        }
        cmd = Commander(id="cmd1", name="Cmd", side=Side.BLUE, rank="Battalion", unit_id="b1")
        ctx = engine.filter_context_for_agent(gs, cmd)
        assert len(ctx["known_enemy"]) == 1
        enemy = ctx["known_enemy"][0]
        assert isinstance(enemy, Unit)
        assert enemy.id == "r1"

    def test_estimated_enemy_partial_info(self):
        engine = IntelEngine()
        blue = _make_unit(uid="b1", side=Side.BLUE, pos=(5, 5))
        red = _make_unit(uid="r1", side=Side.RED, pos=(10, 10))
        gs = _make_game_state(blue_units=[blue], red_units=[red], turn=5)
        gs.intel_reports = {
            Side.BLUE.value: {
                "r1": IntelReport(
                    unit_id="r1", last_seen_turn=4,
                    last_known_position=HexCoord(q=9, r=9),
                    confidence=IntelLevel.ESTIMATED,
                    reported_strength=0.8, reported_type="INFANTRY",
                ),
            },
        }
        cmd = Commander(id="cmd1", name="Cmd", side=Side.BLUE, rank="Battalion", unit_id="b1")
        ctx = engine.filter_context_for_agent(gs, cmd)
        assert len(ctx["known_enemy"]) == 1
        enemy = ctx["known_enemy"][0]
        assert isinstance(enemy, dict)
        assert enemy["confidence"] == "ESTIMATED"

    def test_unknown_enemy_not_in_context(self):
        engine = IntelEngine()
        blue = _make_unit(uid="b1", side=Side.BLUE, pos=(5, 5))
        gs = _make_game_state(blue_units=[blue], turn=5)
        gs.intel_reports = {
            Side.BLUE.value: {
                "r1": IntelReport(
                    unit_id="r1", last_seen_turn=1,
                    last_known_position=HexCoord(q=9, r=9),
                    confidence=IntelLevel.UNKNOWN,
                    reported_strength=0.8, reported_type="INFANTRY",
                ),
            },
        }
        cmd = Commander(id="cmd1", name="Cmd", side=Side.BLUE, rank="Battalion", unit_id="b1")
        ctx = engine.filter_context_for_agent(gs, cmd)
        assert len(ctx["known_enemy"]) == 0

    def test_no_intel_reports_returns_empty(self):
        engine = IntelEngine()
        blue = _make_unit(uid="b1", side=Side.BLUE, pos=(5, 5))
        gs = _make_game_state(blue_units=[blue])
        cmd = Commander(id="cmd1", name="Cmd", side=Side.BLUE, rank="Battalion", unit_id="b1")
        ctx = engine.filter_context_for_agent(gs, cmd)
        assert len(ctx["known_enemy"]) == 0
        assert len(ctx["own_units"]) == 1


# ---------------------------------------------------------------------------
# Snapshot serialization tests
# ---------------------------------------------------------------------------

class TestSnapshotSerialization:
    def test_snapshot_includes_intel(self):
        gs = _make_game_state(turn=3)
        gs.intel_reports = {
            "BLUE": {
                "r1": IntelReport(
                    unit_id="r1", last_seen_turn=3,
                    last_known_position=HexCoord(q=6, r=5),
                    confidence=IntelLevel.CONFIRMED,
                    reported_strength=0.9, reported_type="INFANTRY",
                ),
            },
        }
        snap = gs.to_snapshot()
        assert "intel_reports" in snap
        assert "BLUE" in snap["intel_reports"]
        assert "r1" in snap["intel_reports"]["BLUE"]

    def test_snapshot_roundtrip(self):
        gs = _make_game_state(turn=3)
        gs.intel_reports = {
            "BLUE": {
                "r1": IntelReport(
                    unit_id="r1", last_seen_turn=3,
                    last_known_position=HexCoord(q=6, r=5),
                    confidence=IntelLevel.CONFIRMED,
                    reported_strength=0.9, reported_type="INFANTRY",
                ),
            },
        }
        snap = gs.to_snapshot()
        restored = GameState.from_snapshot(snap)
        assert "BLUE" in restored.intel_reports
        report = restored.intel_reports["BLUE"]["r1"]
        assert report.confidence == IntelLevel.CONFIRMED
        assert report.reported_strength == 0.9

    def test_snapshot_empty_intel(self):
        gs = _make_game_state()
        snap = gs.to_snapshot()
        restored = GameState.from_snapshot(snap)
        assert restored.intel_reports == {}


# ---------------------------------------------------------------------------
# Regression: existing tests should not break
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_game_state_init_has_intel_reports(self):
        gs = GameState()
        assert hasattr(gs, "intel_reports")
        assert gs.intel_reports == {}

    def test_intel_engine_none_safe(self):
        """IntelEngine is optional — not having one should not affect GameState."""
        gs = GameState()
        assert gs.intel_reports == {}
        snap = gs.to_snapshot()
        assert snap["intel_reports"] == {}
