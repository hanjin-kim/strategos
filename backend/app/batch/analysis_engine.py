from __future__ import annotations
import statistics
from collections import Counter, defaultdict


def _discover_sides(runs: list[dict]) -> tuple[str, str]:
    """Discover the two competing sides from run results."""
    all_winners = set()
    for r in runs:
        w = r.get("winner", "DRAW")
        if w != "DRAW":
            all_winners.add(w)
    sides = sorted(all_winners)
    if len(sides) >= 2:
        return sides[0], sides[1]
    if len(sides) == 1:
        return sides[0], "DRAW"
    return "side_a", "side_b"


class AnalysisEngine:
    """Pure data analysis on batch simulation results. No LLM dependency."""

    def analyze(self, runs: list[dict]) -> dict:
        """Full analysis of batch runs. Input: list of batch_run dicts from OutcomeCollector."""
        completed = [r for r in runs if r.get("status") == "COMPLETED"]
        if not completed:
            return {"error": "No completed runs to analyze", "runs_analyzed": 0}

        side_a, side_b = _discover_sides(completed)

        return {
            "runs_analyzed": len(completed),
            "sides": {"side_a": side_a, "side_b": side_b},
            "win_rates": self.calculate_win_rates(completed, side_a, side_b),
            "casualty_analysis": self.analyze_casualties(completed),
            "duration_analysis": self.analyze_duration(completed),
            "sensitivity": self.sensitivity_analysis(completed, side_a, side_b),
            "classification": self.classify_outcomes(completed, side_a, side_b),
            "divergence_points": self.find_divergence_points(completed),
        }

    def calculate_win_rates(self, runs: list[dict], side_a: str = "BLUE", side_b: str = "RED") -> dict:
        """Win rate by side (dynamic names)."""
        winners = Counter(r.get("winner", "DRAW") for r in runs)
        total = len(runs)
        return {
            "side_a": side_a,
            "side_b": side_b,
            "side_a_wins": winners.get(side_a, 0),
            "side_b_wins": winners.get(side_b, 0),
            "draws": winners.get("DRAW", 0),
            "total": total,
            "side_a_win_rate": round(winners.get(side_a, 0) / total, 3) if total else 0,
            "side_b_win_rate": round(winners.get(side_b, 0) / total, 3) if total else 0,
            # Backward compat aliases
            "blue_wins": winners.get(side_a, 0),
            "red_wins": winners.get(side_b, 0),
            "blue_win_rate": round(winners.get(side_a, 0) / total, 3) if total else 0,
            "red_win_rate": round(winners.get(side_b, 0) / total, 3) if total else 0,
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

    def sensitivity_analysis(self, runs: list[dict], side_a: str = "BLUE", side_b: str = "RED") -> dict:
        """Which parameters most affect outcome?"""
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
            a_rate = round(winners.get(side_a, 0) / total, 3) if total else 0
            b_rate = round(winners.get(side_b, 0) / total, 3) if total else 0
            param_win_rates[name] = {
                "side_a_win_rate": a_rate,
                "side_b_win_rate": b_rate,
                "draw_rate": round(winners.get("DRAW", 0) / total, 3) if total else 0,
                "total_runs": total,
                # Backward compat
                "blue_win_rate": a_rate,
                "red_win_rate": b_rate,
            }

        rates = [v["side_a_win_rate"] for v in param_win_rates.values()]
        variance = statistics.variance(rates) if len(rates) > 1 else 0

        return {
            "by_parameter": param_win_rates,
            "win_rate_variance": round(variance, 4),
            "most_decisive_parameter": max(param_win_rates, key=lambda k: abs(param_win_rates[k]["side_a_win_rate"] - 0.5)) if param_win_rates else None,
        }

    def classify_outcomes(self, runs: list[dict], side_a: str = "BLUE", side_b: str = "RED") -> dict:
        """Classify outcomes into groups."""
        groups = {"decisive_a": [], "decisive_b": [], "close": [], "stalemate": []}

        for r in runs:
            winner = r.get("winner", "DRAW")
            turns = r.get("total_turns", 0)
            max_turns = 72

            if winner == side_a and turns < max_turns * 0.5:
                groups["decisive_a"].append(r.get("run_index", 0))
            elif winner == side_b and turns < max_turns * 0.5:
                groups["decisive_b"].append(r.get("run_index", 0))
            elif winner == "DRAW":
                groups["stalemate"].append(r.get("run_index", 0))
            else:
                groups["close"].append(r.get("run_index", 0))

        return {
            "groups": groups,
            "summary": {k: len(v) for k, v in groups.items()},
            # Backward compat
            "decisive_blue": len(groups["decisive_a"]),
            "decisive_red": len(groups["decisive_b"]),
        }

    def find_divergence_points(self, runs: list[dict]) -> dict:
        """Identify turns where outcomes start diverging."""
        turns = sorted(r.get("total_turns", 0) for r in runs)
        if len(turns) < 2:
            return {"message": "Need multiple runs to find divergence"}

        median_turn = statistics.median(turns)
        early = [t for t in turns if t < median_turn]
        late = [t for t in turns if t >= median_turn]

        return {
            "median_completion_turn": round(median_turn, 1),
            "early_endings": len(early),
            "late_endings": len(late),
            "turn_range": {"min": min(turns), "max": max(turns)},
            "estimated_critical_turn": round(median_turn * 0.7, 0),
        }
