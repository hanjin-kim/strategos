from __future__ import annotations

import pytest
from app.models.domain import (
    Commander, Unit, Side, UnitType, UnitSize, UnitStatus,
    HexCoord, TerrainHex, TerrainType, Force,
)
from app.models.actions import MilitaryAction, ActionType
from app.models.simulation import TurnPhase
from app.models.air import AirAsset, AirMission, AirMissionType, SortiePool
from app.engine.game_state import GameState
from app.engine.constraint_engine import ConstraintEngine
from app.engine.combat_resolver import CombatResolver
from app.engine.movement_engine import MovementEngine
from app.engine.air_engine import AirEngine
from app.engine.turn_manager import TurnManager
from app.agents.theater_commander import TheaterCommander
from app.agents.battalion_commander import BattalionCommander


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_unit(uid: str, side: Side, q: int, r: int, status: UnitStatus = UnitStatus.ACTIVE) -> Unit:
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


def _make_terrain(q: int, r: int) -> TerrainHex:
    return TerrainHex(
        coord=HexCoord(q=q, r=r),
        terrain_type=TerrainType.PLAIN,
        elevation=0,
        movement_cost=1,
        defense_modifier=1.0,
    )


def _make_asset(
    asset_id: str = "f16-1",
    side: Side = Side.BLUE,
    attack_power: float = 10.0,
    defense_against_sam: float = 1.0,
) -> AirAsset:
    return AirAsset(
        id=asset_id,
        name="F-16",
        side=side,
        asset_type="F-16",
        missions_capable=[AirMissionType.CAS, AirMissionType.AIR_SUPERIORITY],
        sortie_count=2,
        attack_power=attack_power,
        defense_against_sam=defense_against_sam,
    )


def _make_pool(side: Side, total: int = 5, remaining: int = 5) -> SortiePool:
    return SortiePool(side=side, total_sorties=total, remaining_sorties=remaining)


def _make_action(
    unit_id: str,
    action_type: ActionType,
    target_hex: HexCoord | None = None,
    target_unit_id: str | None = None,
    commander_id: str = "bcmd_blue",
    turn: int = 1,
) -> MilitaryAction:
    return MilitaryAction(
        action_id="test-action",
        turn=turn,
        commander_id=commander_id,
        unit_id=unit_id,
        action_type=action_type,
        target_hex=target_hex,
        target_unit_id=target_unit_id,
    )


def _make_game_state_with_air() -> GameState:
    gs = GameState()
    for q in range(-1, 7):
        for r in range(-1, 7):
            coord = HexCoord(q=q, r=r)
            gs.terrain[coord] = _make_terrain(q, r)

    gs.units["blue1"] = _make_unit("blue1", Side.BLUE, 0, 0)
    gs.units["red1"] = _make_unit("red1", Side.RED, 3, 0)

    gs.commanders["tcmd_blue"] = Commander(
        id="tcmd_blue", name="Blue Theater", side=Side.BLUE, rank="Theater", unit_id="blue1",
    )
    gs.commanders["tcmd_red"] = Commander(
        id="tcmd_red", name="Red Theater", side=Side.RED, rank="Theater", unit_id="red1",
    )
    gs.commanders["bcmd_blue"] = Commander(
        id="bcmd_blue", name="Blue Bn", side=Side.BLUE, rank="Battalion", unit_id="blue1",
    )
    gs.commanders["bcmd_red"] = Commander(
        id="bcmd_red", name="Red Bn", side=Side.RED, rank="Battalion", unit_id="red1",
    )
    gs.forces[Side.BLUE] = Force(
        side=Side.BLUE, name="Blue", commander_ids=["tcmd_blue", "bcmd_blue"], unit_ids=["blue1"],
    )
    gs.forces[Side.RED] = Force(
        side=Side.RED, name="Red", commander_ids=["tcmd_red", "bcmd_red"], unit_ids=["red1"],
    )

    # Air assets and sortie pools
    gs.air_assets["f16-1"] = _make_asset("f16-1", Side.BLUE)
    gs.sortie_pools[Side.BLUE.value] = _make_pool(Side.BLUE, total=5, remaining=5)

    return gs


def _make_turn_manager(gs: GameState, air_engine: AirEngine | None = None) -> TurnManager:
    constraint_engine = ConstraintEngine()
    combat_resolver = CombatResolver(rng_seed=42)
    movement_engine = MovementEngine()

    # Use llm_config={} so _client=None, triggering fallback mode (matches existing test pattern)
    agents = {
        "tcmd_blue": TheaterCommander(commander=gs.commanders["tcmd_blue"], llm_config={}),
        "tcmd_red": TheaterCommander(commander=gs.commanders["tcmd_red"], llm_config={}),
        "bcmd_blue": BattalionCommander(commander=gs.commanders["bcmd_blue"], llm_config={}),
        "bcmd_red": BattalionCommander(commander=gs.commanders["bcmd_red"], llm_config={}),
    }

    return TurnManager(
        game_state=gs,
        agents=agents,
        constraint_engine=constraint_engine,
        combat_resolver=combat_resolver,
        movement_engine=movement_engine,
        air_engine=air_engine,
        simulation_id="test",
        log_dir="/tmp/test_air_integration_logs",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAirEngineNone:
    """When air_engine=None, existing behavior is unchanged."""

    def test_turn_manager_runs_without_air_engine(self):
        gs = _make_game_state_with_air()
        tm = _make_turn_manager(gs, air_engine=None)
        result = tm._run_turn(1)
        assert result.turn == 1

    def test_no_air_engine_does_not_crash(self):
        gs = _make_game_state_with_air()
        tm = _make_turn_manager(gs, air_engine=None)
        result = tm._run_turn(1)
        assert result is not None


class TestCasModifierInCombat:
    """CAS modifier increases combat effectiveness."""

    def test_cas_modifier_increases_force_ratio(self):
        cr = CombatResolver(rng_seed=42)
        attacker = _make_unit("a1", Side.BLUE, 0, 0)
        defender = _make_unit("d1", Side.RED, 1, 0)
        terrain = _make_terrain(1, 0)

        outcome_no_cas = cr.resolve_combat([attacker], [defender], terrain, cas_modifier=0.0)
        outcome_with_cas = cr.resolve_combat([attacker], [defender], terrain, cas_modifier=0.5)

        # With CAS modifier, force ratio should be higher (50% more attack power)
        assert outcome_with_cas.force_ratio > outcome_no_cas.force_ratio

    def test_cas_modifier_zero_default_unchanged(self):
        cr = CombatResolver(rng_seed=42)
        attacker = _make_unit("a1", Side.BLUE, 0, 0)
        defender = _make_unit("d1", Side.RED, 1, 0)
        terrain = _make_terrain(1, 0)

        outcome_default = cr.resolve_combat([attacker], [defender], terrain)
        outcome_zero = cr.resolve_combat([attacker], [defender], terrain, cas_modifier=0.0)

        assert outcome_default.force_ratio == outcome_zero.force_ratio

    def test_cas_modifier_and_supply_map_compatible(self):
        cr = CombatResolver(rng_seed=42)
        attacker = _make_unit("a1", Side.BLUE, 0, 0)
        defender = _make_unit("d1", Side.RED, 1, 0)
        terrain = _make_terrain(1, 0)

        # Both params can be specified together without error
        outcome = cr.resolve_combat(
            [attacker], [defender], terrain,
            cas_modifier=0.15,
            supply_status_map=None,
        )
        assert outcome is not None


class TestAirMissionResolvesInCommandPhase:
    """Air missions resolve within COMMAND phase, before advance_phase."""

    def test_phase_still_command_after_air_resolution(self):
        """After _collect_air_missions/_extract_cas_modifiers, phase is still COMMAND."""
        gs = _make_game_state_with_air()
        air_engine = AirEngine(rng_seed=42)
        tm = _make_turn_manager(gs, air_engine=air_engine)

        # Simulate what _run_turn does up to the air resolution step
        gs.advance_turn()
        all_actions: list[MilitaryAction] = []
        # Phase is COMMAND at this point
        assert gs.phase == TurnPhase.COMMAND

        # Air resolution happens here (within COMMAND phase)
        air_missions = tm._collect_air_missions(all_actions)
        if air_missions:
            resolved = air_engine.resolve_air_missions(air_missions, gs, gs.air_assets)
            tm._extract_cas_modifiers(resolved)

        # Phase is still COMMAND — not advanced yet
        assert gs.phase == TurnPhase.COMMAND


class TestCollectAirMissions:
    """_collect_air_missions returns CAS for ATTACK actions."""

    def test_attack_action_generates_cas_mission(self):
        gs = _make_game_state_with_air()
        air_engine = AirEngine(rng_seed=42)
        tm = _make_turn_manager(gs, air_engine=air_engine)
        gs.advance_turn()

        attack_action = _make_action("blue1", ActionType.ATTACK, target_hex=HexCoord(q=3, r=0))
        missions = tm._collect_air_missions([attack_action])
        assert len(missions) >= 1
        assert all(m.mission_type == AirMissionType.CAS for m in missions)

    def test_empty_actions_returns_no_missions(self):
        gs = _make_game_state_with_air()
        air_engine = AirEngine(rng_seed=42)
        tm = _make_turn_manager(gs, air_engine=air_engine)
        gs.advance_turn()

        missions = tm._collect_air_missions([])
        assert missions == []

    def test_no_air_assets_returns_no_missions(self):
        gs = _make_game_state_with_air()
        gs.air_assets = {}  # remove all assets
        air_engine = AirEngine(rng_seed=42)
        tm = _make_turn_manager(gs, air_engine=air_engine)
        gs.advance_turn()

        attack_action = _make_action("blue1", ActionType.ATTACK, target_hex=HexCoord(q=3, r=0))
        missions = tm._collect_air_missions([attack_action])
        assert missions == []

    def test_move_action_does_not_generate_cas(self):
        gs = _make_game_state_with_air()
        air_engine = AirEngine(rng_seed=42)
        tm = _make_turn_manager(gs, air_engine=air_engine)
        gs.advance_turn()

        move_action = _make_action("blue1", ActionType.MOVE, target_hex=HexCoord(q=1, r=0))
        missions = tm._collect_air_missions([move_action])
        assert missions == []

    def test_sortie_pool_limits_missions(self):
        gs = _make_game_state_with_air()
        # Only 1 sortie available
        gs.sortie_pools[Side.BLUE.value] = _make_pool(Side.BLUE, total=1, remaining=1)
        air_engine = AirEngine(rng_seed=42)
        tm = _make_turn_manager(gs, air_engine=air_engine)
        gs.advance_turn()

        # Multiple attack actions
        actions = [
            _make_action("blue1", ActionType.ATTACK, target_hex=HexCoord(q=3, r=0)),
            _make_action("blue1", ActionType.ATTACK, target_hex=HexCoord(q=4, r=0)),
        ]
        missions = tm._collect_air_missions(actions)
        # Should be capped at 1 (remaining_sorties)
        assert len(missions) <= 1


class TestExtractCasModifiers:
    """_extract_cas_modifiers accumulates correctly."""

    def test_single_success_gives_015(self):
        gs = _make_game_state_with_air()
        air_engine = AirEngine(rng_seed=42)
        tm = _make_turn_manager(gs, air_engine=air_engine)
        gs.advance_turn()

        target = HexCoord(q=3, r=0)
        mission = AirMission(
            mission_id="m1", turn=1, side=Side.BLUE,
            mission_type=AirMissionType.CAS, asset_id="f16-1",
            target_hex=target, result="SUCCESS",
        )
        modifiers = tm._extract_cas_modifiers([mission])
        assert abs(modifiers.get(str(target), 0.0) - 0.15) < 1e-9

    def test_two_successes_accumulate_to_030(self):
        gs = _make_game_state_with_air()
        air_engine = AirEngine(rng_seed=42)
        tm = _make_turn_manager(gs, air_engine=air_engine)
        gs.advance_turn()

        target = HexCoord(q=3, r=0)
        missions = [
            AirMission(
                mission_id="m1", turn=1, side=Side.BLUE,
                mission_type=AirMissionType.CAS, asset_id="f16-1",
                target_hex=target, result="SUCCESS",
            ),
            AirMission(
                mission_id="m2", turn=1, side=Side.BLUE,
                mission_type=AirMissionType.CAS, asset_id="f16-1",
                target_hex=target, result="SUCCESS",
            ),
        ]
        modifiers = tm._extract_cas_modifiers(missions)
        assert abs(modifiers.get(str(target), 0.0) - 0.30) < 1e-9

    def test_accumulation_capped_at_050(self):
        gs = _make_game_state_with_air()
        air_engine = AirEngine(rng_seed=42)
        tm = _make_turn_manager(gs, air_engine=air_engine)
        gs.advance_turn()

        target = HexCoord(q=3, r=0)
        missions = [
            AirMission(
                mission_id=f"m{i}", turn=1, side=Side.BLUE,
                mission_type=AirMissionType.CAS, asset_id="f16-1",
                target_hex=target, result="SUCCESS",
            )
            for i in range(10)
        ]
        modifiers = tm._extract_cas_modifiers(missions)
        assert modifiers.get(str(target), 0.0) <= 0.5

    def test_intercepted_mission_not_counted(self):
        gs = _make_game_state_with_air()
        air_engine = AirEngine(rng_seed=42)
        tm = _make_turn_manager(gs, air_engine=air_engine)
        gs.advance_turn()

        target = HexCoord(q=3, r=0)
        mission = AirMission(
            mission_id="m1", turn=1, side=Side.BLUE,
            mission_type=AirMissionType.CAS, asset_id="f16-1",
            target_hex=target, result="INTERCEPTED",
        )
        modifiers = tm._extract_cas_modifiers([mission])
        assert modifiers.get(str(target), 0.0) == 0.0

    def test_empty_missions_returns_empty_dict(self):
        gs = _make_game_state_with_air()
        air_engine = AirEngine(rng_seed=42)
        tm = _make_turn_manager(gs, air_engine=air_engine)
        gs.advance_turn()

        modifiers = tm._extract_cas_modifiers([])
        assert modifiers == {}


class TestSortiePoolReset:
    """Sortie pool resets each turn."""

    def test_sortie_pool_resets_on_advance_turn(self):
        gs = GameState()
        gs.sortie_pools[Side.BLUE.value] = SortiePool(
            side=Side.BLUE, total_sorties=5, remaining_sorties=2
        )
        gs.advance_turn()
        pool = gs.sortie_pools[Side.BLUE.value]
        assert pool.remaining_sorties == pool.total_sorties

    def test_sortie_pool_reset_preserves_total(self):
        gs = GameState()
        gs.sortie_pools[Side.BLUE.value] = SortiePool(
            side=Side.BLUE, total_sorties=8, remaining_sorties=0
        )
        gs.advance_turn()
        pool = gs.sortie_pools[Side.BLUE.value]
        assert pool.total_sorties == 8
        assert pool.remaining_sorties == 8


class TestScenarioAirAssetLoading:
    """Air assets load from scenario data."""

    def test_air_assets_loaded_from_scenario(self):
        scenario = {
            "map": {"hexes": [{"q": 0, "r": 0, "terrain": "PLAIN"}]},
            "forces": {
                "BLUE": {
                    "name": "Blue Force",
                    "units": [],
                    "commanders": [],
                    "air_assets": {
                        "total_sorties_per_turn": 4,
                        "assets": [
                            {
                                "id": "f16-1",
                                "name": "F-16",
                                "asset_type": "F-16",
                                "missions_capable": ["CAS", "AIR_SUPERIORITY"],
                                "sortie_count": 2,
                                "attack_power": 10.0,
                                "defense_against_sam": 0.3,
                            }
                        ],
                    },
                },
                "RED": {
                    "name": "Red Force",
                    "units": [],
                    "commanders": [],
                },
            },
        }
        gs = GameState(scenario_data=scenario)
        assert "f16-1" in gs.air_assets
        assert gs.air_assets["f16-1"].side == Side.BLUE
        assert Side.BLUE.value in gs.sortie_pools
        assert gs.sortie_pools[Side.BLUE.value].total_sorties == 4
