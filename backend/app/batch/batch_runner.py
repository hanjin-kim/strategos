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


def _unit_side(u) -> str:
    """Return unit side as plain string regardless of enum or str."""
    s = u.side
    return s.value if hasattr(s, "value") else str(s)


def _unit_status(u) -> str:
    """Return unit status as plain string regardless of enum or str."""
    st = u.status
    return st.value if hasattr(st, "value") else str(st)


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

    def __init__(self, scenario_data: dict, scenario_name: str = "", doctrine_override: str | None = None):
        self.scenario_data = scenario_data
        self.scenario_name = scenario_name
        self.doctrine_override = doctrine_override

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

        # Route non-military domains to TurnLoop
        domain = modified_scenario.get("domain", "military")
        if domain != "military":
            return self._execute_domain_run(run_index, params, domain, modified_scenario)

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

        agents = self._create_agents(game_state, llm_config, graph_tools, params)

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

    def _execute_domain_run(
        self, run_index: int, params: ParameterSet, domain: str, modified_scenario: dict
    ) -> RunResult:
        """Execute a run using the domain-agnostic TurnLoop."""
        import time as _time
        from app.core.domain_registry import get as get_domain
        from app.core.turn_loop import TurnLoop

        run_start = _time.time()
        # Auto-import domain module to trigger registration side-effect if needed
        from app.core.domain_registry import list_domains
        if domain not in list_domains():
            try:
                import importlib
                mod = importlib.import_module(f"app.domains.{domain}")
                importlib.reload(mod)
            except ImportError:
                pass
        factory = get_domain(domain)
        params_dict = params.model_dump() if hasattr(params, "model_dump") else {}
        state = factory.create_state(modified_scenario)
        engines = factory.create_engines(modified_scenario, params_dict)
        agents = factory.create_agents(modified_scenario, params_dict)

        loop = TurnLoop(
            state=state,
            command_orchestrator=engines.get("command_orchestrator"),
            mover=engines.get("mover"),
            interaction_resolver=engines.get("interaction_resolver"),
            constraints=engines.get("constraints"),
            victory_checker=engines.get("victory_checker"),
            agents=agents,
        )

        result = loop.run_simulation(max_turns=params.max_turns)
        elapsed = int((_time.time() - run_start) * 1000)

        winner = self._determine_winner_generic(state)

        dead_statuses = ("DESTROYED", "ROUTED", "BANKRUPT")

        def _strength(u) -> float:
            if hasattr(u, "market_share"):
                return u.market_share
            return getattr(u, "strength", 0.0)

        # Discover sides dynamically (works for BLUE/RED or Netflix/DisneyPlus)
        sides_found: list[str] = []
        if hasattr(state, "units"):
            sides_found = sorted(set(_unit_side(u) for u in state.units.values()))
        side_a = sides_found[0] if len(sides_found) > 0 else "BLUE"
        side_b = sides_found[1] if len(sides_found) > 1 else "RED"

        a_units = [u for u in state.units.values() if _unit_side(u) == side_a and _unit_status(u) not in dead_statuses] if hasattr(state, "units") else []
        b_units = [u for u in state.units.values() if _unit_side(u) == side_b and _unit_status(u) not in dead_statuses] if hasattr(state, "units") else []

        return RunResult(
            run_index=run_index,
            parameter_set_name=params.name,
            rng_seed=params.rng_seed,
            winner=winner,
            total_turns=result.get("total_turns", 0),
            blue_units_remaining=len(a_units),
            red_units_remaining=len(b_units),
            blue_avg_strength=round(
                sum(_strength(u) for u in a_units) / max(len(a_units), 1), 3
            ),
            red_avg_strength=round(
                sum(_strength(u) for u in b_units) / max(len(b_units), 1), 3
            ),
            execution_time_ms=elapsed,
            reproducibility_level="STATISTICAL" if params.use_llm else "DETERMINISTIC",
        )

    def _create_agents(self, game_state: GameState, llm_config: dict, graph_tools: GraphTools, params: ParameterSet | None = None) -> dict:
        """Create agents for a simulation run."""
        agents = {}
        for cmd_id, commander in game_state.commanders.items():
            kwargs: dict = {"graph_tools": graph_tools}
            if self.doctrine_override:
                kwargs["doctrine_override"] = self.doctrine_override
            if commander.rank == "Theater":
                agent = TheaterCommander(commander, llm_config, **kwargs)
            elif commander.rank == "Division":
                agent = DivisionCommander(commander, llm_config, **kwargs)
            else:  # Battalion
                agent = BattalionCommander(commander, llm_config, **kwargs)
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
        if blue_str > red_str * 1.15:
            return "BLUE"
        if red_str > blue_str * 1.15:
            return "RED"
        return "DRAW"

    def _determine_winner_generic(self, state) -> str:
        """Determine winner for any domain state (military or business)."""
        if not hasattr(state, "units"):
            return "DRAW"
        dead_statuses = ("DESTROYED", "ROUTED", "BANKRUPT")

        def active(side_str: str) -> list:
            return [
                u for u in state.units.values()
                if _unit_side(u) == side_str and _unit_status(u) not in dead_statuses
            ]

        def score(units) -> float:
            total = 0.0
            for u in units:
                if hasattr(u, "market_share"):
                    total += u.market_share
                else:
                    total += getattr(u, "strength", 0.0)
            return total

        # Discover sides dynamically
        all_sides = sorted(set(_unit_side(u) for u in state.units.values()))
        if len(all_sides) < 2:
            return "DRAW"

        side_a, side_b = all_sides[0], all_sides[1]
        a_units = active(side_a)
        b_units = active(side_b)

        if not a_units and not b_units:
            return "DRAW"
        if not a_units:
            return side_b
        if not b_units:
            return side_a

        a_score = score(a_units)
        b_score = score(b_units)
        if a_score > b_score * 1.15:
            return side_a
        if b_score > a_score * 1.15:
            return side_b
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
