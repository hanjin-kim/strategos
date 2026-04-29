from __future__ import annotations
import json
import pytest
from unittest.mock import MagicMock
from app.models.domain import Side, UnitType, UnitSize, UnitStatus, HexCoord, Unit, Force
from app.models.simulation import TurnResult, CombatOutcome, CombatResult
from app.models.narrative import TurnNarrative
from app.narrative.commander_personality import (
    CommanderPersonality, get_commander_personality, KOREAN_PENINSULA_COMMANDERS,
)
from app.narrative.dialogue_generator import DialogueGenerator
from app.agents.adjudicator import Adjudicator
from app.agents.base_commander import DIFFICULTY_DOCTRINE


def make_unit(uid, side, q=0, r=0, status=UnitStatus.ACTIVE, strength=1.0):
    return Unit(
        id=uid, name=f"Unit-{uid}", side=side,
        unit_type=UnitType.INFANTRY, size=UnitSize.BATTALION,
        position=HexCoord(q=q, r=r),
        strength=strength, morale=0.8,
        movement_points=2, max_movement_points=2,
        attack_power=10.0, defense_power=10.0,
        effective_range=1, ammo=1.0, fuel=1.0,
        status=status,
    )


def make_game_state():
    from app.engine.game_state import GameState
    gs = GameState()
    gs.turn = 1
    gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0)
    gs.units["blue2"] = make_unit("blue2", Side.BLUE, 1, 0)
    gs.units["red1"] = make_unit("red1", Side.RED, 2, 0)
    gs.units["red2"] = make_unit("red2", Side.RED, 3, 0)
    gs.forces[Side.BLUE] = Force(side=Side.BLUE, name="Blue", unit_ids=["blue1", "blue2"])
    gs.forces[Side.RED] = Force(side=Side.RED, name="Red", unit_ids=["red1", "red2"])
    return gs


def make_turn_result(turn=1, combats=None, destroyed=None):
    return TurnResult(
        turn=turn,
        combats=combats or [],
        destroyed_units=destroyed or [],
    )


def make_combat():
    return CombatOutcome(
        attacker_id="blue1", defender_id="red1",
        hex_coord=HexCoord(q=2, r=0), force_ratio=1.5, die_roll=4,
        result=CombatResult.DEFENDER_RETREAT,
        attacker_losses=0.1, defender_losses=0.3, defender_retreat_hexes=1,
    )


# ---------------------------------------------------------------------------
# CommanderPersonality
# ---------------------------------------------------------------------------

class TestCommanderPersonality:
    def test_blue_commander_exists(self):
        p = KOREAN_PENINSULA_COMMANDERS["BLUE"]
        assert p.name == "Gen. Park Sung-jin"
        assert p.side == "BLUE"
        assert "methodical" in p.traits

    def test_red_commander_exists(self):
        p = KOREAN_PENINSULA_COMMANDERS["RED"]
        assert p.name == "Gen. Kim Tae-hyun"
        assert p.side == "RED"
        assert "aggressive" in p.traits

    def test_get_commander_personality_blue(self):
        p = get_commander_personality("BLUE")
        assert p.name == "Gen. Park Sung-jin"

    def test_get_commander_personality_red(self):
        p = get_commander_personality("RED")
        assert p.name == "Gen. Kim Tae-hyun"

    def test_get_commander_personality_unknown_side(self):
        p = get_commander_personality("GREEN")
        assert p.name == "Commander (GREEN)"
        assert p.side == "GREEN"

    def test_personality_is_frozen(self):
        p = get_commander_personality("BLUE")
        with pytest.raises(Exception):
            p.name = "Modified"  # type: ignore[misc]

    def test_personality_has_catchphrases(self):
        p = KOREAN_PENINSULA_COMMANDERS["RED"]
        assert len(p.catchphrases) > 0

    def test_personality_has_background(self):
        p = KOREAN_PENINSULA_COMMANDERS["BLUE"]
        assert len(p.background) > 0


# ---------------------------------------------------------------------------
# DialogueGenerator
# ---------------------------------------------------------------------------

class TestDialogueGenerator:
    def test_init_no_api_key(self):
        dg = DialogueGenerator({})
        assert dg._client is None

    def test_init_with_api_key(self):
        dg = DialogueGenerator({"api_key": "test", "base_url": "https://example.com"})
        assert dg._client is not None

    def test_set_personalities(self):
        dg = DialogueGenerator({})
        dg.set_personalities("BLUE")
        assert "BLUE" in dg._personalities
        assert "RED" in dg._personalities
        assert dg._player_side == "BLUE"

    def test_fallback_dialogue_no_combats(self):
        dg = DialogueGenerator({})
        dg.set_personalities("BLUE")
        gs = make_game_state()
        tr = make_turn_result()
        result = dg._fallback_dialogue(tr, gs, "BLUE")
        assert "enemy_dialogue" in result
        assert "staff_briefing" in result
        assert "event_reactions" in result
        assert "quiet" in result["enemy_dialogue"][0]["text"].lower() or "biding" in result["enemy_dialogue"][0]["text"].lower()

    def test_fallback_dialogue_with_combats(self):
        dg = DialogueGenerator({})
        dg.set_personalities("BLUE")
        gs = make_game_state()
        tr = make_turn_result(combats=[make_combat()])
        result = dg._fallback_dialogue(tr, gs, "BLUE")
        assert len(result["enemy_dialogue"]) >= 1
        assert "1 engagements" in result["staff_briefing"]

    def test_fallback_dialogue_with_destroyed(self):
        dg = DialogueGenerator({})
        dg.set_personalities("BLUE")
        gs = make_game_state()
        tr = make_turn_result(destroyed=["red1"])
        result = dg._fallback_dialogue(tr, gs, "BLUE")
        assert "1 unit(s) destroyed" in result["staff_briefing"]
        assert "Unit red1 lost" in result["event_reactions"]

    def test_fallback_dialogue_speaker_is_enemy(self):
        dg = DialogueGenerator({})
        dg.set_personalities("BLUE")
        gs = make_game_state()
        tr = make_turn_result()
        result = dg._fallback_dialogue(tr, gs, "BLUE")
        for msg in result["enemy_dialogue"]:
            assert msg["speaker"] == "Gen. Kim Tae-hyun"

    def test_fallback_dialogue_red_player(self):
        dg = DialogueGenerator({})
        dg.set_personalities("RED")
        gs = make_game_state()
        tr = make_turn_result()
        result = dg._fallback_dialogue(tr, gs, "RED")
        for msg in result["enemy_dialogue"]:
            assert msg["speaker"] == "Gen. Park Sung-jin"

    def test_generate_dialogue_no_client_uses_fallback(self):
        dg = DialogueGenerator({})
        dg.set_personalities("BLUE")
        gs = make_game_state()
        tr = make_turn_result()
        result = dg.generate_dialogue(tr, gs, "BLUE")
        assert isinstance(result, dict)
        assert "enemy_dialogue" in result

    def test_generate_dialogue_llm_success(self):
        dg = DialogueGenerator({"api_key": "test", "base_url": "https://example.com"})
        dg.set_personalities("BLUE")
        response_data = {
            "enemy_dialogue": [{"speaker": "Gen. Kim", "text": "We hold!", "tone": "defiant"}],
            "staff_briefing": "Sir, the enemy retreats.",
            "event_reactions": ["Enemy unit destroyed"],
        }
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(response_data)
        dg._client = MagicMock()
        dg._client.chat.completions.create.return_value = mock_response

        gs = make_game_state()
        tr = make_turn_result()
        result = dg.generate_dialogue(tr, gs, "BLUE")
        assert result["enemy_dialogue"][0]["speaker"] == "Gen. Kim"
        assert result["staff_briefing"] == "Sir, the enemy retreats."

    def test_generate_dialogue_llm_failure_fallback(self):
        dg = DialogueGenerator({"api_key": "test", "base_url": "https://example.com"})
        dg.set_personalities("BLUE")
        dg._client = MagicMock()
        dg._client.chat.completions.create.side_effect = Exception("LLM error")

        gs = make_game_state()
        tr = make_turn_result()
        result = dg.generate_dialogue(tr, gs, "BLUE")
        assert isinstance(result, dict)
        assert "enemy_dialogue" in result

    def test_parse_dialogue_valid_json(self):
        dg = DialogueGenerator({})
        data = {
            "enemy_dialogue": [{"speaker": "Test", "text": "Hello", "tone": "confident"}],
            "staff_briefing": "All clear.",
            "event_reactions": [],
        }
        gs = make_game_state()
        tr = make_turn_result()
        result = dg._parse_dialogue(json.dumps(data), tr, gs, "BLUE")
        assert result["enemy_dialogue"][0]["speaker"] == "Test"

    def test_parse_dialogue_markdown_block(self):
        dg = DialogueGenerator({})
        data = {
            "enemy_dialogue": [],
            "staff_briefing": "Briefing here.",
            "event_reactions": [],
        }
        text = f"```json\n{json.dumps(data)}\n```"
        gs = make_game_state()
        tr = make_turn_result()
        result = dg._parse_dialogue(text, tr, gs, "BLUE")
        assert result["staff_briefing"] == "Briefing here."

    def test_parse_dialogue_malformed_falls_back(self):
        dg = DialogueGenerator({})
        dg.set_personalities("BLUE")
        gs = make_game_state()
        tr = make_turn_result()
        result = dg._parse_dialogue("not json!!!", tr, gs, "BLUE")
        assert isinstance(result, dict)
        assert "enemy_dialogue" in result


# ---------------------------------------------------------------------------
# TurnNarrative extended fields
# ---------------------------------------------------------------------------

class TestTurnNarrativeDialogue:
    def test_defaults(self):
        tn = TurnNarrative(turn=1)
        assert tn.enemy_dialogue == []
        assert tn.staff_briefing == ""
        assert tn.event_reactions == []

    def test_with_dialogue_data(self):
        tn = TurnNarrative(
            turn=1,
            enemy_dialogue=[{"speaker": "Gen. Kim", "text": "Attack!", "tone": "defiant"}],
            staff_briefing="Sir, we hold the line.",
            event_reactions=["Enemy unit lost"],
        )
        assert len(tn.enemy_dialogue) == 1
        assert tn.staff_briefing == "Sir, we hold the line."
        assert tn.event_reactions == ["Enemy unit lost"]

    def test_model_copy_with_dialogue(self):
        tn = TurnNarrative(turn=1, summary="Base narrative")
        updated = tn.model_copy(update={
            "enemy_dialogue": [{"speaker": "Test", "text": "msg", "tone": "confident"}],
            "staff_briefing": "Briefing",
        })
        assert updated.summary == "Base narrative"
        assert len(updated.enemy_dialogue) == 1
        assert updated.staff_briefing == "Briefing"


# ---------------------------------------------------------------------------
# TurnResult extended fields
# ---------------------------------------------------------------------------

class TestTurnResultDialogue:
    def test_defaults(self):
        tr = TurnResult(turn=1)
        assert tr.enemy_dialogue == []
        assert tr.staff_briefing == ""
        assert tr.event_reactions == []

    def test_with_dialogue_data(self):
        tr = TurnResult(
            turn=1,
            enemy_dialogue=[{"speaker": "Gen. Kim", "text": "Hold!", "tone": "defiant"}],
            staff_briefing="Sir, enemy retreating.",
            event_reactions=["Unit red1 destroyed"],
        )
        assert len(tr.enemy_dialogue) == 1
        assert tr.staff_briefing == "Sir, enemy retreating."


# ---------------------------------------------------------------------------
# Adjudicator + DialogueGenerator integration
# ---------------------------------------------------------------------------

class TestAdjudicatorDialogueIntegration:
    def test_set_dialogue_generator_no_client(self):
        adj = Adjudicator({})
        adj.set_dialogue_generator("BLUE")
        assert adj._dialogue_generator is not None
        assert "BLUE" in adj._dialogue_generator._personalities

    def test_set_dialogue_generator_with_client(self):
        adj = Adjudicator({"api_key": "test", "base_url": "https://example.com"})
        adj.set_dialogue_generator("BLUE")
        assert adj._dialogue_generator is not None

    def test_generate_narrative_with_dialogue_fallback(self):
        adj = Adjudicator({})
        adj.set_dialogue_generator("BLUE")
        gs = make_game_state()
        tr = make_turn_result()
        result = adj.generate_narrative(tr, gs, player_side="BLUE")
        assert isinstance(result, TurnNarrative)
        assert len(result.enemy_dialogue) > 0 or result.staff_briefing != ""

    def test_generate_narrative_without_player_side_no_dialogue(self):
        adj = Adjudicator({})
        adj.set_dialogue_generator("BLUE")
        gs = make_game_state()
        tr = make_turn_result()
        result = adj.generate_narrative(tr, gs, player_side=None)
        assert result.enemy_dialogue == []
        assert result.staff_briefing == ""

    def test_generate_narrative_no_dialogue_generator(self):
        adj = Adjudicator({})
        gs = make_game_state()
        tr = make_turn_result()
        result = adj.generate_narrative(tr, gs, player_side="BLUE")
        assert result.enemy_dialogue == []
        assert result.staff_briefing == ""


# ---------------------------------------------------------------------------
# Difficulty Doctrine
# ---------------------------------------------------------------------------

class TestDifficultyDoctrine:
    def test_easy_doctrine_exists(self):
        assert "cautious" in DIFFICULTY_DOCTRINE["EASY"].lower()

    def test_medium_doctrine_empty(self):
        assert DIFFICULTY_DOCTRINE["MEDIUM"] == ""

    def test_hard_doctrine_exists(self):
        assert "ruthless" in DIFFICULTY_DOCTRINE["HARD"].lower()

    def test_difficulty_in_system_prompt(self):
        from app.models.domain import Commander
        cmd = Commander(
            id="cmd1", name="Test Commander", rank="Battalion",
            side=Side.BLUE, unit_id="u1",
        )
        from app.agents.base_commander import BaseCommander
        bc = BaseCommander(
            commander=cmd, llm_config={}, difficulty="HARD",
        )
        prompt = bc._build_cached_system_prompt()
        assert "ruthless" in prompt.lower()

    def test_difficulty_default_medium(self):
        from app.models.domain import Commander
        cmd = Commander(
            id="cmd2", name="Test Commander", rank="Battalion",
            side=Side.BLUE, unit_id="u2",
        )
        from app.agents.base_commander import BaseCommander
        bc = BaseCommander(commander=cmd, llm_config={})
        prompt = bc._build_cached_system_prompt()
        assert "cautious" not in prompt.lower()
        assert "ruthless" not in prompt.lower()

    def test_difficulty_easy_doctrine_in_prompt(self):
        from app.models.domain import Commander
        cmd = Commander(
            id="cmd3", name="Test Commander", rank="Battalion",
            side=Side.BLUE, unit_id="u3",
        )
        from app.agents.base_commander import BaseCommander
        bc = BaseCommander(commander=cmd, llm_config={}, difficulty="EASY")
        prompt = bc._build_cached_system_prompt()
        assert "cautious" in prompt.lower()
