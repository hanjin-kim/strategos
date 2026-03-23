from __future__ import annotations
import logging
import time
from pydantic import BaseModel

from app.batch.parameter_set import ParameterSet, apply_to_scenario
from app.engine.game_state import GameState
from app.engine.turn_manager import TurnManager
from app.engine.constraint_engine import ConstraintEngine
from app.engine.combat_resolver import CombatResolver
from app.engine.movement_engine import MovementEngine
from app.engine.intel_engine import IntelEngine
from app.engine.supply_engine import SupplyEngine
from app.engine.air_engine import AirEngine
from app.agents.theater_commander import TheaterCommander
from app.agents.division_commander import DivisionCommander
from app.agents.battalion_commander import BattalionCommander
from app.graph.relationship_graph import RelationshipGraph
from app.graph.graph_tools import GraphTools
from app.models.domain import Side

logger = logging.getLogger(__name__)


class RunResult(BaseModel):
    """Result of a single simulation run."""
    run_index: int
    parameter_set_name: str
    rng_seed: int
    status: str = "COMPLETED"  # COMPLETED, FAILED
    error_message: str = ""
    winner: str = ""  # "BLUE", "RED", "DRAW"
    total_turns: int = 0
    blue_units_remaining: int = 0
    red_units_remaining: int = 0
    blue_avg_strength: float = 0.0
    red_avg_strength: float = 0.0
    execution_time_ms: int = 0
    reproducibility_level: str = "DETERMINISTIC"  # DETERMINISTIC (LLM-free) or STATISTICAL (LLM)


class BatchResult(BaseModel):
    """Aggregate result of a batch of simulation runs."""
    batch_id: str
    scenario_name: str
    total_runs: int
    completed_runs: int = 0
    failed_runs: int = 0
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, PARTIAL
    runs: list[RunResult] = []
    execution_time_ms: int = 0


class BatchRunner:
    """Runs N simulations with parameter variations sequentially."""

    def __init__(self, scenario_data: dict, scenario_name: str = ""):
        self.scenario_data = scenario_data
        self.scenario_name = scenario_name

    def run_batch(
        self,
        parameter_sets: list[ParameterSet],
        batch_id: str = "",
        callback=None,  # callback(run_index, total, run_result)
    ) -> BatchResult:
        """Execute all parameter sets sequentially."""
        import uuid
        if not batch_id:
            batch_id = str(uuid.uuid4())[:8]

        result = BatchResult(
            batch_id=batch_id,
            scenario_name=self.scenario_name,
            total_runs=len(parameter_sets),
            status="RUNNING",
        )

        batch_start = time.time()

        for i, params in enumerate(parameter_sets):
            run_start = time.time()
            try:
                run_result = self._execute_single_run(i, params)
            except Exception as e:
                logger.error("Run %d failed: %s", i, e)
                run_result = RunResult(
                    run_index=i,
                    parameter_set_name=params.name,
                    rng_seed=params.rng_seed,
                    status="FAILED",
                    error_message=str(e),
                    execution_time_ms=int((time.time() - run_start) * 1000),
                )

            result.runs.append(run_result)
            if run_result.status == "COMPLETED":
                result.completed_runs += 1
            else:
                result.failed_runs += 1

            if callback:
                callback(i, len(parameter_sets), run_result)

        result.execution_time_ms = int((time.time() - batch_start) * 1000)
        result.status = "COMPLETED" if result.failed_runs == 0 else "PARTIAL"
        return result

    def _execute_single_run(self, run_index: int, params: ParameterSet) -> RunResult:
        """Execute a single simulation run with given parameters."""
        run_start = time.time()

        # Apply parameters to scenario (creates a deep copy)
        modified_scenario = apply_to_scenario(self.scenario_data, params)

        # Create fresh GameState
        game_state = GameState(modified_scenario)

        # Create engines (all fresh instances)
        constraint_engine = ConstraintEngine()
        combat_resolver = CombatResolver(rng_seed=params.rng_seed)
        movement_engine = MovementEngine()
        intel_engine = IntelEngine()
        supply_engine = SupplyEngine()
        air_engine = AirEngine(rng_seed=params.rng_seed + 1000)  # offset to avoid correlation

        # Create relationship graph
        relationship_graph = RelationshipGraph()
        relationship_graph.load_from_scenario(modified_scenario, game_state)
        graph_tools = GraphTools(relationship_graph)

        # Create agents — use llm_config with empty api_key for LLM-free mode
        llm_config: dict = {"api_key": "", "base_url": "", "model": ""}
        if params.use_llm:
            from app.config import Settings
            settings = Settings()
            llm_config = {
                "api_key": settings.LLM_API_KEY,
                "base_url": settings.LLM_BASE_URL,
                "model": settings.LLM_MODEL_NAME,
            }

        agents = self._create_agents(game_state, llm_config, graph_tools)

        # Create TurnManager with all engines
        turn_manager = TurnManager(
            game_state=game_state,
            agents=agents,
            constraint_engine=constraint_engine,
            combat_resolver=combat_resolver,
            movement_engine=movement_engine,
            intel_engine=intel_engine,
            supply_engine=supply_engine,
            air_engine=air_engine,
            relationship_graph=relationship_graph,
            simulation_id=f"batch_{run_index}",
        )

        # Run simulation
        final_state = turn_manager.run_simulation(max_turns=params.max_turns)
        elapsed_ms = int((time.time() - run_start) * 1000)

        # Extract results
        winner = self._determine_winner(final_state)

        from app.models.domain import UnitStatus
        blue_units = [
            u for u in final_state.units.values()
            if u.side == Side.BLUE and u.status not in (UnitStatus.DESTROYED, UnitStatus.ROUTED)
        ]
        red_units = [
            u for u in final_state.units.values()
            if u.side == Side.RED and u.status not in (UnitStatus.DESTROYED, UnitStatus.ROUTED)
        ]

        return RunResult(
            run_index=run_index,
            parameter_set_name=params.name,
            rng_seed=params.rng_seed,
            winner=winner,
            total_turns=final_state.turn,
            blue_units_remaining=len(blue_units),
            red_units_remaining=len(red_units),
            blue_avg_strength=round(sum(u.strength for u in blue_units) / max(len(blue_units), 1), 3),
            red_avg_strength=round(sum(u.strength for u in red_units) / max(len(red_units), 1), 3),
            execution_time_ms=elapsed_ms,
            reproducibility_level="STATISTICAL" if params.use_llm else "DETERMINISTIC",
        )

    def _create_agents(self, game_state: GameState, llm_config: dict, graph_tools: GraphTools) -> dict:
        """Create agents for a simulation run."""
        agents = {}
        for cmd_id, commander in game_state.commanders.items():
            if commander.rank == "Theater":
                agent = TheaterCommander(commander, llm_config, graph_tools=graph_tools)
            elif commander.rank == "Division":
                agent = DivisionCommander(commander, llm_config, graph_tools=graph_tools)
            else:  # Battalion
                agent = BattalionCommander(commander, llm_config, graph_tools=graph_tools)
            agents[cmd_id] = agent
        return agents

    def _determine_winner(self, game_state: GameState) -> str:
        """Determine winner based on remaining active units."""
        from app.models.domain import UnitStatus
        blue_active = sum(
            1 for u in game_state.units.values()
            if u.side == Side.BLUE and u.status not in (UnitStatus.DESTROYED, UnitStatus.ROUTED)
        )
        red_active = sum(
            1 for u in game_state.units.values()
            if u.side == Side.RED and u.status not in (UnitStatus.DESTROYED, UnitStatus.ROUTED)
        )
        if blue_active == 0 and red_active == 0:
            return "DRAW"
        if blue_active == 0:
            return "RED"
        if red_active == 0:
            return "BLUE"
        # No decisive outcome — compare strength
        blue_str = sum(
            u.strength for u in game_state.units.values()
            if u.side == Side.BLUE and u.status not in (UnitStatus.DESTROYED, UnitStatus.ROUTED)
        )
        red_str = sum(
            u.strength for u in game_state.units.values()
            if u.side == Side.RED and u.status not in (UnitStatus.DESTROYED, UnitStatus.ROUTED)
        )
        if blue_str > red_str * 1.5:
            return "BLUE"
        if red_str > blue_str * 1.5:
            return "RED"
        return "DRAW"

    def estimate_cost(self, parameter_sets: list[ParameterSet]) -> dict:
        """Estimate LLM API cost for batch run."""
        llm_runs = sum(1 for p in parameter_sets if p.use_llm)
        free_runs = len(parameter_sets) - llm_runs
        # Count agents from scenario
        agent_count = sum(
            len(force.get("commanders", []))
            for force in self.scenario_data.get("forces", {}).values()
        ) + 1  # +1 for adjudicator
        avg_turns = sum(p.max_turns for p in parameter_sets) / max(len(parameter_sets), 1)
        total_llm_calls = llm_runs * avg_turns * agent_count
        estimated_cost_usd = total_llm_calls * 0.002  # rough estimate per call
        return {
            "total_runs": len(parameter_sets),
            "llm_runs": llm_runs,
            "free_runs": free_runs,
            "estimated_llm_calls": int(total_llm_calls),
            "estimated_cost_usd": round(estimated_cost_usd, 2),
            "estimated_time_minutes": round(free_runs * 0.08 + llm_runs * avg_turns * 0.3, 1),
        }
