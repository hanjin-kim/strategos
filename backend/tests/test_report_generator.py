from __future__ import annotations
import json
import pytest
from unittest.mock import MagicMock, patch
from app.batch.report_generator import ReportGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_analysis(blue_wr=0.7, red_wr=0.2, runs=10):
    return {
        "runs_analyzed": runs,
        "sides": {"side_a": "BLUE", "side_b": "RED"},
        "win_rates": {
            "side_a": "BLUE",
            "side_b": "RED",
            "side_a_win_rate": blue_wr,
            "side_b_win_rate": red_wr,
            "blue_win_rate": blue_wr,
            "red_win_rate": red_wr,
            "draw_rate": 1 - blue_wr - red_wr,
        },
        "casualty_analysis": {
            "blue_avg_strength": {"mean": 0.75, "min": 0.1, "max": 1.0},
            "red_avg_strength": {"mean": 0.5, "min": 0.05, "max": 0.9},
        },
        "duration_analysis": {
            "turns": {"mean": 15.0, "min": 8, "max": 25}
        },
        "sensitivity": {
            "by_parameter": {
                "aggressive": {"side_a_win_rate": 0.8, "side_b_win_rate": 0.1, "blue_win_rate": 0.8, "red_win_rate": 0.1},
                "defensive": {"side_a_win_rate": 0.5, "side_b_win_rate": 0.4, "blue_win_rate": 0.5, "red_win_rate": 0.4},
            },
            "most_decisive_parameter": "aggressive",
        },
        "classification": {
            "summary": {"blue_victory": 7, "red_victory": 2, "stalemate": 1}
        },
        "divergence_points": {
            "estimated_critical_turn": 8.0,
            "turn_range": {"min": 8, "max": 25},
        },
    }


def _minimal_analysis():
    return {}


# ---------------------------------------------------------------------------
# Init tests
# ---------------------------------------------------------------------------

class TestReportGeneratorInit:
    def test_init_no_config(self):
        rg = ReportGenerator()
        assert rg._client is None
        assert rg._model == "qwen-plus"

    def test_init_with_empty_llm_config(self):
        rg = ReportGenerator(llm_config={})
        assert rg._client is None

    def test_init_with_config_no_api_key(self):
        rg = ReportGenerator(llm_config={"model": "gpt-4", "api_key": ""})
        assert rg._client is None
        assert rg._model == "gpt-4"

    def test_init_with_api_key_creates_client(self):
        with patch("app.batch.report_generator.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            rg = ReportGenerator(llm_config={
                "api_key": "test-key",
                "base_url": "https://example.com",
                "model": "qwen-plus",
            })
            assert rg._client is not None
            mock_openai.assert_called_once_with(api_key="test-key", base_url="https://example.com")


# ---------------------------------------------------------------------------
# _template_report tests
# ---------------------------------------------------------------------------

class TestTemplateReport:
    def test_full_analysis_returns_all_fields(self):
        rg = ReportGenerator()
        report = rg._template_report(_full_analysis())
        for field in ("executive_summary", "strategy_comparison", "risk_assessment",
                      "recommendations", "key_decision_points", "source"):
            assert field in report

    def test_source_is_template(self):
        rg = ReportGenerator()
        report = rg._template_report(_full_analysis())
        assert report["source"] == "template"

    def test_empty_analysis_does_not_crash(self):
        rg = ReportGenerator()
        report = rg._template_report(_minimal_analysis())
        assert report["source"] == "template"
        assert isinstance(report["executive_summary"], str)

    def test_blue_advantage_scenario(self):
        rg = ReportGenerator()
        report = rg._template_report(_full_analysis(blue_wr=0.8, red_wr=0.1))
        assert "BLUE holds a significant advantage" in report["executive_summary"]

    def test_red_advantage_scenario(self):
        rg = ReportGenerator()
        analysis = _full_analysis(blue_wr=0.1, red_wr=0.8)
        report = rg._template_report(analysis)
        assert "RED holds a significant advantage" in report["executive_summary"]

    def test_contested_scenario(self):
        rg = ReportGenerator()
        analysis = _full_analysis(blue_wr=0.4, red_wr=0.4)
        report = rg._template_report(analysis)
        assert "contested" in report["executive_summary"]

    def test_stalemate_risk_flagged(self):
        rg = ReportGenerator()
        analysis = _full_analysis(runs=10)
        # 4 stalemates out of 10 > 30%
        analysis["classification"]["summary"]["stalemate"] = 4
        report = rg._template_report(analysis)
        assert "stalemate" in report["risk_assessment"].lower()

    def test_no_risk_when_all_fine(self):
        rg = ReportGenerator()
        analysis = _full_analysis()
        # Ensure strength minimums are fine
        analysis["casualty_analysis"]["blue_avg_strength"]["min"] = 0.5
        analysis["casualty_analysis"]["red_avg_strength"]["min"] = 0.5
        analysis["classification"]["summary"]["stalemate"] = 0
        report = rg._template_report(analysis)
        assert report["risk_assessment"] == "No critical risks identified."

    def test_strategy_comparison_with_by_parameter(self):
        rg = ReportGenerator()
        report = rg._template_report(_full_analysis())
        assert "aggressive" in report["strategy_comparison"]

    def test_strategy_comparison_without_by_parameter(self):
        rg = ReportGenerator()
        analysis = _full_analysis()
        analysis["sensitivity"] = {}
        report = rg._template_report(analysis)
        assert "Insufficient" in report["strategy_comparison"]

    def test_key_decision_points_is_list(self):
        rg = ReportGenerator()
        report = rg._template_report(_full_analysis())
        assert isinstance(report["key_decision_points"], list)

    def test_key_decision_points_contains_critical_turn(self):
        rg = ReportGenerator()
        report = rg._template_report(_full_analysis())
        joined = " ".join(report["key_decision_points"])
        assert "8" in joined

    def test_recommendations_mention_decisive_param(self):
        rg = ReportGenerator()
        report = rg._template_report(_full_analysis())
        assert "aggressive" in report["recommendations"]

    def test_win_rates_in_executive_summary(self):
        rg = ReportGenerator()
        report = rg._template_report(_full_analysis(blue_wr=0.7, red_wr=0.2))
        assert "70.0%" in report["executive_summary"]
        assert "20.0%" in report["executive_summary"]


# ---------------------------------------------------------------------------
# _parse_report tests
# ---------------------------------------------------------------------------

class TestParseReport:
    def test_valid_json_parsed(self):
        rg = ReportGenerator()
        data = {
            "executive_summary": "Summary here.",
            "strategy_comparison": "Compare.",
            "risk_assessment": "Low risk.",
            "recommendations": "Proceed.",
            "key_decision_points": ["Turn 5"],
        }
        report = rg._parse_report(json.dumps(data), _full_analysis())
        assert report["executive_summary"] == "Summary here."
        assert report["source"] == "llm"

    def test_json_in_code_fence_parsed(self):
        rg = ReportGenerator()
        data = {"executive_summary": "Fenced.", "strategy_comparison": "",
                "risk_assessment": "", "recommendations": "", "key_decision_points": []}
        text = f"```json\n{json.dumps(data)}\n```"
        report = rg._parse_report(text, _full_analysis())
        assert report["executive_summary"] == "Fenced."
        assert report["source"] == "llm"

    def test_malformed_json_falls_back_to_template(self):
        rg = ReportGenerator()
        report = rg._parse_report("NOT VALID JSON {{{{", _full_analysis())
        assert report["source"] == "template"

    def test_parse_report_returns_all_required_fields(self):
        rg = ReportGenerator()
        data = {
            "executive_summary": "E",
            "strategy_comparison": "S",
            "risk_assessment": "R",
            "recommendations": "Rec",
            "key_decision_points": [],
        }
        report = rg._parse_report(json.dumps(data), _full_analysis())
        for field in ("executive_summary", "strategy_comparison", "risk_assessment",
                      "recommendations", "key_decision_points"):
            assert field in report


# ---------------------------------------------------------------------------
# generate_report tests
# ---------------------------------------------------------------------------

class TestGenerateReport:
    def test_no_client_uses_template(self):
        rg = ReportGenerator()
        report = rg.generate_report(_full_analysis())
        assert report["source"] == "template"

    def test_llm_failure_falls_back_to_template(self):
        with patch("app.batch.report_generator.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = RuntimeError("API down")
            mock_openai.return_value = mock_client
            rg = ReportGenerator(llm_config={"api_key": "key", "base_url": "url"})
            report = rg.generate_report(_full_analysis())
            assert report["source"] == "template"

    def test_llm_success_returns_llm_source(self):
        with patch("app.batch.report_generator.OpenAI") as mock_openai:
            mock_client = MagicMock()
            response_data = {
                "executive_summary": "LLM summary",
                "strategy_comparison": "LLM compare",
                "risk_assessment": "LLM risk",
                "recommendations": "LLM rec",
                "key_decision_points": ["Point A"],
            }
            mock_msg = MagicMock()
            mock_msg.content = json.dumps(response_data)
            mock_client.chat.completions.create.return_value.choices = [
                MagicMock(message=mock_msg)
            ]
            mock_openai.return_value = mock_client
            rg = ReportGenerator(llm_config={"api_key": "key", "base_url": "url"})
            report = rg.generate_report(_full_analysis())
            assert report["source"] == "llm"
            assert report["executive_summary"] == "LLM summary"

    def test_generate_report_with_batch_meta(self):
        rg = ReportGenerator()
        batch_meta = {"batch_id": "abc123", "scenario": "test"}
        report = rg.generate_report(_full_analysis(), batch_meta=batch_meta)
        assert report["source"] == "template"


# ---------------------------------------------------------------------------
# to_markdown tests
# ---------------------------------------------------------------------------

class TestToMarkdown:
    def test_produces_markdown_string(self):
        rg = ReportGenerator()
        report = rg._template_report(_full_analysis())
        md = rg.to_markdown(report)
        assert isinstance(md, str)

    def test_contains_all_section_headers(self):
        rg = ReportGenerator()
        report = rg._template_report(_full_analysis())
        md = rg.to_markdown(report)
        assert "## Executive Summary" in md
        assert "## Strategy Comparison" in md
        assert "## Risk Assessment" in md
        assert "## Recommendations" in md
        assert "## Key Decision Points" in md

    def test_contains_source_footer(self):
        rg = ReportGenerator()
        report = rg._template_report(_full_analysis())
        md = rg.to_markdown(report)
        assert "Report source:" in md
        assert "template" in md

    def test_empty_report_does_not_crash(self):
        rg = ReportGenerator()
        md = rg.to_markdown({})
        assert "# Simulation Analysis Report" in md

    def test_key_decision_points_rendered_as_bullets(self):
        rg = ReportGenerator()
        report = rg._template_report(_full_analysis())
        md = rg.to_markdown(report)
        # At least one bullet point for key decision points
        assert "- " in md

    def test_h1_title_present(self):
        rg = ReportGenerator()
        md = rg.to_markdown({"source": "template", "key_decision_points": []})
        assert md.startswith("# Simulation Analysis Report")
