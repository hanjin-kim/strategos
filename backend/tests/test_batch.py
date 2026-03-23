from __future__ import annotations

import random
import uuid

import pytest

from app.agents.rule_based_fallback import RuleBasedFallback
from app.batch.batch_runner import BatchResult, BatchRunner, RunResult
from app.batch.parameter_set import (
    ParameterSet,
    apply_to_scenario,
    generate_parameter_grid,
)
from app.engine.game_state import GameState
from app.models.actions import ActionType
from app.models.domain import HexCoord, Side, UnitStatus


# ---------------------------------------------------------------------------
# Minimal scenario fixture
# ---------------------------------------------------------------------------

def _minimal_scenario(
    blue_pos: dict | None = None,
    red_pos: dict | None = None,
    blue_strength: float = 1.0,
    red_strength: float = 1.0,
) -> dict:
    """A tiny 7-hex scenario with one blue and one red unit."""
    blue_pos = blue_pos or {"q": 0, "r": 0}
    red_pos = red_pos or {"q": 5, "r": 0}

    hexes = [
        {"q": q, "r": 0, "terrain": "PLAIN", "movement_cost": 1, "defense_modifier": 1.0}
        for q in range(-1, 8)
    ]

    return {
        "map": {"hexes": hexes},
        "forces": {
            "BLUE": {
                "name": "Blue Force",
                "units": [
                    {
                        "id": "blue_1",
                        "name": "Blue Bn 1",
                        "type": "INFANTRY",
                        "size": "BATTALION",
                        "position": blue_pos,
                        "strength": blue_strength,
                        "morale": 0.8,
                        "max_movement_points": 3,
                        "attack_power": 10.0,
                        "defense_power": 10.0,
                        "effective_range": 1,
                    }
                ],
                "commanders": [
                    {
                        "id": "blue_tc",
                        "name": "Blue Theater",
                        "rank": "Theater",
                        "unit_id": "blue_1",
                    },
                    {
                        "id": "blue_bn",
                        "name": "Blue Bn Cmd",
                        "rank": "Battalion",
                        "unit_id": "blue_1",
                    },
                ],
            },
            "RED": {
                "name": "Red Force",
                "units": [
                    {
                        "id": "red_1",
                        "name": "Red Bn 1",
                        "type": "INFANTRY",
                        "size": "BATTALION",
                        "position": red_pos,
                        "strength": red_strength,
                        "morale": 0.8,
                        "max_movement_points": 3,
                        "attack_power": 10.0,
                        "defense_power": 10.0,
                        "effective_range": 1,
                    }
                ],
                "commanders": [
                    {
                        "id": "red_tc",
                        "name": "Red Theater",
                        "rank": "Theater",
                        "unit_id": "red_1",
                    },
                    {
                        "id": "red_bn",
                        "name": "Red Bn Cmd",
                        "rank": "Battalion",
                        "unit_id": "red_1",
                    },
                ],
            },
        },
    }


# ---------------------------------------------------------------------------
# ParameterSet creation and serialization
# ---------------------------------------------------------------------------

def test_parameter_set_defaults():
    ps = ParameterSet()
    assert ps.name == "default"
    assert ps.rng_seed == 42
    assert ps.max_turns == 72
    assert ps.use_llm is False
    assert ps.personality_overrides == {}
    assert ps.strength_multipliers == {}
    assert ps.position_overrides == {}
    assert ps.strategy_prompt_suffix == ""


def test_parameter_set_custom_values():
    ps = ParameterSet(
        name="test_run",
        rng_seed=123,
        max_turns=10,
        use_llm=False,
        strength_multipliers={"blue_1": 0.8},
        personality_overrides={"blue_tc": {"aggression": 0.9}},
    )
    assert ps.name == "test_run"
    assert ps.rng_seed == 123
    assert ps.strength_multipliers == {"blue_1": 0.8}
    assert ps.personality_overrides == {"blue_tc": {"aggression": 0.9}}


def test_parameter_set_is_frozen():
    ps = ParameterSet(name="immutable")
    with pytest.raises(Exception):
        ps.name = "changed"  # type: ignore[misc]


def test_parameter_set_serialization():
    ps = ParameterSet(name="serial", rng_seed=7, max_turns=5)
    data = ps.model_dump()
    assert data["name"] == "serial"
    assert data["rng_seed"] == 7
    assert data["max_turns"] == 5
    restored = ParameterSet(**data)
    assert restored == ps


# ---------------------------------------------------------------------------
# apply_to_scenario
# ---------------------------------------------------------------------------

def test_apply_strength_multiplier():
    scenario = _minimal_scenario(blue_strength=1.0)
    params = ParameterSet(strength_multipliers={"blue_1": 0.5})
    result = apply_to_scenario(scenario, params)
    blue_unit = result["forces"]["BLUE"]["units"][0]
    assert blue_unit["strength"] == pytest.approx(0.5)


def test_apply_strength_multiplier_capped_at_1():
    scenario = _minimal_scenario(blue_strength=0.9)
    params = ParameterSet(strength_multipliers={"blue_1": 2.0})
    result = apply_to_scenario(scenario, params)
    blue_unit = result["forces"]["BLUE"]["units"][0]
    assert blue_unit["strength"] == pytest.approx(1.0)


def test_apply_position_override():
    scenario = _minimal_scenario(blue_pos={"q": 0, "r": 0})
    params = ParameterSet(position_overrides={"blue_1": {"q": 3, "r": 0}})
    result = apply_to_scenario(scenario, params)
    blue_unit = result["forces"]["BLUE"]["units"][0]
    assert blue_unit["position"] == {"q": 3, "r": 0}


def test_apply_personality_override():
    scenario = _minimal_scenario()
    params = ParameterSet(personality_overrides={"blue_tc": {"aggression": 0.9, "caution": 0.1}})
    result = apply_to_scenario(scenario, params)
    blue_tc = result["forces"]["BLUE"]["commanders"][0]
    assert blue_tc["personality_traits"]["aggression"] == pytest.approx(0.9)
    assert blue_tc["personality_traits"]["caution"] == pytest.approx(0.1)


def test_apply_to_scenario_original_unchanged():
    scenario = _minimal_scenario(blue_strength=1.0)
    params = ParameterSet(strength_multipliers={"blue_1": 0.3})
    apply_to_scenario(scenario, params)
    # Original must not be modified
    assert scenario["forces"]["BLUE"]["units"][0]["strength"] == pytest.approx(1.0)


def test_apply_unmatched_ids_ignored():
    scenario = _minimal_scenario()
    params = ParameterSet(
        strength_multipliers={"nonexistent_unit": 0.5},
        position_overrides={"nonexistent_unit": {"q": 99, "r": 99}},
        personality_overrides={"nonexistent_cmd": {"aggression": 0.9}},
    )
    result = apply_to_scenario(scenario, params)
    # Should complete without error, originals unchanged
    assert result["forces"]["BLUE"]["units"][0].get("strength", 1.0) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# generate_parameter_grid
# ---------------------------------------------------------------------------

def test_generate_grid_empty_variations():
    base = ParameterSet(name="base", rng_seed=1)
    result = generate_parameter_grid(base, {})
    assert result == [base]


def test_generate_grid_single_axis():
    base = ParameterSet(name="base")
    result = generate_parameter_grid(base, {"rng_seed": [1, 2, 3]})
    assert len(result) == 3
    seeds = [ps.rng_seed for ps in result]
    assert sorted(seeds) == [1, 2, 3]


def test_generate_grid_multi_axis():
    base = ParameterSet(name="base")
    result = generate_parameter_grid(base, {"rng_seed": [1, 2], "max_turns": [5, 10]})
    assert len(result) == 4  # 2 * 2
    combos = [(ps.rng_seed, ps.max_turns) for ps in result]
    assert (1, 5) in combos
    assert (1, 10) in combos
    assert (2, 5) in combos
    assert (2, 10) in combos


def test_generate_grid_names_unique():
    base = ParameterSet(name="base")
    result = generate_parameter_grid(base, {"rng_seed": [10, 20, 30]})
    names = [ps.name for ps in result]
    assert len(set(names)) == 3


# ---------------------------------------------------------------------------
# BatchRunner._execute_single_run (LLM-free, 3 turns)
# ---------------------------------------------------------------------------

def test_single_run_completes():
    scenario = _minimal_scenario()
    runner = BatchRunner(scenario, "test_scenario")
    params = ParameterSet(name="quick", rng_seed=42, max_turns=3)
    result = runner._execute_single_run(0, params)
    assert result.status == "COMPLETED"
    assert result.run_index == 0
    assert result.total_turns <= 3
    assert result.winner in ("BLUE", "RED", "DRAW")
    assert result.reproducibility_level == "DETERMINISTIC"


def test_single_run_execution_time_recorded():
    scenario = _minimal_scenario()
    runner = BatchRunner(scenario, "test_scenario")
    params = ParameterSet(max_turns=3)
    result = runner._execute_single_run(0, params)
    assert result.execution_time_ms >= 0


# ---------------------------------------------------------------------------
# BatchRunner.run_batch — N=3 all complete
# ---------------------------------------------------------------------------

def test_run_batch_three_runs():
    scenario = _minimal_scenario()
    runner = BatchRunner(scenario, "test_scenario")
    params = [ParameterSet(name=f"run_{i}", rng_seed=i, max_turns=3) for i in range(3)]
    batch = runner.run_batch(params)
    assert batch.total_runs == 3
    assert batch.completed_runs == 3
    assert batch.failed_runs == 0
    assert batch.status == "COMPLETED"
    assert len(batch.runs) == 3


def test_run_batch_callback_called():
    scenario = _minimal_scenario()
    runner = BatchRunner(scenario, "test_scenario")
    params = [ParameterSet(name=f"cb_{i}", rng_seed=i, max_turns=3) for i in range(2)]
    calls = []
    runner.run_batch(params, callback=lambda i, total, r: calls.append((i, total)))
    assert len(calls) == 2
    assert calls[0] == (0, 2)
    assert calls[1] == (1, 2)


def test_run_batch_error_recovery():
    """One run fails (bad scenario), others continue."""
    scenario = _minimal_scenario()
    runner = BatchRunner(scenario, "test_scenario")

    # Good params
    good1 = ParameterSet(name="good1", rng_seed=1, max_turns=3)
    good2 = ParameterSet(name="good2", rng_seed=2, max_turns=3)

    # Patch _execute_single_run to fail on run_index=1
    original = runner._execute_single_run

    def patched(run_index, params):
        if run_index == 1:
            raise RuntimeError("Simulated failure")
        return original(run_index, params)

    runner._execute_single_run = patched

    batch = runner.run_batch([good1, good2])
    assert batch.total_runs == 2
    assert batch.completed_runs == 1
    assert batch.failed_runs == 1
    assert batch.status == "PARTIAL"
    failed = [r for r in batch.runs if r.status == "FAILED"]
    assert len(failed) == 1
    assert "Simulated failure" in failed[0].error_message


def test_run_batch_batch_id_assigned():
    scenario = _minimal_scenario()
    runner = BatchRunner(scenario)
    batch = runner.run_batch([ParameterSet(max_turns=3)], batch_id="custom_id")
    assert batch.batch_id == "custom_id"


# ---------------------------------------------------------------------------
# BatchRunner._determine_winner
# ---------------------------------------------------------------------------

def test_determine_winner_blue_wins():
    scenario = _minimal_scenario()
    runner = BatchRunner(scenario)
    game_state = GameState(scenario)
    game_state.update_unit("red_1", status=UnitStatus.DESTROYED)
    assert runner._determine_winner(game_state) == "BLUE"


def test_determine_winner_red_wins():
    scenario = _minimal_scenario()
    runner = BatchRunner(scenario)
    game_state = GameState(scenario)
    game_state.update_unit("blue_1", status=UnitStatus.DESTROYED)
    assert runner._determine_winner(game_state) == "RED"


def test_determine_winner_draw_both_destroyed():
    scenario = _minimal_scenario()
    runner = BatchRunner(scenario)
    game_state = GameState(scenario)
    game_state.update_unit("blue_1", status=UnitStatus.DESTROYED)
    game_state.update_unit("red_1", status=UnitStatus.DESTROYED)
    assert runner._determine_winner(game_state) == "DRAW"


def test_determine_winner_draw_balanced():
    scenario = _minimal_scenario()
    runner = BatchRunner(scenario)
    game_state = GameState(scenario)
    # Both at equal strength ~1.0 -> DRAW (neither 1.5x the other)
    assert runner._determine_winner(game_state) == "DRAW"


# ---------------------------------------------------------------------------
# BatchRunner.estimate_cost
# ---------------------------------------------------------------------------

def test_estimate_cost_no_llm_runs():
    scenario = _minimal_scenario()
    runner = BatchRunner(scenario)
    params = [ParameterSet(use_llm=False, max_turns=5) for _ in range(4)]
    cost = runner.estimate_cost(params)
    assert cost["total_runs"] == 4
    assert cost["llm_runs"] == 0
    assert cost["free_runs"] == 4
    assert cost["estimated_llm_calls"] == 0
    assert cost["estimated_cost_usd"] == 0.0


def test_estimate_cost_mixed_runs():
    scenario = _minimal_scenario()
    runner = BatchRunner(scenario)
    params = [
        ParameterSet(use_llm=True, max_turns=10),
        ParameterSet(use_llm=False, max_turns=10),
    ]
    cost = runner.estimate_cost(params)
    assert cost["total_runs"] == 2
    assert cost["llm_runs"] == 1
    assert cost["free_runs"] == 1
    assert cost["estimated_llm_calls"] > 0
    assert cost["estimated_cost_usd"] > 0.0


# ---------------------------------------------------------------------------
# RunResult / BatchResult model validation
# ---------------------------------------------------------------------------

def test_run_result_defaults():
    r = RunResult(run_index=0, parameter_set_name="x", rng_seed=1)
    assert r.status == "COMPLETED"
    assert r.winner == ""
    assert r.reproducibility_level == "DETERMINISTIC"


def test_batch_result_defaults():
    b = BatchResult(batch_id="abc", scenario_name="test", total_runs=5)
    assert b.completed_runs == 0
    assert b.failed_runs == 0
    assert b.status == "PENDING"
    assert b.runs == []


# ---------------------------------------------------------------------------
# Reproducibility: same rng_seed produces same winner
# ---------------------------------------------------------------------------

def test_reproducibility_same_seed():
    scenario = _minimal_scenario()
    runner = BatchRunner(scenario, "repro")
    params = ParameterSet(name="r", rng_seed=99, max_turns=5)
    result1 = runner._execute_single_run(0, params)
    result2 = runner._execute_single_run(1, params)
    assert result1.winner == result2.winner
    assert result1.total_turns == result2.total_turns


def test_reproducibility_different_seeds_may_differ():
    """Different seeds are allowed to produce different results (statistical check)."""
    scenario = _minimal_scenario()
    runner = BatchRunner(scenario)
    results = []
    for seed in range(5):
        r = runner._execute_single_run(seed, ParameterSet(rng_seed=seed * 7 + 1, max_turns=5))
        results.append(r)
    # All should at least complete without error
    for r in results:
        assert r.status == "COMPLETED"


# ---------------------------------------------------------------------------
# RuleBasedFallback personality tests
# ---------------------------------------------------------------------------

def _make_state_with_adjacent_enemy(blue_strength: float = 1.0) -> tuple[GameState, object]:
    """Return (game_state, blue_unit) with enemy at adjacent hex."""
    scenario = {
        "map": {
            "hexes": [
                {"q": q, "r": 0, "terrain": "PLAIN", "movement_cost": 1, "defense_modifier": 1.0}
                for q in range(-2, 6)
            ]
        },
        "forces": {
            "BLUE": {
                "name": "Blue Force",
                "units": [
                    {
                        "id": "blue_1", "name": "B1", "type": "INFANTRY", "size": "BATTALION",
                        "position": {"q": 0, "r": 0},
                        "strength": blue_strength, "morale": 0.8, "max_movement_points": 2,
                        "attack_power": 10.0, "defense_power": 10.0, "effective_range": 1,
                    }
                ],
                "commanders": [{"id": "bc1", "name": "BC1", "rank": "Battalion", "unit_id": "blue_1"}],
            },
            "RED": {
                "name": "Red Force",
                "units": [
                    {
                        "id": "red_1", "name": "R1", "type": "INFANTRY", "size": "BATTALION",
                        "position": {"q": 1, "r": 0},
                        "strength": 1.0, "morale": 0.8, "max_movement_points": 2,
                        "attack_power": 10.0, "defense_power": 10.0, "effective_range": 1,
                    }
                ],
                "commanders": [{"id": "rc1", "name": "RC1", "rank": "Battalion", "unit_id": "red_1"}],
            },
        },
    }
    state = GameState(scenario)
    unit = state.get_unit("blue_1")
    return state, unit


def test_personality_aggression_can_attack():
    """With aggression>0.7 and seeded rng that triggers, should return ATTACK."""
    fallback = RuleBasedFallback()
    state, unit = _make_state_with_adjacent_enemy()
    traits = {"aggression": 0.95}

    # Find a seed that produces rng.random() < 0.95 (very likely; try a few)
    got_attack = False
    for seed in range(50):
        rng = random.Random(seed)
        actions = fallback.decide("bc1", unit, state, rng=rng, personality_traits=traits)
        if actions[0].action_type == ActionType.ATTACK:
            got_attack = True
            break
    assert got_attack, "Expected at least one ATTACK with aggression=0.95 over 50 seeds"


def test_personality_aggression_low_still_defends():
    """With aggression=0.3 (below threshold), should always DEFEND."""
    fallback = RuleBasedFallback()
    state, unit = _make_state_with_adjacent_enemy()
    traits = {"aggression": 0.3}
    rng = random.Random(42)
    for _ in range(10):
        actions = fallback.decide("bc1", unit, state, rng=rng, personality_traits=traits)
        assert actions[0].action_type == ActionType.DEFEND


def test_personality_caution_retreats_when_weak():
    """With caution>0.7 and strength<0.5, should RETREAT (no adjacent enemy)."""
    fallback = RuleBasedFallback()
    state, unit = _make_state_with_adjacent_enemy(blue_strength=0.3)
    # Move red away so no adjacent enemy
    state.update_unit("red_1", position=HexCoord(q=5, r=0))
    unit = state.get_unit("blue_1")

    traits = {"caution": 0.9}
    rng = random.Random(42)
    actions = fallback.decide("bc1", unit, state, rng=rng, personality_traits=traits)
    assert actions[0].action_type == ActionType.RETREAT


def test_personality_none_preserves_existing_behavior_defend():
    """personality_traits=None + rng=None -> same as before (enemy adjacent -> DEFEND)."""
    fallback = RuleBasedFallback()
    state, unit = _make_state_with_adjacent_enemy()
    actions = fallback.decide("bc1", unit, state)
    assert actions[0].action_type == ActionType.DEFEND


def test_personality_none_preserves_existing_behavior_hold():
    """personality_traits=None -> default HOLD when no enemy."""
    fallback = RuleBasedFallback()
    state, unit = _make_state_with_adjacent_enemy()
    state.update_unit("red_1", position=HexCoord(q=5, r=0))
    unit = state.get_unit("blue_1")
    actions = fallback.decide("bc1", unit, state)
    assert actions[0].action_type == ActionType.HOLD


def test_personality_rng_is_seeded_random():
    """Verify rng parameter uses random.Random (not global random)."""
    fallback = RuleBasedFallback()
    state, unit = _make_state_with_adjacent_enemy()
    traits = {"aggression": 0.95}
    rng1 = random.Random(123)
    rng2 = random.Random(123)
    result1 = fallback.decide("bc1", unit, state, rng=rng1, personality_traits=traits)
    # Re-fetch unit (state may differ if attack modifies state — but decide() is read-only)
    state2, unit2 = _make_state_with_adjacent_enemy()
    result2 = fallback.decide("bc1", unit2, state2, rng=rng2, personality_traits=traits)
    assert result1[0].action_type == result2[0].action_type
