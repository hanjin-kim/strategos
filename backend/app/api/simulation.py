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
from app.engine.intel_engine import IntelEngine
from app.engine.supply_engine import SupplyEngine
from app.engine.air_engine import AirEngine
from app.agents.theater_commander import TheaterCommander
from app.agents.battalion_commander import BattalionCommander
from app.agents.adjudicator import Adjudicator
from app.graph.relationship_graph import RelationshipGraph
from app.graph.graph_tools import GraphTools
from app.memory.replay_store import ReplayStore
from app.config import Settings
from app.models.game_config import GameConfig, CommandMode, FogMode, AIDifficulty
from app.models.actions import MilitaryAction, ActionType, OrderDirective, MissionType
from app.models.domain import HexCoord, Side
from app.engine.human_commander import HumanCommander

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


def _create_agents(
    game_state: GameState,
    scenario_data: dict,
    llm_config: dict,
    graph_tools: GraphTools | None,
    memory_window: int = 10,
    difficulty: str = "MEDIUM",
) -> dict:
    """Create all commander agents from scenario data."""
    agents = {}
    for side_str, force_data in scenario_data.get("forces", {}).items():
        for cmd_data in force_data.get("commanders", []):
            commander = game_state.commanders.get(cmd_data["id"])
            if not commander:
                continue
            if commander.rank == "Theater":
                agents[commander.id] = TheaterCommander(
                    commander=commander, llm_config=llm_config,
                    graph_tools=graph_tools, memory_window=memory_window,
                    difficulty=difficulty,
                )
            else:
                agents[commander.id] = BattalionCommander(
                    commander=commander, llm_config=llm_config,
                    graph_tools=graph_tools, memory_window=memory_window,
                    difficulty=difficulty,
                )
    return agents


def _build_game_config(data: dict) -> GameConfig:
    """Parse game config from request data."""
    return GameConfig(
        player_side=data.get("player_side"),
        command_mode=CommandMode(data.get("command_mode", "HYBRID")),
        fog_mode=FogMode(data.get("fog_mode", "SOFT")),
        ai_difficulty=AIDifficulty(data.get("ai_difficulty", "MEDIUM")),
    )


def _difficulty_llm_overrides(difficulty: AIDifficulty) -> dict:
    """Return LLM config overrides based on difficulty."""
    if difficulty == AIDifficulty.EASY:
        return {"use_llm": False}
    if difficulty == AIDifficulty.HARD:
        return {"temperature": 0.0, "memory_window": 15}
    return {"temperature": 0.3, "memory_window": 5}


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
    domain = scenario_data.get("domain", "military")
    game_config = _build_game_config(data)

    settings = Settings()
    db_path = str(Path(settings.DB_PATH).parent / f"sim_{sim_id}.db")
    replay_store = ReplayStore(db_path)
    replay_store.create_simulation(scenario_name, scenario_data.get("config", {}))

    if domain != "military":
        # Business or other domain — use DomainRegistry + TurnLoop
        from app.core.domain_registry import get as get_domain
        try:
            import app.domains.business  # noqa: F401 — ensure registered
        except ImportError:
            pass

        factory = get_domain(domain)
        state = factory.create_state(scenario_data)
        engines = factory.create_engines(scenario_data, {"rng_seed": 42})
        agents = factory.create_agents(scenario_data, {
            "use_llm": bool(settings.LLM_API_KEY),
            "doctrine_override": None,
        })

        from app.core.turn_loop import TurnLoop
        turn_loop = TurnLoop(
            state=state,
            command_orchestrator=engines.get("command_orchestrator"),
            mover=engines.get("mover"),
            interaction_resolver=engines.get("interaction_resolver"),
            constraints=engines.get("constraints"),
            victory_checker=engines.get("victory_checker"),
            agents=agents,
        )

        _simulations[sim_id] = {
            "turn_loop": turn_loop,
            "game_state": state,
            "status": "created",
            "thread": None,
            "lock": threading.Lock(),
            "scenario_name": scenario_name,
            "domain": domain,
            "max_turns": scenario_data.get("config", {}).get("max_turns", 72),
        }
        return jsonify({"simulation_id": sim_id, "status": "created", "domain": domain}), 201

    # Military domain — existing code path
    game_state = GameState(scenario_data)

    # Create relationship graph
    rel_graph = RelationshipGraph()
    rel_graph.load_from_scenario(scenario_data, game_state)
    graph_tools = GraphTools(rel_graph)

    # Create agents with difficulty-aware config
    llm_config = settings.get_llm_config()
    diff_overrides = _difficulty_llm_overrides(game_config.ai_difficulty)
    if not diff_overrides.get("use_llm", True):
        llm_config = {**llm_config, "api_key": ""}
    else:
        llm_config = {**llm_config, "temperature": diff_overrides.get("temperature", 0.0)}

    agents = _create_agents(
        game_state, scenario_data, llm_config, graph_tools,
        memory_window=diff_overrides.get("memory_window", 10),
        difficulty=game_config.ai_difficulty.value,
    )

    # Create Phase 2 engines
    intel_engine = IntelEngine()
    supply_engine = SupplyEngine()
    air_engine = AirEngine()
    adjudicator = None
    if llm_config.get("api_key"):
        adjudicator = Adjudicator(llm_config)
        if game_config.player_side:
            adjudicator.set_dialogue_generator(game_config.player_side, scenario_name)

    # Create turn manager
    turn_manager = TurnManager(
        game_state=game_state,
        agents=agents,
        constraint_engine=ConstraintEngine(),
        combat_resolver=CombatResolver(),
        movement_engine=MovementEngine(),
        replay_store=replay_store,
        relationship_graph=rel_graph,
        intel_engine=intel_engine,
        supply_engine=supply_engine,
        air_engine=air_engine,
        adjudicator=adjudicator,
        simulation_id=sim_id,
        log_dir=settings.LOG_DIR,
    )

    # Wire up human commander for player mode
    human_commander = None
    if game_config.player_side:
        human_commander = HumanCommander(
            side=game_config.player_side,
            command_mode=game_config.command_mode,
        )
        turn_manager.human_commander = human_commander

    _simulations[sim_id] = {
        "turn_manager": turn_manager,
        "game_state": game_state,
        "status": "created",
        "thread": None,
        "lock": threading.Lock(),
        "scenario_name": scenario_name,
        "domain": "military",
        "max_turns": scenario_data.get("config", {}).get("max_turns", 72),
        "game_config": game_config,
        "human_commander": human_commander,
    }

    mode = "player" if game_config.player_side else "observer"
    return jsonify({
        "simulation_id": sim_id,
        "status": "created",
        "domain": "military",
        "mode": mode,
        "game_config": game_config.model_dump(),
    }), 201


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
            if "turn_loop" in sim:
                # Business/non-military domain
                loop = sim["turn_loop"]
                loop.run_simulation(max_turns=max_turns)
                with sim["lock"]:
                    sim["current_turn"] = loop.state.turn if hasattr(loop.state, "turn") else max_turns
                sim["status"] = "completed"
            else:
                # Military domain
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

    gc = sim.get("game_config")
    result = {
        "simulation_id": sim_id,
        "status": sim["status"],
        "current_turn": sim.get("current_turn", 0),
        "max_turns": sim.get("max_turns", 72),
        "scenario_name": sim.get("scenario_name", ""),
        "mode": "player" if (gc and gc.player_side) else "observer",
        "game_config": gc.model_dump() if gc else None,
    }
    if sim.get("error"):
        result["error"] = sim["error"]
    return jsonify(result)


@simulation_bp.route("/<sim_id>/state", methods=["GET"])
def get_state(sim_id: str):
    """Get current game state or state at specific turn. Optional ?side=BLUE|RED for filtered view."""
    sim = _simulations.get(sim_id)
    if not sim:
        return jsonify({"error": "Simulation not found"}), 404

    side = request.args.get("side")

    with sim["lock"]:
        game_state = sim["game_state"]

        # Side-filtered view (military domain only, requires intel_engine)
        turn_manager = sim.get("turn_manager")
        if side and turn_manager and hasattr(turn_manager, "intel_engine") and turn_manager.intel_engine:
            from app.models.domain import Side as DomainSide
            try:
                domain_side = DomainSide(side)
            except ValueError:
                return jsonify({"error": f"Invalid side '{side}'"}), 400
            filtered = turn_manager.intel_engine.filter_context_for_agent(
                game_state, type("obj", (), {"side": domain_side})()
            )
            state_data = game_state.to_snapshot()
            state_data["view_side"] = side
            state_data["filtered_enemy"] = [
                e if isinstance(e, dict) else e.model_dump()
                for e in filtered.get("known_enemy", [])
            ]
            return jsonify(state_data)

        return jsonify(game_state.to_snapshot())


@simulation_bp.route("/<sim_id>/narrative", methods=["GET"])
def get_narrative(sim_id: str):
    """Get narrative for a specific turn."""
    sim = _simulations.get(sim_id)
    if not sim:
        return jsonify({"error": "Simulation not found"}), 404

    turn = request.args.get("turn", type=int)
    replay_store = sim["turn_manager"].replay_store
    if replay_store and turn is not None:
        narrative_raw = replay_store.get_narrative(sim_id, turn)
        if narrative_raw:
            return jsonify(json.loads(narrative_raw))
    return jsonify({"summary": "", "combat_reports": [], "key_events": []})


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


@simulation_bp.route("/<sim_id>/commands", methods=["POST"])
def submit_commands(sim_id: str):
    """Submit player commands for the current turn."""
    sim = _simulations.get(sim_id)
    if not sim:
        return jsonify({"error": "Simulation not found"}), 404

    hc = sim.get("human_commander")
    if not hc:
        return jsonify({"error": "Not a player game (no player_side configured)"}), 400

    data = request.get_json() or {}
    orders_raw = data.get("orders", [])
    actions_raw = data.get("actions", [])

    # Parse OrderDirectives
    orders = []
    for o in orders_raw:
        obj_hex = None
        if o.get("objective_hex"):
            obj_hex = HexCoord(q=o["objective_hex"]["q"], r=o["objective_hex"]["r"])
        orders.append(OrderDirective(
            order_id=o.get("order_id", str(uuid.uuid4())),
            turn=sim["game_state"].turn + 1,
            issuer_id=o.get("issuer_id", "PLAYER"),
            target_unit_id=o["target_unit_id"],
            mission=MissionType(o["mission"]),
            objective_hex=obj_hex,
            priority=o.get("priority", 3),
            constraints=o.get("constraints", []),
            reasoning=o.get("reasoning", "Player order"),
        ))

    # Parse MilitaryActions
    actions = []
    for a in actions_raw:
        target_hex = None
        if a.get("target_hex"):
            target_hex = HexCoord(q=a["target_hex"]["q"], r=a["target_hex"]["r"])
        actions.append(MilitaryAction(
            action_id=a.get("action_id", str(uuid.uuid4())),
            turn=sim["game_state"].turn + 1,
            commander_id=a.get("commander_id", "PLAYER"),
            unit_id=a["unit_id"],
            action_type=ActionType(a["action_type"]),
            target_hex=target_hex,
            target_unit_id=a.get("target_unit_id"),
            priority=a.get("priority", 3),
            reasoning=a.get("reasoning", "Player action"),
        ))

    errors = hc.validate_commands(orders=orders, actions=actions)
    if errors:
        return jsonify({"error": "Invalid commands", "details": errors}), 400

    if orders:
        hc.submit_orders(orders)
    if actions:
        hc.submit_actions(actions)

    return jsonify({
        "accepted": True,
        "orders_count": len(orders),
        "actions_count": len(actions),
    })


@simulation_bp.route("/<sim_id>/step", methods=["POST"])
def step_turn(sim_id: str):
    """Advance exactly one turn synchronously. Returns turn result."""
    sim = _simulations.get(sim_id)
    if not sim:
        return jsonify({"error": "Simulation not found"}), 404

    if sim["status"] == "running":
        return jsonify({"error": "Simulation is running in auto-play mode"}), 400

    turn_manager = sim.get("turn_manager")
    if not turn_manager:
        return jsonify({"error": "Step mode not supported for this domain"}), 400

    sim["status"] = "running"
    try:
        turn_result = turn_manager.step_turn()
        victory = turn_manager._check_victory()
        sim["current_turn"] = sim["game_state"].turn
        sim["status"] = "completed" if victory else "waiting_for_commands"

        return jsonify({
            "turn": turn_result.turn,
            "phase_results": {k.value: v for k, v in turn_result.phase_results.items()},
            "movements": len(turn_result.movements),
            "combats": len(turn_result.combats),
            "destroyed_units": turn_result.destroyed_units,
            "narrative": turn_result.narrative,
            "enemy_dialogue": turn_result.enemy_dialogue,
            "staff_briefing": turn_result.staff_briefing,
            "event_reactions": turn_result.event_reactions,
            "victory": victory,
            "status": sim["status"],
        })
    except Exception as e:
        logger.error("Step turn failed for %s: %s", sim_id, e)
        sim["status"] = "error"
        sim["error"] = str(e)
        return jsonify({"error": str(e)}), 500


@simulation_bp.route("/<sim_id>/available-actions", methods=["GET"])
def get_available_actions(sim_id: str):
    """Return valid actions for the player's units."""
    sim = _simulations.get(sim_id)
    if not sim:
        return jsonify({"error": "Simulation not found"}), 404

    turn_manager = sim.get("turn_manager")
    if not turn_manager:
        return jsonify({"error": "Not supported for this domain"}), 400

    if not turn_manager.human_commander:
        return jsonify({"error": "Not a player game"}), 400

    return jsonify(turn_manager.get_available_actions())


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
