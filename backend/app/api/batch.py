from __future__ import annotations
import json
import logging
import threading
import uuid
from pathlib import Path
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

batch_bp = Blueprint("batch", __name__, url_prefix="/api/batches")

SCENARIOS_DIR = Path(__file__).parent.parent.parent.parent / "scripts" / "seed_scenarios"

# In-memory batch state (for running batches)
_batches: dict[str, dict] = {}


def _load_scenario_data(scenario_name: str) -> dict | None:
    """Load scenario JSON by stem name."""
    path = SCENARIOS_DIR / f"{scenario_name}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _list_scenario_names() -> list[str]:
    """Return all available scenario stem names."""
    if not SCENARIOS_DIR.exists():
        return []
    return [f.stem for f in sorted(SCENARIOS_DIR.glob("*.json"))]


@batch_bp.route("", methods=["POST"])
def create_batch():
    """Create and start a batch run.

    Body: {
        "scenario_name": "korean_peninsula",
        "parameter_sets": [{"name": "default", "rng_seed": 42, "max_turns": 10}, ...],
        "use_llm": false
    }
    """
    data = request.get_json() or {}
    scenario_name = data.get("scenario_name")
    if not scenario_name:
        return jsonify({"error": "scenario_name required"}), 400

    scenario_data = _load_scenario_data(scenario_name)
    if scenario_data is None:
        return jsonify({"error": f"Scenario '{scenario_name}' not found"}), 404

    from app.batch.parameter_set import ParameterSet
    raw_params = data.get("parameter_sets", [{"name": "default", "rng_seed": 42, "max_turns": 10}])
    try:
        param_sets = [ParameterSet(**p) for p in raw_params]
    except Exception as exc:
        return jsonify({"error": f"Invalid parameter_sets: {exc}"}), 400

    batch_id = str(uuid.uuid4())[:8]

    from app.batch.batch_runner import BatchRunner
    runner = BatchRunner(scenario_data, scenario_name)
    cost = runner.estimate_cost(param_sets)

    _batches[batch_id] = {
        "batch_id": batch_id,
        "status": "RUNNING",
        "scenario_name": scenario_name,
        "total_runs": len(param_sets),
        "completed_runs": 0,
        "cost_estimate": cost,
    }

    def run_batch():
        from app.batch.outcome_collector import OutcomeCollector
        from app.batch.analysis_engine import AnalysisEngine
        from app.batch.report_generator import ReportGenerator

        def on_progress(i, total, run_result):
            _batches[batch_id]["completed_runs"] = i + 1
            _batches[batch_id]["last_run"] = run_result.model_dump()

        try:
            result = runner.run_batch(param_sets, batch_id=batch_id, callback=on_progress)

            collector = OutcomeCollector()
            collector.save_batch(result)

            runs = collector.get_batch_runs(batch_id)
            engine = AnalysisEngine()
            analysis = engine.analyze(runs)

            reporter = ReportGenerator()
            report = reporter.generate_report(analysis, {"batch_id": batch_id, "scenario": scenario_name})

            _batches[batch_id]["status"] = result.status
            _batches[batch_id]["result"] = result.model_dump()
            _batches[batch_id]["analysis"] = analysis
            _batches[batch_id]["report"] = report
        except Exception as exc:
            logger.error("Batch %s failed: %s", batch_id, exc)
            _batches[batch_id]["status"] = "FAILED"
            _batches[batch_id]["error"] = str(exc)

    thread = threading.Thread(target=run_batch, daemon=True)
    thread.start()

    return jsonify({
        "batch_id": batch_id,
        "status": "RUNNING",
        "total_runs": len(param_sets),
        "cost_estimate": cost,
    }), 201


@batch_bp.route("/<batch_id>/status", methods=["GET"])
def get_batch_status(batch_id: str):
    """Get status of a batch run."""
    if batch_id in _batches:
        b = _batches[batch_id]
        return jsonify({
            "batch_id": batch_id,
            "status": b["status"],
            "total_runs": b["total_runs"],
            "completed_runs": b.get("completed_runs", 0),
        })
    from app.batch.outcome_collector import OutcomeCollector
    collector = OutcomeCollector()
    batch = collector.get_batch(batch_id)
    if batch:
        return jsonify(batch)
    return jsonify({"error": "Batch not found"}), 404


@batch_bp.route("/<batch_id>/report", methods=["GET"])
def get_batch_report(batch_id: str):
    """Get analysis report for a completed batch."""
    if batch_id in _batches and "report" in _batches[batch_id]:
        return jsonify({
            "report": _batches[batch_id]["report"],
            "analysis": _batches[batch_id].get("analysis", {}),
        })
    from app.batch.outcome_collector import OutcomeCollector
    from app.batch.analysis_engine import AnalysisEngine
    from app.batch.report_generator import ReportGenerator
    collector = OutcomeCollector()
    runs = collector.get_batch_runs(batch_id)
    if not runs:
        return jsonify({"error": "Batch not found or no runs"}), 404
    analysis = AnalysisEngine().analyze(runs)
    report = ReportGenerator().generate_report(analysis)
    return jsonify({"report": report, "analysis": analysis})


@batch_bp.route("/<batch_id>/runs", methods=["GET"])
def get_batch_runs(batch_id: str):
    """Get individual run results for a batch."""
    from app.batch.outcome_collector import OutcomeCollector
    collector = OutcomeCollector()
    runs = collector.get_batch_runs(batch_id)
    return jsonify(runs)


@batch_bp.route("/<batch_id>/stop", methods=["POST"])
def stop_batch(batch_id: str):
    """Stop a running batch."""
    if batch_id in _batches:
        _batches[batch_id]["status"] = "STOPPED"
        return jsonify({"status": "STOPPED"})
    return jsonify({"error": "Batch not found or already completed"}), 404


@batch_bp.route("", methods=["GET"])
def list_batches():
    """List all batches (DB + in-memory running)."""
    from app.batch.outcome_collector import OutcomeCollector
    collector = OutcomeCollector()
    batches = collector.get_all_batches()
    db_ids = {b["batch_id"] for b in batches}
    for bid, b in _batches.items():
        if bid not in db_ids:
            batches.append({
                "batch_id": bid,
                "scenario_name": b.get("scenario_name", ""),
                "status": b["status"],
                "total_runs": b["total_runs"],
                "completed_runs": b.get("completed_runs", 0),
            })
    return jsonify(batches)


@batch_bp.route("/<batch_id>/report/markdown", methods=["GET"])
def get_batch_report_markdown(batch_id: str):
    """Get report as Markdown."""
    from app.batch.analysis_engine import AnalysisEngine
    from app.batch.report_generator import ReportGenerator

    if batch_id in _batches and "report" in _batches[batch_id]:
        report = _batches[batch_id]["report"]
    else:
        from app.batch.outcome_collector import OutcomeCollector
        collector = OutcomeCollector()
        runs = collector.get_batch_runs(batch_id)
        if not runs:
            return "Batch not found", 404
        analysis = AnalysisEngine().analyze(runs)
        report = ReportGenerator().generate_report(analysis)

    md = ReportGenerator().to_markdown(report)
    return md, 200, {"Content-Type": "text/markdown"}
