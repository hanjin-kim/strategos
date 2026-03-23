from __future__ import annotations
import json
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates analysis reports from batch simulation results.
    Supports LLM-powered reports and template-based fallback."""

    def __init__(self, llm_config: dict | None = None):
        self._client = None
        self._model = "qwen-plus"
        if llm_config:
            self._model = llm_config.get("model", "qwen-plus")
            api_key = llm_config.get("api_key", "")
            if api_key:
                self._client = OpenAI(
                    api_key=api_key,
                    base_url=llm_config.get("base_url", ""),
                )

    def generate_report(self, analysis: dict, batch_meta: dict | None = None) -> dict:
        """Generate a structured report from analysis results.
        Returns dict with: executive_summary, strategy_comparison, risk_assessment,
        recommendations, key_decision_points."""
        if self._client:
            try:
                return self._llm_report(analysis, batch_meta)
            except Exception as e:
                logger.warning("LLM report generation failed: %s", e)
        return self._template_report(analysis, batch_meta)

    def _llm_report(self, analysis: dict, batch_meta: dict | None) -> dict:
        """LLM-powered report generation."""
        prompt = self._build_prompt(analysis, batch_meta)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2048,
        )
        text = response.choices[0].message.content
        return self._parse_report(text, analysis)

    def _system_prompt(self) -> str:
        return (
            "You are a military analyst writing a wargame simulation analysis report. "
            "Be concise and data-driven. Output JSON with these fields: "
            '"executive_summary", "strategy_comparison", "risk_assessment", '
            '"recommendations", "key_decision_points"'
        )

    def _build_prompt(self, analysis: dict, batch_meta: dict | None) -> str:
        context = {"analysis": analysis}
        if batch_meta:
            context["batch"] = batch_meta
        return json.dumps(context, default=str)

    def _parse_report(self, text: str, analysis: dict) -> dict:
        try:
            clean = text.strip()
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0]
            elif "```" in clean:
                clean = clean.split("```")[1].split("```")[0]
            data = json.loads(clean)
            return {
                "executive_summary": data.get("executive_summary", ""),
                "strategy_comparison": data.get("strategy_comparison", ""),
                "risk_assessment": data.get("risk_assessment", ""),
                "recommendations": data.get("recommendations", ""),
                "key_decision_points": data.get("key_decision_points", ""),
                "source": "llm",
            }
        except Exception:
            return self._template_report(analysis)

    def _template_report(self, analysis: dict, batch_meta: dict | None = None) -> dict:
        """Template-based fallback report."""
        win_rates = analysis.get("win_rates", {})
        casualties = analysis.get("casualty_analysis", {})
        duration = analysis.get("duration_analysis", {})
        sensitivity = analysis.get("sensitivity", {})
        classification = analysis.get("classification", {})
        divergence = analysis.get("divergence_points", {})

        # Executive summary
        runs = analysis.get("runs_analyzed", 0)
        blue_wr = win_rates.get("blue_win_rate", 0)
        red_wr = win_rates.get("red_win_rate", 0)

        if blue_wr > 0.6:
            outlook = "BLUE forces hold a significant advantage"
        elif red_wr > 0.6:
            outlook = "RED forces hold a significant advantage"
        else:
            outlook = "The outcome is contested with no clear favorite"

        exec_summary = (
            f"Analysis of {runs} simulation runs: {outlook}. "
            f"BLUE win rate: {blue_wr:.1%}, RED win rate: {red_wr:.1%}. "
            f"Average game duration: {duration.get('turns', {}).get('mean', 0):.0f} turns."
        )

        # Strategy comparison
        by_param = sensitivity.get("by_parameter", {})
        if by_param:
            best_blue = max(by_param, key=lambda k: by_param[k].get("blue_win_rate", 0))
            best_red = max(by_param, key=lambda k: by_param[k].get("red_win_rate", 0))
            strategy_comp = (
                f"Best BLUE strategy: '{best_blue}' ({by_param[best_blue]['blue_win_rate']:.1%} win rate). "
                f"Best RED strategy: '{best_red}' ({by_param[best_red]['red_win_rate']:.1%} win rate)."
            )
        else:
            strategy_comp = "Insufficient parameter variation for strategy comparison."

        # Risk assessment
        blue_str = casualties.get("blue_avg_strength", {})
        red_str = casualties.get("red_avg_strength", {})
        risk_items = []
        if blue_str.get("min", 1) < 0.3:
            risk_items.append("BLUE forces risk near-total attrition in worst-case scenarios")
        if red_str.get("min", 1) < 0.3:
            risk_items.append("RED forces risk near-total attrition in worst-case scenarios")
        summary_groups = classification.get("summary", {})
        if summary_groups.get("stalemate", 0) > runs * 0.3:
            risk_items.append(f"High stalemate probability ({summary_groups['stalemate']}/{runs} runs)")
        risk_assessment = "; ".join(risk_items) if risk_items else "No critical risks identified."

        # Recommendations
        recs = []
        most_decisive = sensitivity.get("most_decisive_parameter")
        if most_decisive:
            recs.append(f"Focus on parameter '{most_decisive}' — it has the highest impact on outcome.")
        critical_turn = divergence.get("estimated_critical_turn", 0)
        if critical_turn > 0:
            recs.append(f"Critical decision window around turn {critical_turn:.0f}.")
        if not recs:
            recs.append("Run additional simulations with more parameter variation for deeper insights.")
        recommendations = " ".join(recs)

        # Key decision points
        key_points = []
        if critical_turn > 0:
            key_points.append(f"Turn ~{critical_turn:.0f}: Estimated divergence point where outcomes split")
        min_turn = divergence.get("turn_range", {}).get("min", 0)
        max_turn = divergence.get("turn_range", {}).get("max", 0)
        if min_turn != max_turn:
            key_points.append(
                f"Game length varies from {min_turn} to {max_turn} turns — early aggression can force quick resolution"
            )

        return {
            "executive_summary": exec_summary,
            "strategy_comparison": strategy_comp,
            "risk_assessment": risk_assessment,
            "recommendations": recommendations,
            "key_decision_points": key_points,
            "source": "template",
        }

    def to_markdown(self, report: dict) -> str:
        """Convert report dict to Markdown string."""
        lines = ["# Simulation Analysis Report", ""]
        lines.append("## Executive Summary")
        lines.append(report.get("executive_summary", "N/A"))
        lines.append("")
        lines.append("## Strategy Comparison")
        lines.append(report.get("strategy_comparison", "N/A"))
        lines.append("")
        lines.append("## Risk Assessment")
        lines.append(report.get("risk_assessment", "N/A"))
        lines.append("")
        lines.append("## Recommendations")
        lines.append(report.get("recommendations", "N/A"))
        lines.append("")
        lines.append("## Key Decision Points")
        for point in report.get("key_decision_points", []):
            if isinstance(point, str):
                lines.append(f"- {point}")
            else:
                lines.append(f"- {point}")
        lines.append("")
        lines.append(f"*Report source: {report.get('source', 'unknown')}*")
        return "\n".join(lines)
