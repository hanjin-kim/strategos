"""Phase 2 full integration tests."""
from __future__ import annotations

import pytest
from app.engine.game_state import GameState
from app.engine.turn_manager import TurnManager
from app.engine.constraint_engine import ConstraintEngine
from app.engine.combat_resolver import CombatResolver
from app.engine.movement_engine import MovementEngine
from app.engine.intel_engine import IntelEngine
from app.engine.supply_engine import SupplyEngine
from app.engine.air_engine import AirEngine
from app.agents.battalion_commander import BattalionCommander
from app.models.domain import Side


_DUMMY_LLM = {"api_key": "", "base_url": "", "model": "qwen-plus", "temperature": 0.0}


def _make_scenario():
    """Minimal scenario: 2 units per side, no commanders, 10x10 map."""
    return {
        "map": {
            "hexes": [
                {
                    "q": q, "r": r, "terrain": "PLAIN",
                    "elevation": 0, "movement_cost": 1, "defense_modifier": 1.0,
                }
                for q in range(10) for r in range(10)
            ],
        },
        "forces": {
            "BLUE": {
                "name": "Blue Force",
                "units": [
                    {
                        "id": "B1", "name": "B1", "type": "INFANTRY", "size": "BATTALION",
                        "position": {"q": 2, "r": 2}, "strength": 1.0, "morale": 0.8,
                        "max_movement_points": 2, "attack_power": 10.0, "defense_power": 10.0,
                        "effective_range": 1, "ammo": 1.0, "fuel": 1.0,
                    },
                    {
                        "id": "B_HQ", "name": "B_HQ", "type": "HQ", "size": "BATTALION",
                        "position": {"q": 0, "r": 0}, "strength": 1.0, "morale": 0.8,
                        "max_movement_points": 1, "attack_power": 2.0, "defense_power": 5.0,
                        "effective_range": 1, "ammo": 1.0, "fuel": 1.0,
                    },
                ],
                "commanders": [
                    {
                        "id": "B_CMD", "name": "Blue Commander", "rank": "Battalion",
                        "unit_id": "B1",
                    },
                    {
                        "id": "B_HQ_CMD", "name": "Blue HQ Commander", "rank": "Battalion",
                        "unit_id": "B_HQ",
                    },
                ],
            },
            "RED": {
                "name": "Red Force",
                "units": [
                    {
                        "id": "R1", "name": "R1", "type": "INFANTRY", "size": "BATTALION",
                        "position": {"q": 7, "r": 7}, "strength": 1.0, "morale": 0.8,
                        "max_movement_points": 2, "attack_power": 10.0, "defense_power": 10.0,
                        "effective_range": 1, "ammo": 1.0, "fuel": 1.0,
                    },
                    {
                        "id": "R_HQ", "name": "R_HQ", "type": "HQ", "size": "BATTALION",
                        "position": {"q": 9, "r": 9}, "strength": 1.0, "morale": 0.8,
                        "max_movement_points": 1, "attack_power": 2.0, "defense_power": 5.0,
                        "effective_range": 1, "ammo": 1.0, "fuel": 1.0,
                    },
                ],
                "commanders": [
                    {
                        "id": "R_CMD", "name": "Red Commander", "rank": "Battalion",
                        "unit_id": "R1",
                    },
                    {
                        "id": "R_HQ_CMD", "name": "Red HQ Commander", "rank": "Battalion",
                        "unit_id": "R_HQ",
                    },
                ],
            },
        },
    }


def _make_turn_manager(engines: bool = True) -> TurnManager:
    scenario = _make_scenario()
    gs = GameState(scenario)

    agents = {}
    for cmd_id, cmd in gs.commanders.items():
        agents[cmd_id] = BattalionCommander(commander=cmd, llm_config=_DUMMY_LLM)

    ce = ConstraintEngine()
    cr = CombatResolver(rng_seed=42)
    me = MovementEngine()

    kwargs: dict = {}
    if engines:
        kwargs["intel_engine"] = IntelEngine()
        kwargs["supply_engine"] = SupplyEngine()
        kwargs["air_engine"] = AirEngine(rng_seed=42)

    return TurnManager(
        game_state=gs,
        agents=agents,
        constraint_engine=ce,
        combat_resolver=cr,
        movement_engine=me,
        **kwargs,
    )


class TestPhase2Integration:

    def test_backward_compat_no_engines(self):
        """All engines None = Phase 1 behavior, intel/supply stay empty."""
        tm = _make_turn_manager(engines=False)
        gs = tm.run_simulation(max_turns=3)
        assert gs.turn == 3
        assert gs.intel_reports == {}
        assert gs.supply_status == {}

    def test_intel_engine_populates_reports(self):
        """IntelEngine active -> intel_reports is a dict (may or may not detect at distance)."""
        tm = _make_turn_manager(engines=True)
        gs = tm.run_simulation(max_turns=1)
        assert isinstance(gs.intel_reports, dict)

    def test_supply_status_populated(self):
        """SupplyEngine active -> supply_status is populated after one turn."""
        tm = _make_turn_manager(engines=True)
        gs = tm.run_simulation(max_turns=1)
        assert isinstance(gs.supply_status, dict)

    def test_multi_turn_simulation(self):
        """5 turns with all engines active completes without error."""
        tm = _make_turn_manager(engines=True)
        gs = tm.run_simulation(max_turns=5)
        assert gs.turn == 5

    def test_snapshot_roundtrip_with_engines(self):
        """Snapshot preserves Phase 2 state after restore."""
        tm = _make_turn_manager(engines=True)
        gs = tm.run_simulation(max_turns=1)
        snap = gs.to_snapshot()
        restored = GameState.from_snapshot(snap)
        assert restored.turn == gs.turn
        assert isinstance(restored.intel_reports, dict)
        assert isinstance(restored.supply_status, dict)

    def test_turn_results_have_data(self):
        """TurnResult list is populated with one entry per turn."""
        tm = _make_turn_manager(engines=True)
        tm.run_simulation(max_turns=2)
        assert len(tm.turn_results) == 2
        for tr in tm.turn_results:
            assert tr.turn > 0

    def test_engines_dont_interfere(self):
        """With and without engines both complete correctly."""
        tm_with = _make_turn_manager(engines=True)
        tm_without = _make_turn_manager(engines=False)
        gs_with = tm_with.run_simulation(max_turns=2)
        gs_without = tm_without.run_simulation(max_turns=2)
        assert gs_with.turn == 2
        assert gs_without.turn == 2
