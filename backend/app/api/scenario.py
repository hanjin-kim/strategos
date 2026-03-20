from __future__ import annotations
import json
from pathlib import Path
from flask import Blueprint, jsonify

scenario_bp = Blueprint("scenario", __name__, url_prefix="/api/scenarios")

SCENARIOS_DIR = Path(__file__).parent.parent.parent.parent / "scripts" / "seed_scenarios"


@scenario_bp.route("/", methods=["GET"])
def list_scenarios():
    """List available scenarios."""
    scenarios = []
    if SCENARIOS_DIR.exists():
        for f in sorted(SCENARIOS_DIR.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                scenarios.append({
                    "name": f.stem,
                    "display_name": data.get("name", f.stem),
                    "description": data.get("description", ""),
                })
            except (json.JSONDecodeError, OSError):
                continue
    return jsonify(scenarios)


@scenario_bp.route("/<name>", methods=["GET"])
def get_scenario(name: str):
    """Get scenario details."""
    path = SCENARIOS_DIR / f"{name}.json"
    if not path.exists():
        return jsonify({"error": f"Scenario '{name}' not found"}), 404
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return jsonify(data)
    except (json.JSONDecodeError, OSError) as e:
        return jsonify({"error": str(e)}), 500


@scenario_bp.route("/<name>/validate", methods=["POST"])
def validate_scenario(name: str):
    """Validate scenario JSON can be loaded into GameState."""
    from app.engine.game_state import GameState
    path = SCENARIOS_DIR / f"{name}.json"
    if not path.exists():
        return jsonify({"error": f"Scenario '{name}' not found"}), 404
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = GameState(data)
        return jsonify({
            "valid": True,
            "units": len(state.units),
            "terrain_hexes": len(state.terrain),
            "commanders": len(state.commanders),
        })
    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 400
