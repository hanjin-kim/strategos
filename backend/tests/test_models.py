from __future__ import annotations
import pytest
from pydantic import ValidationError
from app.models.domain import (
    HexCoord, Side, UnitType, UnitSize, UnitStatus, TerrainType,
    Unit, Commander, TerrainHex, Force,
)
from app.models.actions import (
    ActionType, MilitaryAction, MissionType, OrderDirective,
)
from app.models.simulation import (
    TurnPhase, CombatResult, CombatOutcome, MovementResult, TurnResult,
)


# ---------------------------------------------------------------------------
# HexCoord
# ---------------------------------------------------------------------------

class TestHexCoord:
    def test_s_invariant(self):
        coord = HexCoord(q=2, r=-1)
        assert coord.s == -coord.q - coord.r
        assert coord.s == -1

    def test_s_invariant_zero(self):
        coord = HexCoord(q=0, r=0)
        assert coord.s == 0

    def test_hash_usable_as_dict_key(self):
        coord = HexCoord(q=1, r=2)
        d = {coord: "value"}
        assert d[HexCoord(q=1, r=2)] == "value"

    def test_equality(self):
        assert HexCoord(q=3, r=-1) == HexCoord(q=3, r=-1)

    def test_inequality(self):
        assert HexCoord(q=1, r=0) != HexCoord(q=0, r=1)

    def test_equality_non_hexcoord_returns_not_implemented(self):
        coord = HexCoord(q=1, r=1)
        result = coord.__eq__("not_a_coord")
        assert result is NotImplemented

    def test_hash_consistency(self):
        a = HexCoord(q=5, r=-3)
        b = HexCoord(q=5, r=-3)
        assert hash(a) == hash(b)

    def test_usable_in_set(self):
        coords = {HexCoord(q=0, r=0), HexCoord(q=1, r=0), HexCoord(q=0, r=0)}
        assert len(coords) == 2

    def test_frozen_raises_on_mutation(self):
        coord = HexCoord(q=1, r=2)
        with pytest.raises(ValidationError):
            coord.q = 99

    def test_roundtrip_serialization(self):
        coord = HexCoord(q=3, r=-5)
        json_str = coord.model_dump_json()
        restored = HexCoord.model_validate_json(json_str)
        assert restored == coord


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------

def _make_unit(**overrides) -> Unit:
    defaults = dict(
        id="unit-1",
        name="1st Battalion",
        side=Side.BLUE,
        unit_type=UnitType.INFANTRY,
        size=UnitSize.BATTALION,
        position=HexCoord(q=0, r=0),
        strength=1.0,
        morale=0.8,
        movement_points=6,
        max_movement_points=6,
        attack_power=10.0,
        defense_power=8.0,
        effective_range=1,
        ammo=1.0,
        fuel=1.0,
        status=UnitStatus.ACTIVE,
    )
    defaults.update(overrides)
    return Unit(**defaults)


class TestUnit:
    def test_valid_unit_creation(self):
        unit = _make_unit()
        assert unit.id == "unit-1"
        assert unit.side == Side.BLUE

    def test_strength_below_zero_raises(self):
        with pytest.raises(ValidationError):
            _make_unit(strength=-0.1)

    def test_strength_above_one_raises(self):
        with pytest.raises(ValidationError):
            _make_unit(strength=1.1)

    def test_morale_below_zero_raises(self):
        with pytest.raises(ValidationError):
            _make_unit(morale=-0.01)

    def test_morale_above_one_raises(self):
        with pytest.raises(ValidationError):
            _make_unit(morale=1.001)

    def test_ammo_boundary_zero(self):
        unit = _make_unit(ammo=0.0)
        assert unit.ammo == 0.0

    def test_ammo_boundary_one(self):
        unit = _make_unit(ammo=1.0)
        assert unit.ammo == 1.0

    def test_fuel_below_zero_raises(self):
        with pytest.raises(ValidationError):
            _make_unit(fuel=-0.5)

    def test_fuel_above_one_raises(self):
        with pytest.raises(ValidationError):
            _make_unit(fuel=2.0)

    def test_frozen_raises_on_mutation(self):
        unit = _make_unit()
        with pytest.raises(ValidationError):
            unit.strength = 0.5

    def test_subordinate_ids_default_empty(self):
        unit = _make_unit()
        assert unit.subordinate_ids == []

    def test_parent_unit_id_default_none(self):
        unit = _make_unit()
        assert unit.parent_unit_id is None

    def test_roundtrip_serialization(self):
        unit = _make_unit(subordinate_ids=["sub-1", "sub-2"], parent_unit_id="parent-1")
        json_str = unit.model_dump_json()
        restored = Unit.model_validate_json(json_str)
        assert restored == unit
        assert restored.subordinate_ids == ["sub-1", "sub-2"]
        assert restored.parent_unit_id == "parent-1"


# ---------------------------------------------------------------------------
# Commander
# ---------------------------------------------------------------------------

class TestCommander:
    def test_creation(self):
        cmd = Commander(id="cmd-1", name="Gen. Kim", side=Side.RED, rank="Division", unit_id="unit-1")
        assert cmd.rank == "Division"

    def test_personality_traits_default_empty(self):
        cmd = Commander(id="cmd-2", name="Gen. Park", side=Side.BLUE, rank="Theater", unit_id="unit-2")
        assert cmd.personality_traits == {}

    def test_frozen_raises_on_mutation(self):
        cmd = Commander(id="cmd-3", name="Col. Lee", side=Side.BLUE, rank="Battalion", unit_id="unit-3")
        with pytest.raises(ValidationError):
            cmd.name = "Col. Choi"

    def test_roundtrip_serialization(self):
        cmd = Commander(
            id="cmd-4", name="Gen. Test", side=Side.RED, rank="Division",
            unit_id="unit-4", personality_traits={"aggression": 0.8, "caution": 0.2}
        )
        restored = Commander.model_validate_json(cmd.model_dump_json())
        assert restored == cmd


# ---------------------------------------------------------------------------
# TerrainHex
# ---------------------------------------------------------------------------

class TestTerrainHex:
    def test_defaults(self):
        th = TerrainHex(coord=HexCoord(q=0, r=0), terrain_type=TerrainType.PLAIN)
        assert th.elevation == 0
        assert th.movement_cost == 1
        assert th.defense_modifier == 1.0
        assert th.name is None

    def test_frozen(self):
        th = TerrainHex(coord=HexCoord(q=1, r=0), terrain_type=TerrainType.MOUNTAIN)
        with pytest.raises(ValidationError):
            th.elevation = 500

    def test_roundtrip_serialization(self):
        th = TerrainHex(
            coord=HexCoord(q=2, r=-1), terrain_type=TerrainType.URBAN,
            elevation=10, movement_cost=3, defense_modifier=1.5, name="Seoul"
        )
        restored = TerrainHex.model_validate_json(th.model_dump_json())
        assert restored == th


# ---------------------------------------------------------------------------
# Force
# ---------------------------------------------------------------------------

class TestForce:
    def test_defaults(self):
        force = Force(side=Side.BLUE, name="Blue Force")
        assert force.commander_ids == []
        assert force.unit_ids == []
        assert force.victory_points == 0

    def test_frozen(self):
        force = Force(side=Side.RED, name="Red Force")
        with pytest.raises(ValidationError):
            force.victory_points = 100

    def test_roundtrip_serialization(self):
        force = Force(
            side=Side.BLUE, name="Blue Force",
            commander_ids=["c1"], unit_ids=["u1", "u2"], victory_points=5
        )
        restored = Force.model_validate_json(force.model_dump_json())
        assert restored == force


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_side_values(self):
        assert Side.BLUE.value == "BLUE"
        assert Side.RED.value == "RED"

    def test_unit_type_all_values(self):
        expected = {"INFANTRY", "MECHANIZED", "ARMOR", "ARTILLERY", "AIR_DEFENSE", "ENGINEER", "HQ"}
        assert {e.value for e in UnitType} == expected

    def test_mission_type_all_values(self):
        expected = {"ATTACK", "DEFEND", "DELAY", "RESERVE", "WITHDRAW"}
        assert {e.value for e in MissionType} == expected

    def test_combat_result_all_values(self):
        expected = {"AR", "S", "DR", "DE", "DRt"}
        assert {e.value for e in CombatResult} == expected

    def test_turn_phase_all_values(self):
        expected = {"COMMAND", "EXECUTION", "RESOLUTION"}
        assert {e.value for e in TurnPhase} == expected

    def test_action_type_all_values(self):
        expected = {"MOVE", "ATTACK", "DEFEND", "RETREAT", "HOLD", "DO_NOTHING"}
        assert {e.value for e in ActionType} == expected


# ---------------------------------------------------------------------------
# MilitaryAction
# ---------------------------------------------------------------------------

class TestMilitaryAction:
    def test_creation_defaults(self):
        action = MilitaryAction(
            action_id="a-1", turn=1, commander_id="cmd-1",
            unit_id="unit-1", action_type=ActionType.MOVE
        )
        assert action.priority == 3
        assert action.reasoning == ""
        assert action.target_hex is None
        assert action.target_unit_id is None

    def test_frozen(self):
        action = MilitaryAction(
            action_id="a-2", turn=1, commander_id="cmd-1",
            unit_id="unit-1", action_type=ActionType.HOLD
        )
        with pytest.raises(ValidationError):
            action.priority = 1

    def test_roundtrip_serialization(self):
        action = MilitaryAction(
            action_id="a-3", turn=2, commander_id="cmd-2",
            unit_id="unit-2", action_type=ActionType.ATTACK,
            target_hex=HexCoord(q=1, r=0), target_unit_id="unit-3",
            priority=1, reasoning="Flank attack"
        )
        restored = MilitaryAction.model_validate_json(action.model_dump_json())
        assert restored == action


# ---------------------------------------------------------------------------
# OrderDirective
# ---------------------------------------------------------------------------

class TestOrderDirective:
    def _make_directive(self, **overrides) -> OrderDirective:
        defaults = dict(
            order_id="ord-1", turn=1, issuer_id="cmd-1",
            target_unit_id="unit-1", mission=MissionType.ATTACK,
            objective_hex=HexCoord(q=5, r=-2), priority=2,
            constraints=["Avoid urban", "Maintain supply line"],
            reasoning="Exploit gap in enemy line"
        )
        defaults.update(overrides)
        return OrderDirective(**defaults)

    def test_to_battalion_context_structure(self):
        directive = self._make_directive()
        ctx = directive.to_battalion_context()
        assert ctx["mission"] == "ATTACK"
        assert ctx["objective_hex"] == {"q": 5, "r": -2}
        assert ctx["priority"] == 2
        assert ctx["constraints"] == ["Avoid urban", "Maintain supply line"]
        assert ctx["reasoning"] == "Exploit gap in enemy line"

    def test_to_battalion_context_no_objective(self):
        directive = self._make_directive(objective_hex=None)
        ctx = directive.to_battalion_context()
        assert ctx["objective_hex"] is None

    def test_constraints_default_empty(self):
        directive = OrderDirective(
            order_id="ord-2", turn=1, issuer_id="cmd-1",
            target_unit_id="unit-1", mission=MissionType.DEFEND
        )
        assert directive.constraints == []

    def test_frozen(self):
        directive = self._make_directive()
        with pytest.raises(ValidationError):
            directive.mission = MissionType.DEFEND

    def test_roundtrip_serialization(self):
        directive = self._make_directive()
        restored = OrderDirective.model_validate_json(directive.model_dump_json())
        assert restored == directive


# ---------------------------------------------------------------------------
# CombatOutcome
# ---------------------------------------------------------------------------

class TestCombatOutcome:
    def test_creation(self):
        outcome = CombatOutcome(
            attacker_id="unit-1", defender_id="unit-2",
            hex_coord=HexCoord(q=3, r=0), force_ratio=1.5,
            die_roll=4, result=CombatResult.DEFENDER_RETREAT,
            attacker_losses=0.1, defender_losses=0.3,
            defender_retreat_hexes=1
        )
        assert outcome.narrative == ""
        assert outcome.result == CombatResult.DEFENDER_RETREAT

    def test_frozen(self):
        outcome = CombatOutcome(
            attacker_id="u1", defender_id="u2",
            hex_coord=HexCoord(q=0, r=0), force_ratio=1.0,
            die_roll=3, result=CombatResult.STALEMATE,
            attacker_losses=0.05, defender_losses=0.05,
            defender_retreat_hexes=0
        )
        with pytest.raises(ValidationError):
            outcome.die_roll = 6

    def test_roundtrip_serialization(self):
        outcome = CombatOutcome(
            attacker_id="u1", defender_id="u2",
            hex_coord=HexCoord(q=2, r=1), force_ratio=2.0,
            die_roll=6, result=CombatResult.DEFENDER_ROUT,
            attacker_losses=0.05, defender_losses=0.8,
            defender_retreat_hexes=3, narrative="Overwhelming assault"
        )
        restored = CombatOutcome.model_validate_json(outcome.model_dump_json())
        assert restored == outcome


# ---------------------------------------------------------------------------
# MovementResult
# ---------------------------------------------------------------------------

class TestMovementResult:
    def test_triggered_combats_default_empty(self):
        result = MovementResult(
            unit_id="unit-1",
            path=[HexCoord(q=0, r=0), HexCoord(q=1, r=0)],
            final_position=HexCoord(q=1, r=0),
            movement_spent=1,
            remaining_mp=5,
        )
        assert result.triggered_combats == []

    def test_frozen(self):
        result = MovementResult(
            unit_id="unit-1",
            path=[HexCoord(q=0, r=0)],
            final_position=HexCoord(q=0, r=0),
            movement_spent=0,
            remaining_mp=6,
        )
        with pytest.raises(ValidationError):
            result.remaining_mp = 3

    def test_triggered_combats_populated(self):
        result = MovementResult(
            unit_id="unit-1",
            path=[HexCoord(q=0, r=0), HexCoord(q=1, r=0)],
            final_position=HexCoord(q=1, r=0),
            movement_spent=1,
            remaining_mp=5,
            triggered_combats=[("unit-1", "unit-enemy-1")],
        )
        assert len(result.triggered_combats) == 1
        assert result.triggered_combats[0] == ("unit-1", "unit-enemy-1")

    def test_roundtrip_serialization(self):
        result = MovementResult(
            unit_id="unit-2",
            path=[HexCoord(q=0, r=0), HexCoord(q=1, r=-1), HexCoord(q=2, r=-1)],
            final_position=HexCoord(q=2, r=-1),
            movement_spent=2,
            remaining_mp=4,
            triggered_combats=[("unit-2", "unit-red-3")],
        )
        restored = MovementResult.model_validate_json(result.model_dump_json())
        assert restored == result


# ---------------------------------------------------------------------------
# TurnResult
# ---------------------------------------------------------------------------

class TestTurnResult:
    def test_defaults(self):
        turn_result = TurnResult(turn=1)
        assert turn_result.phase_results == {}
        assert turn_result.movements == []
        assert turn_result.combats == []
        assert turn_result.destroyed_units == []
        assert turn_result.state_snapshot_path is None

    def test_not_frozen(self):
        # TurnResult is intentionally not frozen (mutable accumulator)
        turn_result = TurnResult(turn=1)
        turn_result.destroyed_units = ["unit-x"]
        assert turn_result.destroyed_units == ["unit-x"]

    def test_roundtrip_serialization(self):
        turn_result = TurnResult(
            turn=3,
            destroyed_units=["unit-5"],
            state_snapshot_path="/snapshots/turn_3.json"
        )
        restored = TurnResult.model_validate_json(turn_result.model_dump_json())
        assert restored.turn == 3
        assert restored.destroyed_units == ["unit-5"]
        assert restored.state_snapshot_path == "/snapshots/turn_3.json"
