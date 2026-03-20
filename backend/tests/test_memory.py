from __future__ import annotations

import pytest

from app.memory.rolling_memory import RollingMemory
from app.memory.replay_store import ReplayStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockGameState:
    def __init__(self, data: dict):
        self._data = data

    def to_snapshot(self) -> dict:
        return self._data


def make_store(tmp_path) -> ReplayStore:
    return ReplayStore(str(tmp_path / "test.db"))


# ---------------------------------------------------------------------------
# RollingMemory tests
# ---------------------------------------------------------------------------

def test_add_and_get_recent():
    mem = RollingMemory(window=10)
    mem.add(1, "Turn 1 context", [{"action_type": "MOVE"}])
    mem.add(2, "Turn 2 context", [{"action_type": "ATTACK"}])
    recent = mem.get_recent()
    assert len(recent) == 2
    assert recent[0]["turn"] == 1
    assert recent[1]["turn"] == 2


def test_window_overflow_drops_oldest():
    mem = RollingMemory(window=3)
    for i in range(4):
        mem.add(i, f"ctx {i}", [])
    items = mem.get_recent()
    assert len(items) == 3
    assert items[0]["turn"] == 1  # turn 0 was dropped


def test_get_recent_n_returns_last_n():
    mem = RollingMemory(window=10)
    for i in range(5):
        mem.add(i, f"ctx {i}", [])
    recent = mem.get_recent(2)
    assert len(recent) == 2
    assert recent[0]["turn"] == 3
    assert recent[1]["turn"] == 4


def test_to_context_string_contains_recent_turns_header():
    mem = RollingMemory()
    mem.add(1, "some context", [{"action_type": "MOVE"}])
    result = mem.to_context_string()
    assert "Recent Turns:" in result
    assert "Turn 1" in result


def test_to_context_string_with_summary():
    mem = RollingMemory()
    mem.summary = "Blue advanced north."
    mem.add(1, "ctx", [])
    result = mem.to_context_string()
    assert "Historical Summary: Blue advanced north." in result
    assert "Recent Turns:" in result


def test_needs_consolidation_true_at_20():
    mem = RollingMemory()
    for i in range(20):
        mem.add(i, "ctx", [])
    assert mem.needs_consolidation() is True


def test_needs_consolidation_false_at_19():
    mem = RollingMemory()
    for i in range(19):
        mem.add(i, "ctx", [])
    assert mem.needs_consolidation() is False


def test_consolidate_calls_summarize_fn_and_updates_summary():
    mem = RollingMemory(window=10)
    for i in range(6):
        mem.add(i, f"ctx {i}", [])

    called_with = {}

    def summarize_fn(current_summary: str, old_entries: list[dict]) -> str:
        called_with["current"] = current_summary
        called_with["entries"] = old_entries
        return "consolidated summary"

    mem.consolidate(summarize_fn)
    assert mem.summary == "consolidated summary"
    assert called_with["current"] == ""
    assert len(called_with["entries"]) == 5


def test_to_dict_from_dict_roundtrip():
    mem = RollingMemory(window=5)
    mem.add(1, "ctx1", [{"action_type": "MOVE"}])
    mem.add(2, "ctx2", [])
    mem.summary = "summary text"

    data = mem.to_dict()
    restored = RollingMemory.from_dict(data)

    assert restored.summary == "summary text"
    assert restored._turn_count == 2
    assert restored.recent.maxlen == 5
    items = list(restored.recent)
    assert len(items) == 2
    assert items[0]["turn"] == 1
    assert items[1]["turn"] == 2


def test_empty_memory_get_recent_returns_empty():
    mem = RollingMemory()
    assert mem.get_recent() == []


# ---------------------------------------------------------------------------
# ReplayStore tests
# ---------------------------------------------------------------------------

def test_create_simulation_returns_uuid_string(tmp_path):
    store = make_store(tmp_path)
    sim_id = store.create_simulation("test_scenario")
    assert isinstance(sim_id, str)
    assert len(sim_id) == 36  # UUID4 format


def test_save_and_load_snapshot_roundtrip(tmp_path):
    store = make_store(tmp_path)
    sim_id = store.create_simulation("scenario_a")
    state = MockGameState({"turn": 3, "units": {"u1": {"strength": 0.8}}})
    store.save_snapshot(sim_id, 3, state)
    loaded = store.load_snapshot(sim_id, 3)
    assert loaded == {"turn": 3, "units": {"u1": {"strength": 0.8}}}


def test_load_snapshot_nonexistent_turn_returns_none(tmp_path):
    store = make_store(tmp_path)
    sim_id = store.create_simulation("scenario_b")
    result = store.load_snapshot(sim_id, 99)
    assert result is None


def test_save_and_get_turn_actions_roundtrip(tmp_path):
    store = make_store(tmp_path)
    sim_id = store.create_simulation("scenario_c")
    actions = [
        {"commander_id": "cmd1", "action_type": "MOVE", "target": "q1r0"},
        {"commander_id": "cmd2", "action_type": "ATTACK", "target": "q2r0"},
    ]
    store.save_actions(sim_id, 1, actions)
    result = store.get_turn_actions(sim_id, 1)
    assert len(result) == 2
    assert result[0]["action_type"] == "MOVE"
    assert result[1]["action_type"] == "ATTACK"


def test_list_turns_correct_order(tmp_path):
    store = make_store(tmp_path)
    sim_id = store.create_simulation("scenario_d")
    for turn in [3, 1, 2]:
        store.save_snapshot(sim_id, turn, MockGameState({"turn": turn}))
    turns = store.list_turns(sim_id)
    assert turns == [1, 2, 3]


def test_list_simulations_returns_created(tmp_path):
    store = make_store(tmp_path)
    store.create_simulation("alpha")
    store.create_simulation("beta")
    sims = store.list_simulations()
    names = [s["scenario_name"] for s in sims]
    assert "alpha" in names
    assert "beta" in names


def test_multiple_turns_stored_separately(tmp_path):
    store = make_store(tmp_path)
    sim_id = store.create_simulation("scenario_e")
    for turn in range(1, 4):
        store.save_snapshot(sim_id, turn, MockGameState({"turn": turn}))
    for turn in range(1, 4):
        loaded = store.load_snapshot(sim_id, turn)
        assert loaded["turn"] == turn


def test_replace_on_same_turn_updates_snapshot(tmp_path):
    store = make_store(tmp_path)
    sim_id = store.create_simulation("scenario_f")
    store.save_snapshot(sim_id, 5, MockGameState({"turn": 5, "version": "first"}))
    store.save_snapshot(sim_id, 5, MockGameState({"turn": 5, "version": "second"}))
    loaded = store.load_snapshot(sim_id, 5)
    assert loaded["version"] == "second"
