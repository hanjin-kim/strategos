from __future__ import annotations
import json
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from app.models.domain import Side, UnitType, UnitSize, UnitStatus, HexCoord, Unit, Force, TerrainHex, TerrainType
from app.models.simulation import TurnResult, CombatOutcome, MovementResult, CombatResult
from app.models.narrative import TurnNarrative
from app.agents.adjudicator import Adjudicator
from app.memory.replay_store import ReplayStore
from app.engine.game_state import GameState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_unit(uid: str, side: Side, q: int = 0, r: int = 0, status: UnitStatus = UnitStatus.ACTIVE, strength: float = 1.0) -> Unit:
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


def make_game_state() -> GameState:
    gs = GameState()
    gs.turn = 1
    gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0)
    gs.units["blue2"] = make_unit("blue2", Side.BLUE, 1, 0)
    gs.units["red1"] = make_unit("red1", Side.RED, 2, 0)
    gs.units["red2"] = make_unit("red2", Side.RED, 3, 0)
    gs.forces[Side.BLUE] = Force(side=Side.BLUE, name="Blue", unit_ids=["blue1", "blue2"])
    gs.forces[Side.RED] = Force(side=Side.RED, name="Red", unit_ids=["red1", "red2"])
    return gs


def make_turn_result(turn: int = 1, combats=None, movements=None, destroyed=None) -> TurnResult:
    return TurnResult(
        turn=turn,
        movements=movements or [],
        combats=combats or [],
        destroyed_units=destroyed or [],
    )


def make_combat_outcome(attacker_id="blue1", defender_id="red1") -> CombatOutcome:
    return CombatOutcome(
        attacker_id=attacker_id,
        defender_id=defender_id,
        hex_coord=HexCoord(q=2, r=0),
        force_ratio=1.5,
        die_roll=4,
        result=CombatResult.DEFENDER_RETREAT,
        attacker_losses=0.1,
        defender_losses=0.3,
        defender_retreat_hexes=1,
    )


def make_movement_result(unit_id="blue1") -> MovementResult:
    return MovementResult(
        unit_id=unit_id,
        path=[HexCoord(q=0, r=0), HexCoord(q=1, r=0)],
        final_position=HexCoord(q=1, r=0),
        movement_spent=1,
        remaining_mp=1,
    )


# ---------------------------------------------------------------------------
# 1. Adjudicator instantiation
# ---------------------------------------------------------------------------

def test_adjudicator_no_api_key_client_is_none():
    adj = Adjudicator({})
    assert adj._client is None


def test_adjudicator_with_empty_api_key_client_is_none():
    adj = Adjudicator({"api_key": "", "model": "qwen-plus"})
    assert adj._client is None


def test_adjudicator_with_api_key_creates_client():
    adj = Adjudicator({"api_key": "test-key", "base_url": "https://example.com", "model": "qwen-plus"})
    assert adj._client is not None


def test_adjudicator_model_default():
    adj = Adjudicator({})
    assert adj._model == "qwen-plus"


def test_adjudicator_model_custom():
    adj = Adjudicator({"model": "gpt-4"})
    assert adj._model == "gpt-4"


# ---------------------------------------------------------------------------
# 2. generate_narrative without LLM client -> fallback
# ---------------------------------------------------------------------------

def test_generate_narrative_no_client_returns_fallback():
    adj = Adjudicator({})
    gs = make_game_state()
    tr = make_turn_result(turn=1)
    result = adj.generate_narrative(tr, gs)
    assert isinstance(result, TurnNarrative)
    assert result.turn == 1


# ---------------------------------------------------------------------------
# 3. _fallback_narrative structure
# ---------------------------------------------------------------------------

def test_fallback_narrative_empty_turn():
    adj = Adjudicator({})
    gs = make_game_state()
    tr = make_turn_result(turn=3)
    result = adj._fallback_narrative(tr, gs)
    assert result.turn == 3
    assert "Turn 3" in result.summary
    assert "quiet turn" in result.summary
    assert result.combat_reports == []
    assert result.key_events == []
    assert result.movement_summary == "No movement."


def test_fallback_narrative_with_combats():
    adj = Adjudicator({})
    gs = make_game_state()
    combat = make_combat_outcome()
    tr = make_turn_result(turn=2, combats=[combat])
    result = adj._fallback_narrative(tr, gs)
    assert "1 engagements occurred" in result.summary
    assert len(result.combat_reports) == 1
    assert "blue1" in result.combat_reports[0]
    assert "red1" in result.combat_reports[0]


def test_fallback_narrative_with_movements():
    adj = Adjudicator({})
    gs = make_game_state()
    mv = make_movement_result()
    tr = make_turn_result(turn=2, movements=[mv])
    result = adj._fallback_narrative(tr, gs)
    assert "1 units moved" in result.summary
    assert "1 movement(s) executed" in result.movement_summary


def test_fallback_narrative_with_destroyed_units():
    adj = Adjudicator({})
    gs = make_game_state()
    tr = make_turn_result(turn=2, destroyed=["red1"])
    result = adj._fallback_narrative(tr, gs)
    assert "1 units destroyed" in result.summary
    assert "Unit red1 destroyed" in result.key_events


def test_fallback_narrative_strategic_analysis_blue_advantage():
    adj = Adjudicator({})
    gs = make_game_state()
    # Destroy all RED units
    gs.units["red1"] = make_unit("red1", Side.RED, 2, 0, status=UnitStatus.DESTROYED)
    gs.units["red2"] = make_unit("red2", Side.RED, 3, 0, status=UnitStatus.DESTROYED)
    tr = make_turn_result(turn=1)
    result = adj._fallback_narrative(tr, gs)
    assert "BLUE holds numerical advantage" in result.strategic_analysis


def test_fallback_narrative_strategic_analysis_red_advantage():
    adj = Adjudicator({})
    gs = make_game_state()
    # Destroy all BLUE units
    gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0, status=UnitStatus.DESTROYED)
    gs.units["blue2"] = make_unit("blue2", Side.BLUE, 1, 0, status=UnitStatus.DESTROYED)
    tr = make_turn_result(turn=1)
    result = adj._fallback_narrative(tr, gs)
    assert "RED holds numerical advantage" in result.strategic_analysis


def test_fallback_narrative_strategic_analysis_even():
    adj = Adjudicator({})
    gs = make_game_state()
    tr = make_turn_result(turn=1)
    result = adj._fallback_narrative(tr, gs)
    assert "evenly matched" in result.strategic_analysis


# ---------------------------------------------------------------------------
# 4. _parse_narrative
# ---------------------------------------------------------------------------

def test_parse_narrative_valid_json():
    adj = Adjudicator({})
    data = {
        "summary": "Heavy fighting on the eastern front.",
        "combat_reports": ["Alpha attacked Bravo: victory"],
        "movement_summary": "Two battalions advanced.",
        "strategic_analysis": "BLUE holds the advantage.",
        "key_events": ["Bravo destroyed"],
    }
    result = adj._parse_narrative(json.dumps(data), turn=5)
    assert result.turn == 5
    assert result.summary == "Heavy fighting on the eastern front."
    assert result.combat_reports == ["Alpha attacked Bravo: victory"]
    assert result.movement_summary == "Two battalions advanced."
    assert result.strategic_analysis == "BLUE holds the advantage."
    assert result.key_events == ["Bravo destroyed"]


def test_parse_narrative_with_markdown_json_block():
    adj = Adjudicator({})
    data = {"summary": "Quiet turn.", "combat_reports": [], "movement_summary": "", "strategic_analysis": "", "key_events": []}
    text = f"```json\n{json.dumps(data)}\n```"
    result = adj._parse_narrative(text, turn=2)
    assert result.turn == 2
    assert result.summary == "Quiet turn."


def test_parse_narrative_with_plain_code_block():
    adj = Adjudicator({})
    data = {"summary": "Assault repelled.", "combat_reports": [], "movement_summary": "", "strategic_analysis": "", "key_events": []}
    text = f"```\n{json.dumps(data)}\n```"
    result = adj._parse_narrative(text, turn=3)
    assert result.summary == "Assault repelled."


def test_parse_narrative_malformed_json_graceful_fallback():
    adj = Adjudicator({})
    result = adj._parse_narrative("This is not JSON at all!!!", turn=7)
    assert result.turn == 7
    assert "This is not JSON at all!!!" in result.summary


def test_parse_narrative_partial_json_uses_defaults():
    adj = Adjudicator({})
    data = {"summary": "Partial data only."}
    result = adj._parse_narrative(json.dumps(data), turn=4)
    assert result.summary == "Partial data only."
    assert result.combat_reports == []
    assert result.key_events == []


# ---------------------------------------------------------------------------
# 5. _build_narrative_prompt
# ---------------------------------------------------------------------------

def test_build_narrative_prompt_contains_turn():
    adj = Adjudicator({})
    gs = make_game_state()
    tr = make_turn_result(turn=5)
    prompt = adj._build_narrative_prompt(tr, gs)
    data = json.loads(prompt)
    assert data["turn"] == 5


def test_build_narrative_prompt_contains_unit_counts():
    adj = Adjudicator({})
    gs = make_game_state()
    tr = make_turn_result(turn=1)
    prompt = adj._build_narrative_prompt(tr, gs)
    data = json.loads(prompt)
    assert data["blue_active"] == 2
    assert data["red_active"] == 2


def test_build_narrative_prompt_excludes_destroyed():
    adj = Adjudicator({})
    gs = make_game_state()
    gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0, status=UnitStatus.DESTROYED)
    tr = make_turn_result(turn=1)
    prompt = adj._build_narrative_prompt(tr, gs)
    data = json.loads(prompt)
    assert data["blue_active"] == 1


def test_build_narrative_prompt_includes_combat_details():
    adj = Adjudicator({})
    gs = make_game_state()
    combat = make_combat_outcome()
    tr = make_turn_result(turn=1, combats=[combat])
    prompt = adj._build_narrative_prompt(tr, gs)
    data = json.loads(prompt)
    assert len(data["combat_details"]) == 1
    assert data["combat_details"][0]["attacker"] == "blue1"
    assert data["combat_details"][0]["defender"] == "red1"


# ---------------------------------------------------------------------------
# 6. TurnNarrative model validation
# ---------------------------------------------------------------------------

def test_turn_narrative_defaults():
    tn = TurnNarrative(turn=1)
    assert tn.summary == ""
    assert tn.combat_reports == []
    assert tn.movement_summary == ""
    assert tn.strategic_analysis == ""
    assert tn.key_events == []


def test_turn_narrative_is_frozen():
    tn = TurnNarrative(turn=1, summary="test")
    with pytest.raises(Exception):
        tn.summary = "modified"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 7. TurnResult.narrative field
# ---------------------------------------------------------------------------

def test_turn_result_narrative_default_empty():
    tr = TurnResult(turn=1)
    assert tr.narrative == ""


def test_turn_result_narrative_can_be_set():
    tr = TurnResult(turn=1, narrative="Turn 1 summary.")
    assert tr.narrative == "Turn 1 summary."


# ---------------------------------------------------------------------------
# 8. ReplayStore narrative save/load roundtrip
# ---------------------------------------------------------------------------

def test_replay_store_save_and_get_narrative():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        store = ReplayStore(f.name)
        sim_id = store.create_simulation("test_scenario")
        narrative_json = json.dumps({"summary": "Big battle.", "turn": 1})
        store.save_narrative(sim_id, 1, narrative_json)
        result = store.get_narrative(sim_id, 1)
        assert result is not None
        data = json.loads(result)
        assert data["summary"] == "Big battle."


def test_replay_store_get_narrative_missing_returns_none():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        store = ReplayStore(f.name)
        sim_id = store.create_simulation("test_scenario")
        result = store.get_narrative(sim_id, 99)
        assert result is None


def test_replay_store_save_narrative_replace():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        store = ReplayStore(f.name)
        sim_id = store.create_simulation("test_scenario")
        store.save_narrative(sim_id, 1, json.dumps({"summary": "First version."}))
        store.save_narrative(sim_id, 1, json.dumps({"summary": "Updated version."}))
        result = store.get_narrative(sim_id, 1)
        data = json.loads(result)
        assert data["summary"] == "Updated version."


# ---------------------------------------------------------------------------
# 9. generate_narrative with mocked LLM
# ---------------------------------------------------------------------------

def test_generate_narrative_llm_success():
    adj = Adjudicator({"api_key": "test-key", "base_url": "https://example.com"})
    response_data = {
        "summary": "Fierce combat ensued.",
        "combat_reports": ["BLUE alpha routed RED bravo."],
        "movement_summary": "Three advances.",
        "strategic_analysis": "BLUE gaining ground.",
        "key_events": ["RED bravo destroyed"],
    }
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(response_data)
    adj._client = MagicMock()
    adj._client.chat.completions.create.return_value = mock_response

    gs = make_game_state()
    tr = make_turn_result(turn=2)
    result = adj.generate_narrative(tr, gs)

    assert result.summary == "Fierce combat ensued."
    assert result.combat_reports == ["BLUE alpha routed RED bravo."]
    assert result.turn == 2


def test_generate_narrative_llm_failure_falls_back():
    adj = Adjudicator({"api_key": "test-key", "base_url": "https://example.com"})
    adj._client = MagicMock()
    adj._client.chat.completions.create.side_effect = Exception("Network error")

    gs = make_game_state()
    tr = make_turn_result(turn=3)
    result = adj.generate_narrative(tr, gs)

    assert isinstance(result, TurnNarrative)
    assert result.turn == 3


# ---------------------------------------------------------------------------
# 10. TurnManager with adjudicator=None doesn't break
# ---------------------------------------------------------------------------

def test_turn_manager_adjudicator_none_no_effect():
    """Adjudicator=None in TurnManager produces TurnResult with empty narrative."""
    from app.engine.turn_manager import TurnManager
    from app.engine.game_state import GameState
    from app.engine.constraint_engine import ConstraintEngine
    from app.engine.combat_resolver import CombatResolver
    from app.engine.movement_engine import MovementEngine
    gs = GameState()
    gs.turn = 0
    gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0)
    gs.units["red1"] = make_unit("red1", Side.RED, 5, 5)
    gs.forces[Side.BLUE] = Force(side=Side.BLUE, name="Blue", unit_ids=["blue1"])
    gs.forces[Side.RED] = Force(side=Side.RED, name="Red", unit_ids=["red1"])
    gs.terrain[HexCoord(q=0, r=0)] = TerrainHex(coord=HexCoord(q=0, r=0), terrain_type=TerrainType.PLAIN, elevation=0)
    gs.terrain[HexCoord(q=5, r=5)] = TerrainHex(coord=HexCoord(q=5, r=5), terrain_type=TerrainType.PLAIN, elevation=0)

    tm = TurnManager(
        game_state=gs,
        agents={},
        constraint_engine=ConstraintEngine(),
        combat_resolver=CombatResolver(),
        movement_engine=MovementEngine(),
        adjudicator=None,
    )
    result = tm._run_turn(1)
    assert result.narrative == ""
