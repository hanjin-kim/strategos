from __future__ import annotations
import pytest
from app.models.domain import (
    HexCoord, Side, UnitType, UnitSize, UnitStatus, TerrainType,
    Unit, Commander, TerrainHex,
)
from app.models.actions import ActionType, MilitaryAction
from app.engine.game_state import GameState
from app.engine.constraint_engine import ConstraintEngine, ValidationResult


# ---------------------------------------------------------------------------
# Test fixture helpers
# ---------------------------------------------------------------------------

def _make_unit(**overrides) -> Unit:
    defaults = dict(
        id="blue-1",
        name="1st Battalion",
        side=Side.BLUE,
        unit_type=UnitType.INFANTRY,
        size=UnitSize.BATTALION,
        position=HexCoord(q=0, r=0),
        strength=1.0,
        morale=0.8,
        movement_points=3,
        max_movement_points=3,
        attack_power=10.0,
        defense_power=8.0,
        effective_range=2,
        ammo=1.0,
        fuel=1.0,
        status=UnitStatus.ACTIVE,
    )
    defaults.update(overrides)
    return Unit(**defaults)


def _make_action(**overrides) -> MilitaryAction:
    defaults = dict(
        action_id="a-1",
        turn=1,
        commander_id="cmd-blue",
        unit_id="blue-1",
        action_type=ActionType.MOVE,
        target_hex=HexCoord(q=1, r=0),
    )
    defaults.update(overrides)
    return MilitaryAction(**defaults)


def _build_game_state() -> GameState:
    """Build a minimal GameState with two opposing units and commanders."""
    state = GameState()

    # Blue unit at (0,0), range 2, movement 3, ammo full
    blue_unit = _make_unit(id="blue-1", side=Side.BLUE, position=HexCoord(q=0, r=0))
    # Red unit at (1,0)
    red_unit = _make_unit(id="red-1", side=Side.RED, position=HexCoord(q=1, r=0))

    state.units["blue-1"] = blue_unit
    state.units["red-1"] = red_unit

    state.commanders["cmd-blue"] = Commander(
        id="cmd-blue", name="Blue Commander", side=Side.BLUE,
        rank="Battalion", unit_id="blue-1",
    )
    state.commanders["cmd-red"] = Commander(
        id="cmd-red", name="Red Commander", side=Side.RED,
        rank="Battalion", unit_id="red-1",
    )

    # Add some terrain
    state.terrain[HexCoord(q=0, r=0)] = TerrainHex(coord=HexCoord(q=0, r=0), terrain_type=TerrainType.PLAIN)
    state.terrain[HexCoord(q=1, r=0)] = TerrainHex(coord=HexCoord(q=1, r=0), terrain_type=TerrainType.PLAIN)
    state.terrain[HexCoord(q=2, r=0)] = TerrainHex(coord=HexCoord(q=2, r=0), terrain_type=TerrainType.PLAIN)
    state.terrain[HexCoord(q=0, r=1)] = TerrainHex(coord=HexCoord(q=0, r=1), terrain_type=TerrainType.WATER)

    return state


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestConstraintEngine:
    def setup_method(self):
        self.engine = ConstraintEngine()
        self.state = _build_game_state()

    # 1. Valid MOVE action -> passes
    def test_valid_move_action(self):
        action = _make_action(action_type=ActionType.MOVE, target_hex=HexCoord(q=2, r=0))
        result = self.engine.validate([action], self.state)
        assert len(result.valid_actions) == 1
        assert len(result.rejections) == 0

    # 2. Non-existent unit -> rejected
    def test_nonexistent_unit_rejected(self):
        action = _make_action(unit_id="ghost-99")
        result = self.engine.validate([action], self.state)
        assert len(result.valid_actions) == 0
        assert len(result.rejections) == 1
        assert "does not exist" in result.rejections[0][1]

    # 3. Wrong side (enemy unit) -> rejected
    def test_wrong_side_rejected(self):
        # cmd-blue tries to command red-1
        action = _make_action(unit_id="red-1", commander_id="cmd-blue")
        result = self.engine.validate([action], self.state)
        assert len(result.rejections) == 1
        assert "belongs to" in result.rejections[0][1]

    # 4. DESTROYED unit -> rejected
    def test_destroyed_unit_rejected(self):
        self.state.units["blue-1"] = _make_unit(id="blue-1", status=UnitStatus.DESTROYED)
        action = _make_action(action_type=ActionType.HOLD)
        result = self.engine.validate([action], self.state)
        assert len(result.rejections) == 1
        assert "destroyed" in result.rejections[0][1]

    # 5. ROUTED unit can only RETREAT or DO_NOTHING
    def test_routed_unit_can_retreat(self):
        self.state.units["blue-1"] = _make_unit(id="blue-1", status=UnitStatus.ROUTED)
        action = _make_action(action_type=ActionType.RETREAT, target_hex=HexCoord(q=0, r=0))
        result = self.engine.validate([action], self.state)
        assert len(result.valid_actions) == 1

    def test_routed_unit_can_do_nothing(self):
        self.state.units["blue-1"] = _make_unit(id="blue-1", status=UnitStatus.ROUTED)
        action = _make_action(action_type=ActionType.DO_NOTHING, target_hex=None)
        result = self.engine.validate([action], self.state)
        assert len(result.valid_actions) == 1

    def test_routed_unit_cannot_move(self):
        self.state.units["blue-1"] = _make_unit(id="blue-1", status=UnitStatus.ROUTED)
        action = _make_action(action_type=ActionType.MOVE, target_hex=HexCoord(q=1, r=0))
        result = self.engine.validate([action], self.state)
        assert len(result.rejections) == 1
        assert "routed" in result.rejections[0][1]

    def test_routed_unit_cannot_attack(self):
        self.state.units["blue-1"] = _make_unit(id="blue-1", status=UnitStatus.ROUTED)
        action = _make_action(action_type=ActionType.ATTACK, target_hex=HexCoord(q=1, r=0))
        result = self.engine.validate([action], self.state)
        assert len(result.rejections) == 1
        assert "routed" in result.rejections[0][1]

    # 6. Move exceeding movement_points -> rejected
    def test_move_exceeds_movement_points(self):
        # blue-1 has movement_points=3, target at distance 4
        action = _make_action(action_type=ActionType.MOVE, target_hex=HexCoord(q=4, r=0))
        result = self.engine.validate([action], self.state)
        assert len(result.rejections) == 1
        assert "movement points" in result.rejections[0][1]

    # 7. Move into WATER -> rejected
    def test_move_into_water_rejected(self):
        action = _make_action(action_type=ActionType.MOVE, target_hex=HexCoord(q=0, r=1))
        result = self.engine.validate([action], self.state)
        assert len(result.rejections) == 1
        assert "water" in result.rejections[0][1].lower()

    # 8. Move without target_hex -> rejected
    def test_move_without_target_hex_rejected(self):
        action = _make_action(action_type=ActionType.MOVE, target_hex=None)
        result = self.engine.validate([action], self.state)
        assert len(result.rejections) == 1
        assert "target_hex" in result.rejections[0][1]

    # 9. Attack out of range -> rejected
    def test_attack_out_of_range_rejected(self):
        # blue-1 at (0,0), effective_range=2, target at distance 3
        action = _make_action(action_type=ActionType.ATTACK, target_hex=HexCoord(q=3, r=0))
        result = self.engine.validate([action], self.state)
        assert len(result.rejections) == 1
        assert "out of range" in result.rejections[0][1]

    # 10. Attack with low ammo (<0.1) -> rejected
    def test_attack_low_ammo_rejected(self):
        self.state.units["blue-1"] = _make_unit(id="blue-1", ammo=0.05)
        action = _make_action(action_type=ActionType.ATTACK, target_hex=HexCoord(q=1, r=0))
        result = self.engine.validate([action], self.state)
        assert len(result.rejections) == 1
        assert "ammo" in result.rejections[0][1]

    # 11. Attack friendly unit -> rejected
    def test_attack_friendly_unit_rejected(self):
        # Add another blue unit
        blue_2 = _make_unit(id="blue-2", position=HexCoord(q=1, r=0))
        self.state.units["blue-2"] = blue_2
        action = _make_action(
            action_type=ActionType.ATTACK,
            target_hex=None,
            target_unit_id="blue-2",
        )
        result = self.engine.validate([action], self.state)
        assert len(result.rejections) == 1
        assert "friendly" in result.rejections[0][1]

    # 12. Attack non-existent target -> rejected
    def test_attack_nonexistent_target_rejected(self):
        action = _make_action(
            action_type=ActionType.ATTACK,
            target_hex=None,
            target_unit_id="ghost-unit",
        )
        result = self.engine.validate([action], self.state)
        assert len(result.rejections) == 1
        assert "does not exist" in result.rejections[0][1]

    # 13. DO_NOTHING always valid
    def test_do_nothing_always_valid(self):
        action = _make_action(action_type=ActionType.DO_NOTHING, target_hex=None)
        result = self.engine.validate([action], self.state)
        assert len(result.valid_actions) == 1
        assert len(result.rejections) == 0

    # 14. HOLD always valid
    def test_hold_always_valid(self):
        action = _make_action(action_type=ActionType.HOLD, target_hex=None)
        result = self.engine.validate([action], self.state)
        assert len(result.valid_actions) == 1
        assert len(result.rejections) == 0

    # 15. DEFEND always valid
    def test_defend_always_valid(self):
        action = _make_action(action_type=ActionType.DEFEND, target_hex=None)
        result = self.engine.validate([action], self.state)
        assert len(result.valid_actions) == 1
        assert len(result.rejections) == 0

    # 16. Duplicate unit actions -> second rejected
    def test_duplicate_unit_action_rejected(self):
        action1 = _make_action(action_id="a-1", action_type=ActionType.HOLD, target_hex=None)
        action2 = _make_action(action_id="a-2", action_type=ActionType.MOVE, target_hex=HexCoord(q=1, r=0))
        result = self.engine.validate([action1, action2], self.state)
        assert len(result.valid_actions) == 1
        assert len(result.rejections) == 1
        assert result.valid_actions[0].action_id == "a-1"
        assert "Duplicate" in result.rejections[0][1]

    # 17. has_rejections property
    def test_has_rejections_false_when_all_valid(self):
        action = _make_action(action_type=ActionType.HOLD, target_hex=None)
        result = self.engine.validate([action], self.state)
        assert result.has_rejections is False

    def test_has_rejections_true_when_some_invalid(self):
        action = _make_action(unit_id="ghost-99")
        result = self.engine.validate([action], self.state)
        assert result.has_rejections is True

    # 18. audit_state: clean state -> no warnings
    def test_audit_state_clean(self):
        warnings = self.engine.audit_state(self.state)
        assert warnings == []

    # 19. Multiple valid actions -> all pass
    def test_multiple_valid_actions_all_pass(self):
        action_blue = _make_action(
            action_id="a-blue", unit_id="blue-1", commander_id="cmd-blue",
            action_type=ActionType.HOLD, target_hex=None,
        )
        action_red = _make_action(
            action_id="a-red", unit_id="red-1", commander_id="cmd-red",
            action_type=ActionType.HOLD, target_hex=None,
        )
        result = self.engine.validate([action_blue, action_red], self.state)
        assert len(result.valid_actions) == 2
        assert len(result.rejections) == 0

    # 20. Mixed valid/invalid -> correct split
    def test_mixed_valid_invalid_correct_split(self):
        valid_action = _make_action(
            action_id="a-valid", unit_id="blue-1", commander_id="cmd-blue",
            action_type=ActionType.HOLD, target_hex=None,
        )
        invalid_action = _make_action(
            action_id="a-invalid", unit_id="ghost-99", commander_id="cmd-blue",
            action_type=ActionType.MOVE, target_hex=HexCoord(q=1, r=0),
        )
        result = self.engine.validate([valid_action, invalid_action], self.state)
        assert len(result.valid_actions) == 1
        assert len(result.rejections) == 1
        assert result.valid_actions[0].action_id == "a-valid"
        assert result.rejections[0][0].action_id == "a-invalid"

    # Extra: non-existent commander -> rejected
    def test_nonexistent_commander_rejected(self):
        action = _make_action(commander_id="ghost-cmd")
        result = self.engine.validate([action], self.state)
        assert len(result.rejections) == 1
        assert "Commander" in result.rejections[0][1]

    # Extra: valid attack by target_unit_id
    def test_valid_attack_by_target_unit_id(self):
        # blue-1 at (0,0), red-1 at (1,0), range=2
        action = _make_action(
            action_type=ActionType.ATTACK,
            target_hex=None,
            target_unit_id="red-1",
        )
        result = self.engine.validate([action], self.state)
        assert len(result.valid_actions) == 1

    # Extra: attack out of range via target_unit_id
    def test_attack_out_of_range_by_target_unit_id(self):
        far_red = _make_unit(id="red-far", side=Side.RED, position=HexCoord(q=5, r=0))
        self.state.units["red-far"] = far_red
        action = _make_action(
            action_type=ActionType.ATTACK,
            target_hex=None,
            target_unit_id="red-far",
        )
        result = self.engine.validate([action], self.state)
        assert len(result.rejections) == 1
        assert "out of range" in result.rejections[0][1]

    # Extra: retreat without target_hex -> rejected
    def test_retreat_without_target_hex_rejected(self):
        action = _make_action(action_type=ActionType.RETREAT, target_hex=None)
        result = self.engine.validate([action], self.state)
        assert len(result.rejections) == 1
        assert "target_hex" in result.rejections[0][1]
