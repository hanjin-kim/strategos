"""
STRATEGOS Business Competition PoC
Run batch simulation of EV Battery Market scenario and generate report.
"""
from __future__ import annotations
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
    # Load business scenario
    scenario_path = os.path.join(
        os.path.dirname(__file__),
        '../../scripts/seed_scenarios/ev_battery_market.json',
    )
    with open(scenario_path) as f:
        scenario = json.load(f)

    print(f"=== STRATEGOS Business PoC: {scenario['name']} ===\n")

    # Define parameter variations
    base = ParameterSet(name="baseline", rng_seed=42, max_turns=12, use_llm=False)

    param_sets = generate_parameter_grid(base, {
        "rng_seed": [42, 43, 44, 45, 46],
        "strength_multipliers": [
            {},                          # baseline
            {"blue_ev_usa": 1.3},        # BLUE invests heavily in US
            {"red_ev_china": 0.7},       # RED loses China share (regulation)
        ],
    })

    print(f"Running {len(param_sets)} simulations...\n")

    # Run batch
    runner = BatchRunner(scenario, scenario["name"], doctrine_override=BUSINESS_DOCTRINE)
    cost = runner.estimate_cost(param_sets)
    print(f"Cost estimate: {cost}\n")

    result = runner.run_batch(
        param_sets,
        callback=lambda i, total, r: print(
            f"  Run {i+1}/{total}: {r.winner} in {r.total_turns} turns ({r.execution_time_ms}ms)"
        ),
    )

    print(
        f"\nBatch complete: {result.completed_runs}/{result.total_runs} runs, "
        f"{result.execution_time_ms}ms total\n"
    )

    # Save results
    db_path = os.path.join(os.path.dirname(__file__), '../data/business_poc.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    collector = OutcomeCollector(db_path=db_path)
    collector.save_batch(result)

    # Analyze
    runs = collector.get_batch_runs(result.batch_id)
    engine = AnalysisEngine()
    analysis = engine.analyze(runs)

    print("=== Analysis Results ===")
    print(json.dumps(analysis, indent=2, default=str))

    # Generate report
    reporter = ReportGenerator()
    report = reporter.generate_report(analysis, {"scenario": scenario["name"], "domain": "business"})

    print("\n=== Report ===")
    print(reporter.to_markdown(report))

    # Save markdown report
    report_path = os.path.join(os.path.dirname(__file__), '../data/business_poc_report.md')
    with open(report_path, 'w') as f:
        f.write(reporter.to_markdown(report))
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
