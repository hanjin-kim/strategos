"""
STRATEGOS Business PoC: Cloud Computing Market
"""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.batch.parameter_set import ParameterSet, generate_parameter_grid
from app.batch.batch_runner import BatchRunner
from app.batch.outcome_collector import OutcomeCollector
from app.batch.analysis_engine import AnalysisEngine
from app.batch.report_generator import ReportGenerator
from app.prompts.business_doctrine import BUSINESS_DOCTRINE


def main():
    scenario_path = os.path.join(os.path.dirname(__file__), '../../scripts/seed_scenarios/cloud_computing_market.json')
    with open(scenario_path) as f:
        scenario = json.load(f)

    print(f"=== STRATEGOS Business: {scenario['name']} ===\n")

    base = ParameterSet(name="baseline", rng_seed=42, max_turns=18, use_llm=False)

    param_sets = generate_parameter_grid(base, {
        "rng_seed": [42, 43, 44, 45, 46, 47, 48],
        "strength_multipliers": [
            {},  # baseline
            {"aws_aiml": 1.3},  # AWS invests heavily in AI
            {"azure_saas_eu": 1.3},  # Azure doubles down on EU SaaS
            {"aws_iaas_na": 0.7},  # AWS loses NA share (antitrust)
        ],
    })

    print(f"Running {len(param_sets)} simulations...\n")

    runner = BatchRunner(scenario, scenario["name"], doctrine_override=BUSINESS_DOCTRINE)
    cost = runner.estimate_cost(param_sets)
    print(f"Cost estimate: {cost}\n")

    result = runner.run_batch(
        param_sets,
        callback=lambda i, total, r: print(f"  Run {i+1}/{total}: {r.winner} in {r.total_turns} turns ({r.execution_time_ms}ms)")
    )

    print(f"\nBatch: {result.completed_runs}/{result.total_runs} runs, {result.execution_time_ms}ms\n")

    db_path = os.path.join(os.path.dirname(__file__), '../data/cloud_poc.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    collector = OutcomeCollector(db_path=db_path)
    collector.save_batch(result)

    runs = collector.get_batch_runs(result.batch_id)
    engine = AnalysisEngine()
    analysis = engine.analyze(runs)

    print("=== Analysis ===")
    print(json.dumps(analysis.get("win_rates", {}), indent=2))
    print(json.dumps(analysis.get("sensitivity", {}).get("by_parameter", {}), indent=2, default=str)[:500])

    reporter = ReportGenerator()
    report = reporter.generate_report(analysis, {"scenario": scenario["name"], "domain": "business"})

    print("\n=== Report ===")
    print(reporter.to_markdown(report))

    report_path = os.path.join(os.path.dirname(__file__), '../data/cloud_poc_report.md')
    with open(report_path, 'w') as f:
        f.write(reporter.to_markdown(report))
    print(f"\nSaved: {report_path}")


if __name__ == "__main__":
    main()
