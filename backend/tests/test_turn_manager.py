from __future__ import annotations
import pytest
from pathlib import Path
from app.models.domain import (
    Commander, Unit, Side, UnitType, UnitSize, UnitStatus,
    HexCoord, TerrainHex, TerrainType, Force,
)
from app.models.actions import MilitaryAction, ActionType, OrderDirective, MissionType
from app.models.simulation import TurnPhase, TurnResult, CombatOutcome
from app.engine.game_state import GameState
from app.engine.constraint_engine import ConstraintEngine
from app.engine.combat_resolver import CombatResolver
from app.engine.movement_engine import MovementEngine
from app.engine.turn_manager import TurnManager
from app.agents.theater_commander import TheaterCommander
from app.agents.battalion_commander import BattalionCommander
from app.memory.replay_store import ReplayStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_unit(uid: str, side: Side, q: int, r: int, status: UnitStatus = UnitStatus.ACTIVE) -> Unit:
    return Unit(
        id=uid,
        name=f"Unit-{uid}",
        side=side,
        unit_type=UnitType.INFANTRY,
        size=UnitSize.BATTALION,
        position=HexCoord(q=q, r=r),
        strength=1.0,
        morale=0.8,
        movement_points=2,
        max_movement_points=2,
        attack_power=10.0,
        defense_power=10.0,
        effective_range=1,
        ammo=1.0,
        fuel=1.0,
        status=status,
    )


def make_terrain_hex(q: int, r: int, terrain_type: TerrainType = TerrainType.PLAIN) -> TerrainHex:
    return TerrainHex(
        coord=HexCoord(q=q, r=r),
        terrain_type=terrain_type,
        elevation=0,
        movement_cost=1,
        defense_modifier=1.0,
    )


def make_game_state() -> GameState:
    """
    Small 5x5-ish terrain grid with 2 BLUE and 2 RED units.

    Hex layout (q, r):
      BLUE: blue1 at (0,0), blue2 at (1,0)
      RED:  red1  at (3,0), red2  at (4,0)
    """
    gs = GameState()
    # Build a small terrain grid so pathfinding works
    for q in range(-1, 6):
        for r in range(-1, 6):
            coord = HexCoord(q=q, r=r)
            gs.terrain[coord] = make_terrain_hex(q, r)

    # Units
    gs.units["blue1"] = make_unit("blue1", Side.BLUE, 0, 0)
    gs.units["blue2"] = make_unit("blue2", Side.BLUE, 1, 0)
    gs.units["red1"] = make_unit("red1", Side.RED, 3, 0)
    gs.units["red2"] = make_unit("red2", Side.RED, 4, 0)

    # Commanders
    gs.commanders["tcmd_blue"] = Commander(
        id="tcmd_blue", name="Blue Theater", side=Side.BLUE,
        rank="Theater", unit_id="blue1",
    )
    gs.commanders["bcmd_blue1"] = Commander(
        id="bcmd_blue1", name="Blue Bn1", side=Side.BLUE,
        rank="Battalion", unit_id="blue1",
    )
    gs.commanders["bcmd_blue2"] = Commander(
        id="bcmd_blue2", name="Blue Bn2", side=Side.BLUE,
        rank="Battalion", unit_id="blue2",
    )
    gs.commanders["tcmd_red"] = Commander(
        id="tcmd_red", name="Red Theater", side=Side.RED,
        rank="Theater", unit_id="red1",
    )
    gs.commanders["bcmd_red1"] = Commander(
        id="bcmd_red1", name="Red Bn1", side=Side.RED,
        rank="Battalion", unit_id="red1",
    )
    gs.commanders["bcmd_red2"] = Commander(
        id="bcmd_red2", name="Red Bn2", side=Side.RED,
        rank="Battalion", unit_id="red2",
    )

    # Forces
    gs.forces[Side.BLUE] = Force(
        side=Side.BLUE, name="Blue Force",
        commander_ids=["tcmd_blue", "bcmd_blue1", "bcmd_blue2"],
        unit_ids=["blue1", "blue2"],
    )
    gs.forces[Side.RED] = Force(
        side=Side.RED, name="Red Force",
        commander_ids=["tcmd_red", "bcmd_red1", "bcmd_red2"],
        unit_ids=["red1", "red2"],
    )

    return gs


def make_agents(gs: GameState) -> dict:
    """
    Create agents with llm_config={} (no api_key) so _client=None,
    triggering fallback mode automatically.
    """
    agents = {}

    # BLUE theater
    agents["tcmd_blue"] = TheaterCommander(
        commander=gs.commanders["tcmd_blue"],
        llm_config={},
    )
    # BLUE battalions
    agents["bcmd_blue1"] = BattalionCommander(
        commander=gs.commanders["bcmd_blue1"],
        llm_config={},
    )
    agents["bcmd_blue2"] = BattalionCommander(
        commander=gs.commanders["bcmd_blue2"],
        llm_config={},
    )
    # RED theater
    agents["tcmd_red"] = TheaterCommander(
        commander=gs.commanders["tcmd_red"],
        llm_config={},
    )
    # RED battalions
    agents["bcmd_red1"] = BattalionCommander(
        commander=gs.commanders["bcmd_red1"],
        llm_config={},
    )
    agents["bcmd_red2"] = BattalionCommander(
        commander=gs.commanders["bcmd_red2"],
        llm_config={},
    )

    return agents


def make_turn_manager(
    gs: GameState,
    agents: dict,
    replay_store: ReplayStore | None = None,
    sim_id: str = "test-sim",
    log_dir: str | None = None,
    tmp_path: Path | None = None,
) -> TurnManager:
    if log_dir is None and tmp_path is not None:
        log_dir = str(tmp_path / "logs")
    elif log_dir is None:
        log_dir = "/tmp/test_turn_manager_logs"

    return TurnManager(
        game_state=gs,
        agents=agents,
        constraint_engine=ConstraintEngine(),
        combat_resolver=CombatResolver(rng_seed=42),
        movement_engine=MovementEngine(),
        replay_store=replay_store,
        simulation_id=sim_id,
        log_dir=log_dir,
    )


# ---------------------------------------------------------------------------
# 1. run_simulation(max_turns=3) completes without error
# ---------------------------------------------------------------------------

def test_run_simulation_completes(tmp_path):
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents, tmp_path=tmp_path)

    result_state = tm.run_simulation(max_turns=3)
    assert result_state is gs  # same object returned


# ---------------------------------------------------------------------------
# 2. After 3 turns, game_state.turn == 3
# ---------------------------------------------------------------------------

def test_run_simulation_turn_counter(tmp_path):
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents, tmp_path=tmp_path)

    tm.run_simulation(max_turns=3)
    assert gs.turn == 3


# ---------------------------------------------------------------------------
# 3. Each turn produces a TurnResult with movements and combats fields
# ---------------------------------------------------------------------------

def test_turn_results_have_required_fields(tmp_path):
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents, tmp_path=tmp_path)

    tm.run_simulation(max_turns=3)
    results = tm.turn_results

    assert len(results) == 3
    for tr in results:
        assert isinstance(tr, TurnResult)
        assert isinstance(tr.movements, list)
        assert isinstance(tr.combats, list)
        assert isinstance(tr.destroyed_units, list)
        assert TurnPhase.COMMAND in tr.phase_results
        assert TurnPhase.EXECUTION in tr.phase_results
        assert TurnPhase.RESOLUTION in tr.phase_results


# ---------------------------------------------------------------------------
# 4. Theater -> OrderDirective -> Battalion -> MilitaryAction flow (fallback)
# ---------------------------------------------------------------------------

def test_command_phase_flow(tmp_path):
    """
    With _client=None, TheaterCommander falls back to DEFEND orders.
    BattalionCommander receives those orders and uses RuleBasedFallback.
    Result: all_actions should be non-empty MilitaryActions.
    """
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents, tmp_path=tmp_path)

    # Manually advance turn so game_state.turn is set
    gs.advance_turn()
    actions = tm._command_phase()

    assert len(actions) > 0
    for action in actions:
        assert isinstance(action, MilitaryAction)


# ---------------------------------------------------------------------------
# 5. Snapshot saved per turn in ReplayStore
# ---------------------------------------------------------------------------

def test_snapshots_saved_per_turn(tmp_path):
    gs = make_game_state()
    agents = make_agents(gs)
    db_path = str(tmp_path / "test.db")
    replay_store = ReplayStore(db_path=db_path)
    sim_id = replay_store.create_simulation("test-scenario")

    tm = make_turn_manager(gs, agents, replay_store=replay_store, sim_id=sim_id, tmp_path=tmp_path)
    tm.run_simulation(max_turns=3)

    turns = replay_store.list_turns(sim_id)
    assert turns == [1, 2, 3]


# ---------------------------------------------------------------------------
# 6. Victory condition: remove all RED units -> simulation stops early
# ---------------------------------------------------------------------------

def test_victory_condition_stops_early(tmp_path):
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents, tmp_path=tmp_path)

    # Destroy all RED units before simulation starts
    gs.units["red1"] = gs.units["red1"].model_copy(update={"status": UnitStatus.DESTROYED})
    gs.units["red2"] = gs.units["red2"].model_copy(update={"status": UnitStatus.DESTROYED})

    tm.run_simulation(max_turns=10)

    # Should have stopped after turn 1 (victory detected after first turn)
    assert gs.turn < 10


# ---------------------------------------------------------------------------
# 7. JSONL log file created
# ---------------------------------------------------------------------------

def test_jsonl_log_file_created(tmp_path):
    gs = make_game_state()
    agents = make_agents(gs)
    log_dir = str(tmp_path / "logs")
    tm = make_turn_manager(gs, agents, log_dir=log_dir, tmp_path=tmp_path)

    tm.run_simulation(max_turns=2)

    log_file = Path(log_dir) / "sim_test-sim.jsonl"
    assert log_file.exists()

    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 2
    import json
    for line in lines:
        entry = json.loads(line)
        assert "turn" in entry
        assert "actions" in entry
        assert "combats" in entry


# ---------------------------------------------------------------------------
# 8. Callback is called each turn
# ---------------------------------------------------------------------------

def test_callback_called_each_turn(tmp_path):
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents, tmp_path=tmp_path)

    called_turns = []

    def callback(turn: int, state: GameState) -> None:
        called_turns.append(turn)

    tm.run_simulation(max_turns=3, callback=callback)

    assert called_turns == [1, 2, 3]


# ---------------------------------------------------------------------------
# 9. _collect_engagements: attack action triggers combat
# ---------------------------------------------------------------------------

def test_collect_engagements_attack_action(tmp_path):
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents, tmp_path=tmp_path)

    # Place blue1 adjacent to red1 (distance=1)
    gs.units["blue1"] = gs.units["blue1"].model_copy(update={"position": HexCoord(q=2, r=0)})

    attack_action = MilitaryAction(
        action_id="atk1",
        turn=1,
        commander_id="bcmd_blue1",
        unit_id="blue1",
        action_type=ActionType.ATTACK,
        target_unit_id="red1",
    )

    engagements = tm._collect_engagements([], [attack_action])

    assert len(engagements) == 1
    attackers, defenders, terrain = engagements[0]
    assert attackers[0].id == "blue1"
    assert defenders[0].id == "red1"
    assert terrain is not None


# ---------------------------------------------------------------------------
# 10. _resolution_phase: combat outcomes applied (strength reduced)
# ---------------------------------------------------------------------------

def test_resolution_phase_reduces_strength(tmp_path):
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents, tmp_path=tmp_path)

    # Place blue1 adjacent to red1
    gs.units["blue1"] = gs.units["blue1"].model_copy(update={"position": HexCoord(q=2, r=0)})

    attack_action = MilitaryAction(
        action_id="atk1",
        turn=1,
        commander_id="bcmd_blue1",
        unit_id="blue1",
        action_type=ActionType.ATTACK,
        target_unit_id="red1",
    )

    blue1_strength_before = gs.units["blue1"].strength
    red1_strength_before = gs.units["red1"].strength

    combats, destroyed = tm._resolution_phase([], [attack_action])

    assert len(combats) > 0
    # At least one side should have reduced strength
    blue1_after = gs.units["blue1"].strength
    red1_after = gs.units["red1"].strength
    assert blue1_after < blue1_strength_before or red1_after < red1_strength_before


# ---------------------------------------------------------------------------
# 11. _check_victory: returns False when both sides have active units
# ---------------------------------------------------------------------------

def test_check_victory_false_when_both_sides_active(tmp_path):
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents, tmp_path=tmp_path)

    assert tm._check_victory() is False


# ---------------------------------------------------------------------------
# 12. _check_victory: returns True when one side is eliminated
# ---------------------------------------------------------------------------

def test_check_victory_true_when_side_eliminated(tmp_path):
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents, tmp_path=tmp_path)

    gs.units["red1"] = gs.units["red1"].model_copy(update={"status": UnitStatus.DESTROYED})
    gs.units["red2"] = gs.units["red2"].model_copy(update={"status": UnitStatus.DESTROYED})

    assert tm._check_victory() is True


# ---------------------------------------------------------------------------
# 13. turn_results property returns accumulated results
# ---------------------------------------------------------------------------

def test_turn_results_property(tmp_path):
    gs = make_game_state()
    agents = make_agents(gs)
    tm = make_turn_manager(gs, agents, tmp_path=tmp_path)

    assert tm.turn_results == []
    tm.run_simulation(max_turns=2)
    assert len(tm.turn_results) == 2


# ---------------------------------------------------------------------------
# 14. ReplayStore: actions saved per turn
# ---------------------------------------------------------------------------

def test_actions_saved_in_replay_store(tmp_path):
    gs = make_game_state()
    agents = make_agents(gs)
    db_path = str(tmp_path / "actions.db")
    replay_store = ReplayStore(db_path=db_path)
    sim_id = replay_store.create_simulation("test-scenario")

    tm = make_turn_manager(gs, agents, replay_store=replay_store, sim_id=sim_id, tmp_path=tmp_path)
    tm.run_simulation(max_turns=2)

    # Each turn should have action_log entries (may be 0 if all held)
    # Just verify the method runs without error
    actions_turn1 = replay_store.get_turn_actions(sim_id, 1)
    assert isinstance(actions_turn1, list)
