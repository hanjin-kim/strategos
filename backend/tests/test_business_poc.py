"""Tests for the STRATEGOS Business Competition PoC — business-independent stack."""
from __future__ import annotations

import json
import os

import pytest

from app.batch.analysis_engine import AnalysisEngine
from app.batch.batch_runner import BatchRunner
from app.batch.parameter_set import ParameterSet
from app.batch.report_generator import ReportGenerator
from app.domains.business.state import BusinessState
from app.domains.business.agents import BusinessAgent, BusinessCEO
from app.prompts.business_doctrine import BUSINESS_DOCTRINE, BUSINESS_PERSONA_TEMPLATES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCENARIO_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../scripts/seed_scenarios/ev_battery_market.json",
)


def _load_scenario() -> dict:
    with open(SCENARIO_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Scenario loads as BusinessState
# ---------------------------------------------------------------------------

def test_ev_battery_scenario_loads():
    scenario = _load_scenario()
    state = BusinessState(scenario)
    assert len(state.units) > 0
    assert len(state.market_map) > 0
    assert len(state.commanders) > 0


# ---------------------------------------------------------------------------
# 2. Unit counts: BLUE 6, RED 6
# ---------------------------------------------------------------------------

def test_scenario_blue_unit_count():
    scenario = _load_scenario()
    state = BusinessState(scenario)
    blue_units = state.get_units_by_side("BLUE")
    assert len(blue_units) == 6


def test_scenario_red_unit_count():
    scenario = _load_scenario()
    state = BusinessState(scenario)
    red_units = state.get_units_by_side("RED")
    assert len(red_units) == 6


# ---------------------------------------------------------------------------
# 3. Commander counts: BLUE 7, RED 7
# ---------------------------------------------------------------------------

def test_scenario_blue_commander_count():
    scenario = _load_scenario()
    state = BusinessState(scenario)
    blue_cmds = [c for c in state.commanders.values() if c["side"] == "BLUE"]
    assert len(blue_cmds) == 7


def test_scenario_red_commander_count():
    scenario = _load_scenario()
    state = BusinessState(scenario)
    red_cmds = [c for c in state.commanders.values() if c["side"] == "RED"]
    assert len(red_cmds) == 7


# ---------------------------------------------------------------------------
# 4. BUSINESS_DOCTRINE is non-empty string
# ---------------------------------------------------------------------------

def test_business_doctrine_is_nonempty_string():
    assert isinstance(BUSINESS_DOCTRINE, str)
    assert len(BUSINESS_DOCTRINE) > 100


# ---------------------------------------------------------------------------
# 5. BUSINESS_PERSONA_TEMPLATES has all 3 ranks
# ---------------------------------------------------------------------------

def test_business_persona_templates_has_all_ranks():
    assert "Theater" in BUSINESS_PERSONA_TEMPLATES
    assert "Division" in BUSINESS_PERSONA_TEMPLATES
    assert "Battalion" in BUSINESS_PERSONA_TEMPLATES


# ---------------------------------------------------------------------------
# 6. BusinessAgent doctrine flows through to _build_persona
# ---------------------------------------------------------------------------

def test_doctrine_in_business_agent():
    cmd = {
        "id": "test_cmd", "name": "Test Commander", "side": "BLUE",
        "rank": "Battalion", "unit_id": "unit_1", "personality_traits": {},
    }
    agent = BusinessAgent(cmd, {"api_key": "", "base_url": "", "model": ""}, doctrine="CUSTOM DOCTRINE")
    assert agent._doctrine == "CUSTOM DOCTRINE"


# ---------------------------------------------------------------------------
# 7. BusinessCEO has correct rank detection
# ---------------------------------------------------------------------------

def test_business_ceo_is_ceo_type():
    cmd = {
        "id": "ceo1", "name": "CEO Test", "side": "BLUE",
        "rank": "Theater", "unit_id": "hq_unit", "personality_traits": {},
    }
    ceo = BusinessCEO(cmd, {"api_key": "", "base_url": "", "model": ""})
    assert isinstance(ceo, BusinessAgent)
    assert isinstance(ceo, BusinessCEO)


# ---------------------------------------------------------------------------
# 8. BatchRunner with doctrine_override creates agents
# ---------------------------------------------------------------------------

def test_batch_runner_doctrine_override_propagates():
    scenario = _load_scenario()
    runner = BatchRunner(scenario, "ev_test", doctrine_override=BUSINESS_DOCTRINE)
    assert runner.doctrine_override == BUSINESS_DOCTRINE


# ---------------------------------------------------------------------------
# 9. Single run with business scenario completes (max_turns=3)
# ---------------------------------------------------------------------------

def test_single_run_business_scenario_completes():
    import app.domains.business  # noqa: F401
    scenario = _load_scenario()
    runner = BatchRunner(scenario, "ev_test")
    params = ParameterSet(name="quick", rng_seed=42, max_turns=3, use_llm=False)
    result = runner._execute_single_run(0, params)
    assert result.status == "COMPLETED"
    assert result.total_turns <= 3
    assert result.winner in ("BLUE", "RED", "DRAW")


# ---------------------------------------------------------------------------
# 10. Batch run N=3 with business scenario all complete
# ---------------------------------------------------------------------------

def test_batch_run_n3_all_complete():
    import app.domains.business  # noqa: F401
    scenario = _load_scenario()
    runner = BatchRunner(scenario, "ev_test")
    param_sets = [ParameterSet(name=f"run_{i}", rng_seed=i, max_turns=3, use_llm=False) for i in range(3)]
    batch = runner.run_batch(param_sets)
    assert batch.total_runs == 3
    assert batch.completed_runs == 3
    assert batch.failed_runs == 0
    assert batch.status == "COMPLETED"


# ---------------------------------------------------------------------------
# 11. Report generates with business batch results
# ---------------------------------------------------------------------------

def test_report_generates_with_business_batch():
    import app.domains.business  # noqa: F401
    scenario = _load_scenario()
    runner = BatchRunner(scenario, "ev_test")
    param_sets = [ParameterSet(name=f"r{i}", rng_seed=i, max_turns=3, use_llm=False) for i in range(3)]
    batch = runner.run_batch(param_sets)

    runs = [
        {
            "status": r.status,
            "winner": r.winner,
            "total_turns": r.total_turns,
            "blue_units_remaining": r.blue_units_remaining,
            "red_units_remaining": r.red_units_remaining,
            "blue_avg_strength": r.blue_avg_strength,
            "red_avg_strength": r.red_avg_strength,
            "rng_seed": r.rng_seed,
            "parameter_set_name": r.parameter_set_name,
        }
        for r in batch.runs
    ]

    engine = AnalysisEngine()
    analysis = engine.analyze(runs)
    assert analysis["runs_analyzed"] == 3

    reporter = ReportGenerator()
    report = reporter.generate_report(analysis, {"scenario": scenario["name"], "domain": "business"})
    assert isinstance(report, dict)

    md = reporter.to_markdown(report)
    assert isinstance(md, str)
    assert len(md) > 0
