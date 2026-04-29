"""Tests for Phase 4A: step mode, player commands, human commander, game config."""
from __future__ import annotations
import json
import uuid
import pytest
from app.models.game_config import GameConfig, CommandMode, FogMode, AIDifficulty
from app.models.actions import MilitaryAction, ActionType, OrderDirective, MissionType
from app.models.domain import HexCoord, Side, UnitStatus
from app.engine.human_commander import HumanCommander
from app.engine.game_state import GameState
from app.engine.turn_manager import TurnManager
from app.engine.constraint_engine import ConstraintEngine
from app.engine.combat_resolver import CombatResolver
from app.engine.movement_engine import MovementEngine


# ---------- Fixtures ----------

MINI_SCENARIO = {
    "map": {
        "hexes": [
            {"q": q, "r": r, "terrain": "PLAIN"}
            for q in range(6) for r in range(6)
        ]
    },
    "forces": {
        "BLUE": {
            "name": "Blue Force",
            "commanders": [
                {"id": "blue_theater", "name": "Blue Theater", "rank": "Theater", "unit_id": "blue_1bn"},
                {"id": "blue_bn1_cmd", "name": "Blue BN1 Cmd", "rank": "Battalion", "unit_id": "blue_1bn"},
                {"id": "blue_bn2_cmd", "name": "Blue BN2 Cmd", "rank": "Battalion", "unit_id": "blue_2bn"},
            ],
            "units": [
                {
                    "id": "blue_1bn", "name": "1st BN", "type": "INFANTRY", "size": "BATTALION",
                    "position": {"q": 1, "r": 1}, "strength": 1.0, "morale": 0.8,
                    "max_movement_points": 2, "attack_power": 10, "defense_power": 10,
                },
                {
                    "id": "blue_2bn", "name": "2nd BN", "type": "INFANTRY", "size": "BATTALION",
                    "position": {"q": 1, "r": 3}, "strength": 1.0, "morale": 0.8,
                    "max_movement_points": 2, "attack_power": 10, "defense_power": 10,
                },
            ],
        },
        "RED": {
            "name": "Red Force",
            "commanders": [
                {"id": "red_theater", "name": "Red Theater", "rank": "Theater", "unit_id": "red_1bn"},
                {"id": "red_bn1_cmd", "name": "Red BN1 Cmd", "rank": "Battalion", "unit_id": "red_1bn"},
            ],
            "units": [
                {
                    "id": "red_1bn", "name": "Red 1st BN", "type": "INFANTRY", "size": "BATTALION",
                    "position": {"q": 4, "r": 2}, "strength": 1.0, "morale": 0.8,
                    "max_movement_points": 2, "attack_power": 10, "defense_power": 10,
                },
            ],
        },
    },
    "config": {"max_turns": 10},
}


@pytest.fixture
def game_state():
    return GameState(MINI_SCENARIO)


@pytest.fixture
def turn_manager(game_state):
    from app.agents.theater_commander import TheaterCommander
    from app.agents.battalion_commander import BattalionCommander

    llm_config = {"api_key": "", "base_url": "", "model": "test", "temperature": 0.0}
    agents = {}
    for cid, cmd in game_state.commanders.items():
        if cmd.rank == "Theater":
            agents[cid] = TheaterCommander(commander=cmd, llm_config=llm_config)
        else:
            agents[cid] = BattalionCommander(commander=cmd, llm_config=llm_config)

    return TurnManager(
        game_state=game_state,
        agents=agents,
        constraint_engine=ConstraintEngine(),
        combat_resolver=CombatResolver(),
        movement_engine=MovementEngine(),
    )


# ---------- GameConfig ----------

class TestGameConfig:
    def test_default_config(self):
        config = GameConfig()
        assert config.player_side is None
        assert config.command_mode == CommandMode.HYBRID
        assert config.fog_mode == FogMode.SOFT
        assert config.ai_difficulty == AIDifficulty.MEDIUM

    def test_player_config(self):
        config = GameConfig(
            player_side="BLUE",
            command_mode=CommandMode.TACTICAL,
            fog_mode=FogMode.FULL,
            ai_difficulty=AIDifficulty.HARD,
        )
        assert config.player_side == "BLUE"
        assert config.command_mode == CommandMode.TACTICAL

    def test_observer_mode(self):
        config = GameConfig()
        assert config.player_side is None

    def test_serialization(self):
        config = GameConfig(player_side="RED")
        d = config.model_dump()
        assert d["player_side"] == "RED"
        assert d["command_mode"] == "HYBRID"


# ---------- HumanCommander ----------

class TestHumanCommander:
    def test_init(self):
        hc = HumanCommander(side="BLUE", command_mode=CommandMode.HYBRID)
        assert hc.side == "BLUE"
        assert hc.command_mode == CommandMode.HYBRID
        assert not hc.has_pending()

    def test_submit_orders(self):
        hc = HumanCommander(side="BLUE")
        order = OrderDirective(
            order_id="o1", turn=1, issuer_id="PLAYER",
            target_unit_id="blue_1bn", mission=MissionType.ATTACK,
            objective_hex=HexCoord(q=3, r=2),
        )
        hc.submit_orders([order])
        assert hc.has_pending()
        assert len(hc.get_pending_orders()) == 1

    def test_submit_actions(self):
        hc = HumanCommander(side="BLUE")
        action = MilitaryAction(
            action_id="a1", turn=1, commander_id="PLAYER",
            unit_id="blue_1bn", action_type=ActionType.MOVE,
            target_hex=HexCoord(q=2, r=1),
        )
        hc.submit_actions([action])
        assert hc.has_pending()
        assert len(hc.get_pending_actions()) == 1

    def test_clear_pending(self):
        hc = HumanCommander(side="BLUE")
        hc.submit_orders([OrderDirective(
            order_id="o1", turn=1, issuer_id="PLAYER",
            target_unit_id="blue_1bn", mission=MissionType.DEFEND,
        )])
        hc.clear_pending()
        assert not hc.has_pending()

    def test_validate_strategic_rejects_actions(self):
        hc = HumanCommander(side="BLUE", command_mode=CommandMode.STRATEGIC)
        action = MilitaryAction(
            action_id="a1", turn=1, commander_id="PLAYER",
            unit_id="blue_1bn", action_type=ActionType.MOVE,
            target_hex=HexCoord(q=2, r=1),
        )
        errors = hc.validate_commands(actions=[action])
        assert len(errors) == 1
        assert "STRATEGIC" in errors[0]

    def test_validate_tactical_rejects_orders(self):
        hc = HumanCommander(side="BLUE", command_mode=CommandMode.TACTICAL)
        order = OrderDirective(
            order_id="o1", turn=1, issuer_id="PLAYER",
            target_unit_id="blue_1bn", mission=MissionType.ATTACK,
        )
        errors = hc.validate_commands(orders=[order])
        assert len(errors) == 1
        assert "TACTICAL" in errors[0]

    def test_validate_hybrid_accepts_both(self):
        hc = HumanCommander(side="BLUE", command_mode=CommandMode.HYBRID)
        order = OrderDirective(
            order_id="o1", turn=1, issuer_id="PLAYER",
            target_unit_id="blue_1bn", mission=MissionType.ATTACK,
        )
        action = MilitaryAction(
            action_id="a1", turn=1, commander_id="PLAYER",
            unit_id="blue_2bn", action_type=ActionType.DEFEND,
        )
        errors = hc.validate_commands(orders=[order], actions=[action])
        assert len(errors) == 0

    def test_validate_empty_commands(self):
        hc = HumanCommander(side="BLUE")
        errors = hc.validate_commands()
        assert len(errors) == 1
        assert "No commands" in errors[0]

    def test_returns_copies(self):
        hc = HumanCommander(side="BLUE")
        order = OrderDirective(
            order_id="o1", turn=1, issuer_id="PLAYER",
            target_unit_id="blue_1bn", mission=MissionType.DEFEND,
        )
        hc.submit_orders([order])
        result = hc.get_pending_orders()
        result.clear()
        assert len(hc.get_pending_orders()) == 1


# ---------- TurnManager step_turn ----------

class TestStepTurn:
    def test_step_increments_turn(self, turn_manager):
        assert turn_manager.game_state.turn == 0
        turn_manager.step_turn()
        assert turn_manager.game_state.turn == 1

    def test_step_returns_turn_result(self, turn_manager):
        result = turn_manager.step_turn()
        assert result.turn == 1
        assert hasattr(result, "movements")
        assert hasattr(result, "combats")

    def test_multiple_steps(self, turn_manager):
        turn_manager.step_turn()
        turn_manager.step_turn()
        assert turn_manager.game_state.turn == 2
        assert len(turn_manager.turn_results) == 2

    def test_step_with_human_commander_tactical(self, turn_manager):
        hc = HumanCommander(side="BLUE", command_mode=CommandMode.TACTICAL)
        turn_manager.human_commander = hc

        action = MilitaryAction(
            action_id=str(uuid.uuid4()), turn=1,
            commander_id="blue_bn1_cmd", unit_id="blue_1bn",
            action_type=ActionType.MOVE,
            target_hex=HexCoord(q=2, r=1),
        )
        hc.submit_actions([action])

        result = turn_manager.step_turn()
        assert result.turn == 1
        unit = turn_manager.game_state.get_unit("blue_1bn")
        assert unit.position == HexCoord(q=2, r=1)

    def test_step_clears_pending_commands(self, turn_manager):
        hc = HumanCommander(side="BLUE", command_mode=CommandMode.TACTICAL)
        turn_manager.human_commander = hc

        hc.submit_actions([MilitaryAction(
            action_id=str(uuid.uuid4()), turn=1,
            commander_id="blue_bn1_cmd", unit_id="blue_1bn",
            action_type=ActionType.HOLD,
        )])
        turn_manager.step_turn()
        assert not hc.has_pending()

    def test_step_hybrid_override(self, turn_manager):
        hc = HumanCommander(side="BLUE", command_mode=CommandMode.HYBRID)
        turn_manager.human_commander = hc

        override = MilitaryAction(
            action_id=str(uuid.uuid4()), turn=1,
            commander_id="blue_bn1_cmd", unit_id="blue_1bn",
            action_type=ActionType.MOVE,
            target_hex=HexCoord(q=2, r=1),
        )
        hc.submit_actions([override])

        result = turn_manager.step_turn()
        assert result.turn == 1
        unit = turn_manager.game_state.get_unit("blue_1bn")
        assert unit.position == HexCoord(q=2, r=1)


# ---------- Available Actions ----------

class TestAvailableActions:
    def test_no_human_commander(self, turn_manager):
        result = turn_manager.get_available_actions()
        assert result["units"] == []
        assert result["command_mode"] is None

    def test_returns_player_units(self, turn_manager):
        hc = HumanCommander(side="BLUE", command_mode=CommandMode.HYBRID)
        turn_manager.human_commander = hc
        turn_manager.game_state.advance_turn()

        result = turn_manager.get_available_actions()
        assert len(result["units"]) == 2
        unit_ids = {u["unit_id"] for u in result["units"]}
        assert "blue_1bn" in unit_ids
        assert "blue_2bn" in unit_ids

    def test_includes_move_hexes(self, turn_manager):
        hc = HumanCommander(side="BLUE", command_mode=CommandMode.TACTICAL)
        turn_manager.human_commander = hc
        turn_manager.game_state.advance_turn()

        result = turn_manager.get_available_actions()
        unit_data = next(u for u in result["units"] if u["unit_id"] == "blue_1bn")
        move_action = next(a for a in unit_data["available_actions"] if a["type"] == "MOVE")
        assert len(move_action["valid_hexes"]) > 0

    def test_always_has_defend_and_hold(self, turn_manager):
        hc = HumanCommander(side="BLUE", command_mode=CommandMode.TACTICAL)
        turn_manager.human_commander = hc
        turn_manager.game_state.advance_turn()

        result = turn_manager.get_available_actions()
        for unit in result["units"]:
            action_types = {a["type"] for a in unit["available_actions"]}
            assert "DEFEND" in action_types
            assert "HOLD" in action_types

    def test_command_mode_flags(self, turn_manager):
        hc = HumanCommander(side="BLUE", command_mode=CommandMode.STRATEGIC)
        turn_manager.human_commander = hc

        result = turn_manager.get_available_actions()
        assert result["command_mode"] == "STRATEGIC"
        assert result["can_issue_orders"] is True
        assert result["can_issue_actions"] is False

    def test_excludes_destroyed_units(self, turn_manager):
        hc = HumanCommander(side="BLUE", command_mode=CommandMode.TACTICAL)
        turn_manager.human_commander = hc
        turn_manager.game_state.advance_turn()
        turn_manager.game_state.update_unit("blue_1bn", status=UnitStatus.DESTROYED)

        result = turn_manager.get_available_actions()
        unit_ids = {u["unit_id"] for u in result["units"]}
        assert "blue_1bn" not in unit_ids
        assert "blue_2bn" in unit_ids


# ---------- API Integration ----------

class TestSimulationAPI:
    @pytest.fixture
    def client(self):
        from app import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_create_observer_mode(self, client):
        resp = client.post("/api/simulations/", json={"scenario_name": "korean_peninsula"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["mode"] == "observer"
        assert data["game_config"]["player_side"] is None

    def test_create_player_mode(self, client):
        resp = client.post("/api/simulations/", json={
            "scenario_name": "korean_peninsula",
            "player_side": "BLUE",
            "command_mode": "HYBRID",
            "fog_mode": "SOFT",
            "ai_difficulty": "MEDIUM",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["mode"] == "player"
        assert data["game_config"]["player_side"] == "BLUE"
        assert data["game_config"]["command_mode"] == "HYBRID"

    def test_status_includes_game_config(self, client):
        resp = client.post("/api/simulations/", json={
            "scenario_name": "korean_peninsula",
            "player_side": "RED",
            "ai_difficulty": "HARD",
        })
        sim_id = resp.get_json()["simulation_id"]
        status = client.get(f"/api/simulations/{sim_id}/status").get_json()
        assert status["mode"] == "player"
        assert status["game_config"]["ai_difficulty"] == "HARD"

    def test_available_actions_endpoint(self, client):
        resp = client.post("/api/simulations/", json={
            "scenario_name": "korean_peninsula",
            "player_side": "BLUE",
            "command_mode": "TACTICAL",
        })
        sim_id = resp.get_json()["simulation_id"]
        actions_resp = client.get(f"/api/simulations/{sim_id}/available-actions")
        assert actions_resp.status_code == 200
        data = actions_resp.get_json()
        assert data["command_mode"] == "TACTICAL"
        assert len(data["units"]) > 0

    def test_available_actions_observer_rejected(self, client):
        resp = client.post("/api/simulations/", json={"scenario_name": "korean_peninsula"})
        sim_id = resp.get_json()["simulation_id"]
        actions_resp = client.get(f"/api/simulations/{sim_id}/available-actions")
        assert actions_resp.status_code == 400

    def test_step_turn_endpoint(self, client):
        resp = client.post("/api/simulations/", json={
            "scenario_name": "korean_peninsula",
            "player_side": "BLUE",
            "command_mode": "TACTICAL",
        })
        sim_id = resp.get_json()["simulation_id"]

        # Submit a HOLD command for first unit
        actions_data = client.get(f"/api/simulations/{sim_id}/available-actions").get_json()
        first_unit = actions_data["units"][0]

        cmd_resp = client.post(f"/api/simulations/{sim_id}/commands", json={
            "actions": [{"unit_id": first_unit["unit_id"], "action_type": "HOLD"}],
        })
        assert cmd_resp.status_code == 200
        assert cmd_resp.get_json()["accepted"] is True

        step_resp = client.post(f"/api/simulations/{sim_id}/step")
        assert step_resp.status_code == 200
        data = step_resp.get_json()
        assert data["turn"] == 1
        assert "status" in data

    def test_commands_rejected_for_observer(self, client):
        resp = client.post("/api/simulations/", json={"scenario_name": "korean_peninsula"})
        sim_id = resp.get_json()["simulation_id"]
        cmd_resp = client.post(f"/api/simulations/{sim_id}/commands", json={
            "actions": [{"unit_id": "x", "action_type": "HOLD"}],
        })
        assert cmd_resp.status_code == 400

    def test_commands_mode_validation(self, client):
        resp = client.post("/api/simulations/", json={
            "scenario_name": "korean_peninsula",
            "player_side": "BLUE",
            "command_mode": "STRATEGIC",
        })
        sim_id = resp.get_json()["simulation_id"]

        # Tactical actions rejected in strategic mode
        cmd_resp = client.post(f"/api/simulations/{sim_id}/commands", json={
            "actions": [{"unit_id": "blue_1bn", "action_type": "HOLD"}],
        })
        assert cmd_resp.status_code == 400
        assert "STRATEGIC" in cmd_resp.get_json()["details"][0]

    def test_step_not_allowed_during_autoplay(self, client):
        resp = client.post("/api/simulations/", json={
            "scenario_name": "korean_peninsula",
            "player_side": "BLUE",
        })
        sim_id = resp.get_json()["simulation_id"]

        # Start auto-play
        client.post(f"/api/simulations/{sim_id}/start")

        # Step should fail
        step_resp = client.post(f"/api/simulations/{sim_id}/step")
        assert step_resp.status_code == 400

    def test_autoplay_still_works(self, client):
        resp = client.post("/api/simulations/", json={"scenario_name": "korean_peninsula"})
        sim_id = resp.get_json()["simulation_id"]
        start_resp = client.post(f"/api/simulations/{sim_id}/start", json={"max_turns": 2})
        assert start_resp.status_code == 200
        assert start_resp.get_json()["status"] == "running"
