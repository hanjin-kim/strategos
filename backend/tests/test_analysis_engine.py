from __future__ import annotations
import pytest
from app.batch.analysis_engine import AnalysisEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_run(
    run_index=0,
    status="COMPLETED",
    winner="BLUE",
    total_turns=30,
    blue_units_remaining=5,
    red_units_remaining=2,
    blue_avg_strength=0.8,
    red_avg_strength=0.4,
    execution_time_ms=500,
    parameter_set_name="default",
):
    return {
        "run_index": run_index,
        "status": status,
        "winner": winner,
        "total_turns": total_turns,
        "blue_units_remaining": blue_units_remaining,
        "red_units_remaining": red_units_remaining,
        "blue_avg_strength": blue_avg_strength,
        "red_avg_strength": red_avg_strength,
        "execution_time_ms": execution_time_ms,
        "parameter_set_name": parameter_set_name,
    }


# ---------------------------------------------------------------------------
# analyze() — top-level
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_empty_runs_returns_error(self):
        engine = AnalysisEngine()
        result = engine.analyze([])
        assert result["error"] == "No completed runs to analyze"
        assert result["runs_analyzed"] == 0

    def test_all_failed_runs_returns_error(self):
        engine = AnalysisEngine()
        runs = [make_run(status="FAILED"), make_run(status="FAILED")]
        result = engine.analyze(runs)
        assert "error" in result
        assert result["runs_analyzed"] == 0

    def test_completed_runs_returns_all_sections(self):
        engine = AnalysisEngine()
        runs = [make_run(i) for i in range(5)]
        result = engine.analyze(runs)
        assert result["runs_analyzed"] == 5
        assert "win_rates" in result
        assert "casualty_analysis" in result
        assert "duration_analysis" in result
        assert "sensitivity" in result
        assert "classification" in result
        assert "divergence_points" in result

    def test_mixed_status_only_counts_completed(self):
        engine = AnalysisEngine()
        runs = [make_run(0, status="COMPLETED"), make_run(1, status="FAILED")]
        result = engine.analyze(runs)
        assert result["runs_analyzed"] == 1

    def test_full_pipeline_realistic_data(self):
        engine = AnalysisEngine()
        runs = [
            make_run(0, winner="BLUE", total_turns=20, parameter_set_name="aggressive"),
            make_run(1, winner="RED", total_turns=60, parameter_set_name="defensive"),
            make_run(2, winner="DRAW", total_turns=72, parameter_set_name="aggressive"),
            make_run(3, winner="BLUE", total_turns=15, parameter_set_name="defensive"),
            make_run(4, winner="RED", total_turns=45, parameter_set_name="aggressive"),
        ]
        result = engine.analyze(runs)
        assert result["runs_analyzed"] == 5
        wr = result["win_rates"]
        assert wr["blue_wins"] == 2
        assert wr["red_wins"] == 2
        assert wr["draws"] == 1


# ---------------------------------------------------------------------------
# calculate_win_rates
# ---------------------------------------------------------------------------

class TestCalculateWinRates:
    def test_all_blue_wins(self):
        engine = AnalysisEngine()
        runs = [make_run(winner="BLUE") for _ in range(4)]
        result = engine.calculate_win_rates(runs)
        assert result["blue_wins"] == 4
        assert result["red_wins"] == 0
        assert result["draws"] == 0
        assert result["blue_win_rate"] == 1.0
        assert result["red_win_rate"] == 0.0

    def test_all_red_wins(self):
        engine = AnalysisEngine()
        runs = [make_run(winner="RED") for _ in range(3)]
        result = engine.calculate_win_rates(runs)
        assert result["red_wins"] == 3
        assert result["blue_wins"] == 0
        assert result["red_win_rate"] == 1.0

    def test_mixed_outcomes(self):
        engine = AnalysisEngine()
        runs = [
            make_run(winner="BLUE"),
            make_run(winner="RED"),
            make_run(winner="DRAW"),
            make_run(winner="BLUE"),
        ]
        result = engine.calculate_win_rates(runs)
        assert result["blue_wins"] == 2
        assert result["red_wins"] == 1
        assert result["draws"] == 1
        assert result["total"] == 4
        assert result["blue_win_rate"] == 0.5

    def test_all_draws(self):
        engine = AnalysisEngine()
        runs = [make_run(winner="DRAW") for _ in range(5)]
        result = engine.calculate_win_rates(runs)
        assert result["draws"] == 5
        assert result["blue_win_rate"] == 0.0
        assert result["red_win_rate"] == 0.0


# ---------------------------------------------------------------------------
# analyze_casualties
# ---------------------------------------------------------------------------

class TestAnalyzeCasualties:
    def test_stats_calculation(self):
        engine = AnalysisEngine()
        runs = [
            make_run(blue_units_remaining=4, red_units_remaining=2, blue_avg_strength=0.8, red_avg_strength=0.5),
            make_run(blue_units_remaining=6, red_units_remaining=4, blue_avg_strength=0.6, red_avg_strength=0.7),
        ]
        result = engine.analyze_casualties(runs)
        assert result["blue_units_remaining"]["mean"] == 5.0
        assert result["blue_units_remaining"]["min"] == 4
        assert result["blue_units_remaining"]["max"] == 6
        assert result["blue_units_remaining"]["stdev"] > 0

    def test_single_run_stdev_is_zero(self):
        engine = AnalysisEngine()
        runs = [make_run(blue_units_remaining=5)]
        result = engine.analyze_casualties(runs)
        assert result["blue_units_remaining"]["stdev"] == 0
        assert result["blue_units_remaining"]["mean"] == 5.0

    def test_all_sections_present(self):
        engine = AnalysisEngine()
        runs = [make_run()]
        result = engine.analyze_casualties(runs)
        assert "blue_units_remaining" in result
        assert "red_units_remaining" in result
        assert "blue_avg_strength" in result
        assert "red_avg_strength" in result


# ---------------------------------------------------------------------------
# analyze_duration
# ---------------------------------------------------------------------------

class TestAnalyzeDuration:
    def test_turns_and_time_stats(self):
        engine = AnalysisEngine()
        runs = [
            make_run(total_turns=20, execution_time_ms=400),
            make_run(total_turns=40, execution_time_ms=600),
        ]
        result = engine.analyze_duration(runs)
        assert result["turns"]["mean"] == 30.0
        assert result["turns"]["min"] == 20
        assert result["turns"]["max"] == 40
        assert result["execution_ms"]["total"] == 1000
        assert result["execution_ms"]["mean"] == 500.0

    def test_single_run_stdev_is_zero(self):
        engine = AnalysisEngine()
        runs = [make_run(total_turns=25)]
        result = engine.analyze_duration(runs)
        assert result["turns"]["stdev"] == 0
        assert result["turns"]["mean"] == 25.0


# ---------------------------------------------------------------------------
# sensitivity_analysis
# ---------------------------------------------------------------------------

class TestSensitivityAnalysis:
    def test_single_param_set_returns_message(self):
        engine = AnalysisEngine()
        runs = [make_run(parameter_set_name="default") for _ in range(5)]
        result = engine.sensitivity_analysis(runs)
        assert "message" in result

    def test_multiple_param_sets_returns_variance(self):
        engine = AnalysisEngine()
        runs = [
            make_run(winner="BLUE", parameter_set_name="alpha"),
            make_run(winner="BLUE", parameter_set_name="alpha"),
            make_run(winner="RED", parameter_set_name="beta"),
            make_run(winner="RED", parameter_set_name="beta"),
        ]
        result = engine.sensitivity_analysis(runs)
        assert "by_parameter" in result
        assert "win_rate_variance" in result
        assert result["win_rate_variance"] > 0
        assert result["most_decisive_parameter"] in ("alpha", "beta")

    def test_by_parameter_has_correct_rates(self):
        engine = AnalysisEngine()
        runs = [
            make_run(winner="BLUE", parameter_set_name="p1"),
            make_run(winner="RED", parameter_set_name="p2"),
        ]
        result = engine.sensitivity_analysis(runs)
        assert result["by_parameter"]["p1"]["blue_win_rate"] == 1.0
        assert result["by_parameter"]["p2"]["red_win_rate"] == 1.0


# ---------------------------------------------------------------------------
# classify_outcomes
# ---------------------------------------------------------------------------

class TestClassifyOutcomes:
    def test_decisive_blue(self):
        engine = AnalysisEngine()
        runs = [make_run(winner="BLUE", total_turns=10)]  # < 72*0.5=36
        result = engine.classify_outcomes(runs, side_a="BLUE", side_b="RED")
        assert 0 in result["groups"]["decisive_a"]
        assert result["summary"]["decisive_a"] == 1

    def test_decisive_red(self):
        engine = AnalysisEngine()
        runs = [make_run(winner="RED", total_turns=10)]
        result = engine.classify_outcomes(runs, side_a="BLUE", side_b="RED")
        assert 0 in result["groups"]["decisive_b"]
        assert result["summary"]["decisive_b"] == 1

    def test_close_outcome(self):
        engine = AnalysisEngine()
        runs = [make_run(winner="BLUE", total_turns=50)]  # >= 36 turns, not draw
        result = engine.classify_outcomes(runs)
        assert 0 in result["groups"]["close"]

    def test_stalemate(self):
        engine = AnalysisEngine()
        runs = [make_run(winner="DRAW", total_turns=72)]
        result = engine.classify_outcomes(runs)
        assert 0 in result["groups"]["stalemate"]

    def test_summary_counts(self):
        engine = AnalysisEngine()
        runs = [
            make_run(0, winner="BLUE", total_turns=10),
            make_run(1, winner="RED", total_turns=10),
            make_run(2, winner="DRAW", total_turns=72),
            make_run(3, winner="BLUE", total_turns=60),
        ]
        result = engine.classify_outcomes(runs, side_a="BLUE", side_b="RED")
        assert result["summary"]["decisive_a"] == 1
        assert result["summary"]["decisive_b"] == 1
        assert result["summary"]["stalemate"] == 1
        assert result["summary"]["close"] == 1


# ---------------------------------------------------------------------------
# find_divergence_points
# ---------------------------------------------------------------------------

class TestFindDivergencePoints:
    def test_single_run_returns_message(self):
        engine = AnalysisEngine()
        runs = [make_run(total_turns=30)]
        result = engine.find_divergence_points(runs)
        assert "message" in result

    def test_varied_turns(self):
        engine = AnalysisEngine()
        runs = [
            make_run(total_turns=10),
            make_run(total_turns=20),
            make_run(total_turns=30),
            make_run(total_turns=40),
        ]
        result = engine.find_divergence_points(runs)
        assert "median_completion_turn" in result
        assert result["turn_range"]["min"] == 10
        assert result["turn_range"]["max"] == 40
        assert result["early_endings"] + result["late_endings"] == 4
        assert result["estimated_critical_turn"] > 0

    def test_median_calculation(self):
        engine = AnalysisEngine()
        runs = [make_run(total_turns=t) for t in [10, 20, 30, 40]]
        result = engine.find_divergence_points(runs)
        # median of [10, 20, 30, 40] = 25.0
        assert result["median_completion_turn"] == 25.0
