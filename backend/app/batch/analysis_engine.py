from __future__ import annotations
import statistics
from collections import Counter, defaultdict


class AnalysisEngine:
    """Pure data analysis on batch simulation results. No LLM dependency."""

    def analyze(self, runs: list[dict]) -> dict:
        """Full analysis of batch runs. Input: list of batch_run dicts from OutcomeCollector."""
        completed = [r for r in runs if r.get("status") == "COMPLETED"]
        if not completed:
            return {"error": "No completed runs to analyze", "runs_analyzed": 0}

        return {
            "runs_analyzed": len(completed),
            "win_rates": self.calculate_win_rates(completed),
            "casualty_analysis": self.analyze_casualties(completed),
            "duration_analysis": self.analyze_duration(completed),
            "sensitivity": self.sensitivity_analysis(completed),
            "classification": self.classify_outcomes(completed),
            "divergence_points": self.find_divergence_points(completed),
        }

    def calculate_win_rates(self, runs: list[dict]) -> dict:
        """Win rate by side."""
        winners = Counter(r.get("winner", "DRAW") for r in runs)
        total = len(runs)
        return {
            "blue_wins": winners.get("BLUE", 0),
            "red_wins": winners.get("RED", 0),
            "draws": winners.get("DRAW", 0),
            "total": total,
            "blue_win_rate": round(winners.get("BLUE", 0) / total, 3) if total else 0,
            "red_win_rate": round(winners.get("RED", 0) / total, 3) if total else 0,
        }

    def analyze_casualties(self, runs: list[dict]) -> dict:
        """Casualty statistics."""
        blue_remaining = [r.get("blue_units_remaining", 0) for r in runs]
        red_remaining = [r.get("red_units_remaining", 0) for r in runs]
        blue_strength = [r.get("blue_avg_strength", 0) for r in runs]
        red_strength = [r.get("red_avg_strength", 0) for r in runs]

        def safe_stats(data):
            if not data:
                return {"mean": 0, "stdev": 0, "min": 0, "max": 0}
            return {
                "mean": round(statistics.mean(data), 3),
                "stdev": round(statistics.stdev(data), 3) if len(data) > 1 else 0,
                "min": min(data),
                "max": max(data),
            }

        return {
            "blue_units_remaining": safe_stats(blue_remaining),
            "red_units_remaining": safe_stats(red_remaining),
            "blue_avg_strength": safe_stats(blue_strength),
            "red_avg_strength": safe_stats(red_strength),
        }

    def analyze_duration(self, runs: list[dict]) -> dict:
        """Game duration statistics."""
        turns = [r.get("total_turns", 0) for r in runs]
        times = [r.get("execution_time_ms", 0) for r in runs]
        return {
            "turns": {
                "mean": round(statistics.mean(turns), 1) if turns else 0,
                "stdev": round(statistics.stdev(turns), 1) if len(turns) > 1 else 0,
                "min": min(turns) if turns else 0,
                "max": max(turns) if turns else 0,
            },
            "execution_ms": {
                "mean": round(statistics.mean(times), 0) if times else 0,
                "total": sum(times),
            },
        }

    def sensitivity_analysis(self, runs: list[dict]) -> dict:
        """Which parameters most affect outcome?
        Groups runs by parameter_set_name prefix and compares win rates."""
        by_param = defaultdict(list)
        for r in runs:
            name = r.get("parameter_set_name", "default")
            by_param[name].append(r)

        if len(by_param) <= 1:
            return {"message": "Need multiple parameter sets for sensitivity analysis"}

        param_win_rates = {}
        for name, group_runs in by_param.items():
            winners = Counter(r.get("winner", "DRAW") for r in group_runs)
            total = len(group_runs)
            param_win_rates[name] = {
                "blue_win_rate": round(winners.get("BLUE", 0) / total, 3) if total else 0,
                "red_win_rate": round(winners.get("RED", 0) / total, 3) if total else 0,
                "draw_rate": round(winners.get("DRAW", 0) / total, 3) if total else 0,
                "total_runs": total,
            }

        # Find most impactful parameter (highest variance in blue_win_rate)
        rates = [v["blue_win_rate"] for v in param_win_rates.values()]
        variance = statistics.variance(rates) if len(rates) > 1 else 0

        return {
            "by_parameter": param_win_rates,
            "win_rate_variance": round(variance, 4),
            "most_decisive_parameter": max(param_win_rates, key=lambda k: abs(param_win_rates[k]["blue_win_rate"] - 0.5)) if param_win_rates else None,
        }

    def classify_outcomes(self, runs: list[dict]) -> dict:
        """Classify outcomes into groups: decisive_blue, decisive_red, close, stalemate."""
        groups = {"decisive_blue": [], "decisive_red": [], "close": [], "stalemate": []}

        for r in runs:
            winner = r.get("winner", "DRAW")
            turns = r.get("total_turns", 0)
            max_turns = 72  # default

            if winner == "BLUE" and turns < max_turns * 0.5:
                groups["decisive_blue"].append(r.get("run_index", 0))
            elif winner == "RED" and turns < max_turns * 0.5:
                groups["decisive_red"].append(r.get("run_index", 0))
            elif winner == "DRAW":
                groups["stalemate"].append(r.get("run_index", 0))
            else:
                groups["close"].append(r.get("run_index", 0))

        return {
            "groups": groups,
            "summary": {k: len(v) for k, v in groups.items()},
        }

    def find_divergence_points(self, runs: list[dict]) -> dict:
        """Identify turns where outcomes start diverging.
        Uses total_turns as a proxy — if some runs end early and others go long,
        the midpoint is likely a critical decision turn."""
        turns = sorted(r.get("total_turns", 0) for r in runs)
        if len(turns) < 2:
            return {"message": "Need multiple runs to find divergence"}

        # Find the turn range where outcomes split
        median_turn = statistics.median(turns)
        early = [t for t in turns if t < median_turn]
        late = [t for t in turns if t >= median_turn]

        return {
            "median_completion_turn": round(median_turn, 1),
            "early_endings": len(early),
            "late_endings": len(late),
            "turn_range": {"min": min(turns), "max": max(turns)},
            "estimated_critical_turn": round(median_turn * 0.7, 0),  # ~70% of median is often where key decisions happen
        }
