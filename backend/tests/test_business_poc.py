"""Tests for the STRATEGOS Business Competition PoC."""
from __future__ import annotations

import json
import os

import pytest

from app.agents.base_commander import DOCTRINE_PROMPT, BaseCommander
from app.batch.analysis_engine import AnalysisEngine
from app.batch.batch_runner import BatchRunner
from app.batch.parameter_set import ParameterSet
from app.batch.report_generator import ReportGenerator
from app.engine.game_state import GameState
from app.models.domain import Commander, Side
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


def _minimal_commander(rank: str = "Battalion", side: Side = Side.BLUE) -> Commander:
    return Commander(id="test_cmd", name="Test", side=side, rank=rank, unit_id="unit_1")


# ---------------------------------------------------------------------------
# 1. Scenario loads as GameState
# ---------------------------------------------------------------------------

def test_ev_battery_scenario_loads():
    scenario = _load_scenario()
    gs = GameState(scenario)
    assert len(gs.units) > 0
    assert len(gs.terrain) > 0
    assert len(gs.commanders) > 0


# ---------------------------------------------------------------------------
# 2. Unit counts: BLUE 6, RED 6
# ---------------------------------------------------------------------------

def test_scenario_blue_unit_count():
    scenario = _load_scenario()
    gs = GameState(scenario)
    blue_units = gs.get_units_by_side(Side.BLUE)
    assert len(blue_units) == 6


def test_scenario_red_unit_count():
    scenario = _load_scenario()
    gs = GameState(scenario)
    red_units = gs.get_units_by_side(Side.RED)
    assert len(red_units) == 6


# ---------------------------------------------------------------------------
# 3. Commander counts: BLUE 7, RED 7
# ---------------------------------------------------------------------------

def test_scenario_blue_commander_count():
    scenario = _load_scenario()
    gs = GameState(scenario)
    blue_cmds = [c for c in gs.commanders.values() if c.side == Side.BLUE]
    assert len(blue_cmds) == 7


def test_scenario_red_commander_count():
    scenario = _load_scenario()
    gs = GameState(scenario)
    red_cmds = [c for c in gs.commanders.values() if c.side == Side.RED]
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
# 6. doctrine_override flows through to _build_cached_system_prompt
# ---------------------------------------------------------------------------

def test_doctrine_override_used_in_system_prompt():
    cmd = _minimal_commander()
    llm_config = {"api_key": "", "base_url": "", "model": ""}
    agent = BaseCommander.__new__(BaseCommander)
    # Call __init__ directly via super-safe instantiation
    BaseCommander.__init__(
        agent,
        commander=cmd,
        llm_config=llm_config,
        doctrine_override="CUSTOM DOCTRINE",
    )
    prompt = agent._build_cached_system_prompt()
    assert "CUSTOM DOCTRINE" in prompt


# ---------------------------------------------------------------------------
# 7. doctrine_override=None uses default DOCTRINE_PROMPT (backward compat)
# ---------------------------------------------------------------------------

def test_doctrine_override_none_uses_default():
    cmd = _minimal_commander()
    llm_config = {"api_key": "", "base_url": "", "model": ""}
    agent = BaseCommander.__new__(BaseCommander)
    BaseCommander.__init__(
        agent,
        commander=cmd,
        llm_config=llm_config,
        doctrine_override=None,
    )
    prompt = agent._build_cached_system_prompt()
    assert DOCTRINE_PROMPT in prompt


# ---------------------------------------------------------------------------
# 8. BatchRunner with doctrine_override creates agents with business doctrine
# ---------------------------------------------------------------------------

def test_batch_runner_doctrine_override_propagates():
    scenario = _load_scenario()
    runner = BatchRunner(scenario, "ev_test", doctrine_override=BUSINESS_DOCTRINE)
    assert runner.doctrine_override == BUSINESS_DOCTRINE

    from app.engine.game_state import GameState as GS
    from app.graph.relationship_graph import RelationshipGraph
    from app.graph.graph_tools import GraphTools

    gs = GS(scenario)
    rg = RelationshipGraph()
    rg.load_from_scenario(scenario, gs)
    gt = GraphTools(rg)

    llm_config = {"api_key": "", "base_url": "", "model": ""}
    agents = runner._create_agents(gs, llm_config, gt)

    # Every agent should have doctrine_override set
    for agent in agents.values():
        assert agent._doctrine_override == BUSINESS_DOCTRINE
        prompt = agent._build_cached_system_prompt()
        assert "BUSINESS STRATEGY DOCTRINE" in prompt


# ---------------------------------------------------------------------------
# 9. Single run with business scenario completes (max_turns=3)
# ---------------------------------------------------------------------------

def test_single_run_business_scenario_completes():
    scenario = _load_scenario()
    runner = BatchRunner(scenario, "ev_test", doctrine_override=BUSINESS_DOCTRINE)
    params = ParameterSet(name="quick", rng_seed=42, max_turns=3, use_llm=False)
    result = runner._execute_single_run(0, params)
    assert result.status == "COMPLETED"
    assert result.total_turns <= 3
    assert result.winner in ("BLUE", "RED", "DRAW")


# ---------------------------------------------------------------------------
# 10. Batch run N=3 with business scenario all complete
# ---------------------------------------------------------------------------

def test_batch_run_n3_all_complete():
    scenario = _load_scenario()
    runner = BatchRunner(scenario, "ev_test", doctrine_override=BUSINESS_DOCTRINE)
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
    scenario = _load_scenario()
    runner = BatchRunner(scenario, "ev_test", doctrine_override=BUSINESS_DOCTRINE)
    param_sets = [ParameterSet(name=f"r{i}", rng_seed=i, max_turns=3, use_llm=False) for i in range(3)]
    batch = runner.run_batch(param_sets)

    # Build run dicts manually (as OutcomeCollector would store them)
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
