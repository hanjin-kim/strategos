from __future__ import annotations
import json
import threading
import uuid
import logging
from pathlib import Path
from flask import Blueprint, jsonify, request, Response

from app.engine.game_state import GameState
from app.engine.turn_manager import TurnManager
from app.engine.constraint_engine import ConstraintEngine
from app.engine.combat_resolver import CombatResolver
from app.engine.movement_engine import MovementEngine
from app.agents.theater_commander import TheaterCommander
from app.agents.battalion_commander import BattalionCommander
from app.graph.relationship_graph import RelationshipGraph
from app.graph.graph_tools import GraphTools
from app.memory.replay_store import ReplayStore
from app.config import Settings

logger = logging.getLogger(__name__)

simulation_bp = Blueprint("simulation", __name__, url_prefix="/api/simulations")

SCENARIOS_DIR = Path(__file__).parent.parent.parent.parent / "scripts" / "seed_scenarios"

# In-memory tracking of active simulations
_simulations: dict[str, dict] = {}  # sim_id -> {"thread", "turn_manager", "status", "game_state", "lock"}


def _load_scenario(name: str) -> dict:
    path = SCENARIOS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Scenario '{name}' not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _create_agents(game_state: GameState, scenario_data: dict, llm_config: dict, graph_tools: GraphTools | None) -> dict:
    """Create all commander agents from scenario data."""
    agents = {}
    for side_str, force_data in scenario_data.get("forces", {}).items():
        for cmd_data in force_data.get("commanders", []):
            commander = game_state.commanders.get(cmd_data["id"])
            if not commander:
                continue
            if commander.rank == "Theater":
                agents[commander.id] = TheaterCommander(
                    commander=commander, llm_config=llm_config, graph_tools=graph_tools
                )
            else:
                agents[commander.id] = BattalionCommander(
                    commander=commander, llm_config=llm_config, graph_tools=graph_tools
                )
    return agents


@simulation_bp.route("/", methods=["POST"])
def create_simulation():
    """Create a new simulation."""
    data = request.get_json() or {}
    scenario_name = data.get("scenario_name", "korean_peninsula")

    try:
        scenario_data = _load_scenario(scenario_name)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404

    sim_id = str(uuid.uuid4())
    game_state = GameState(scenario_data)

    settings = Settings()
    db_path = str(Path(settings.DB_PATH).parent / f"sim_{sim_id}.db")
    replay_store = ReplayStore(db_path)
    replay_store.create_simulation(scenario_name, scenario_data.get("config", {}))

    # Create relationship graph
    rel_graph = RelationshipGraph()
    rel_graph.load_from_scenario(scenario_data, game_state)
    graph_tools = GraphTools(rel_graph)

    # Create agents
    llm_config = {
        "api_key": settings.LLM_API_KEY,
        "base_url": settings.LLM_BASE_URL,
        "model": settings.LLM_MODEL_NAME,
        "temperature": 0.0,
    }
    agents = _create_agents(game_state, scenario_data, llm_config, graph_tools)

    # Create turn manager
    turn_manager = TurnManager(
        game_state=game_state,
        agents=agents,
        constraint_engine=ConstraintEngine(),
        combat_resolver=CombatResolver(),
        movement_engine=MovementEngine(),
        replay_store=replay_store,
        relationship_graph=rel_graph,
        simulation_id=sim_id,
        log_dir=settings.LOG_DIR,
    )

    _simulations[sim_id] = {
        "turn_manager": turn_manager,
        "game_state": game_state,
        "status": "created",
        "thread": None,
        "lock": threading.Lock(),
        "scenario_name": scenario_name,
        "max_turns": scenario_data.get("config", {}).get("max_turns", 72),
    }

    return jsonify({"simulation_id": sim_id, "status": "created"}), 201


@simulation_bp.route("/<sim_id>/start", methods=["POST"])
def start_simulation(sim_id: str):
    """Start simulation in background thread."""
    sim = _simulations.get(sim_id)
    if not sim:
        return jsonify({"error": "Simulation not found"}), 404
    if sim["status"] == "running":
        return jsonify({"error": "Simulation already running"}), 400

    max_turns = request.get_json(silent=True) or {}
    max_turns = max_turns.get("max_turns", sim["max_turns"])

    def run():
        sim["status"] = "running"
        try:
            def on_turn(turn, state):
                with sim["lock"]:
                    sim["current_turn"] = turn
            sim["turn_manager"].run_simulation(max_turns=max_turns, callback=on_turn)
            sim["status"] = "completed"
        except Exception as e:
            logger.error("Simulation %s failed: %s", sim_id, e)
            sim["status"] = "error"
            sim["error"] = str(e)

    thread = threading.Thread(target=run, daemon=True)
    sim["thread"] = thread
    sim["current_turn"] = 0
    thread.start()

    return jsonify({"simulation_id": sim_id, "status": "running"})


@simulation_bp.route("/<sim_id>/status", methods=["GET"])
def get_status(sim_id: str):
    """Get simulation status."""
    sim = _simulations.get(sim_id)
    if not sim:
        return jsonify({"error": "Simulation not found"}), 404

    result = {
        "simulation_id": sim_id,
        "status": sim["status"],
        "current_turn": sim.get("current_turn", 0),
        "max_turns": sim.get("max_turns", 72),
        "scenario_name": sim.get("scenario_name", ""),
    }
    if sim.get("error"):
        result["error"] = sim["error"]
    return jsonify(result)


@simulation_bp.route("/<sim_id>/state", methods=["GET"])
def get_state(sim_id: str):
    """Get current game state or state at specific turn."""
    sim = _simulations.get(sim_id)
    if not sim:
        return jsonify({"error": "Simulation not found"}), 404

    turn = request.args.get("turn", type=int)
    if turn is not None:
        # Load from replay store
        snapshot = sim["turn_manager"].replay_store.load_snapshot(sim_id, turn)
        if snapshot is None:
            return jsonify({"error": f"No snapshot for turn {turn}"}), 404
        return jsonify(snapshot)

    # Return current state
    with sim["lock"]:
        return jsonify(sim["game_state"].to_snapshot())


@simulation_bp.route("/<sim_id>/log", methods=["GET"])
def get_log(sim_id: str):
    """Get action log for a specific turn or all turns."""
    sim = _simulations.get(sim_id)
    if not sim:
        return jsonify({"error": "Simulation not found"}), 404

    turn = request.args.get("turn", type=int)
    replay_store = sim["turn_manager"].replay_store

    if turn is not None:
        actions = replay_store.get_turn_actions(sim_id, turn)
        return jsonify({"turn": turn, "actions": actions})

    turns = replay_store.list_turns(sim_id)
    return jsonify({"turns": turns})


@simulation_bp.route("/<sim_id>/stop", methods=["POST"])
def stop_simulation(sim_id: str):
    """Stop a running simulation."""
    sim = _simulations.get(sim_id)
    if not sim:
        return jsonify({"error": "Simulation not found"}), 404
    sim["status"] = "stopped"
    return jsonify({"simulation_id": sim_id, "status": "stopped"})


@simulation_bp.route("/<sim_id>/stream", methods=["GET"])
def stream_simulation(sim_id: str):
    """SSE stream for turn updates."""
    sim = _simulations.get(sim_id)
    if not sim:
        return jsonify({"error": "Simulation not found"}), 404

    def generate():
        import time
        last_turn = 0
        while sim["status"] == "running":
            current = sim.get("current_turn", 0)
            if current > last_turn:
                last_turn = current
                data = json.dumps({"turn": current, "status": sim["status"]})
                yield f"data: {data}\n\n"
            time.sleep(0.5)
        # Final event
        data = json.dumps({"turn": sim.get("current_turn", 0), "status": sim["status"]})
        yield f"data: {data}\n\n"

    return Response(generate(), mimetype="text/event-stream")
