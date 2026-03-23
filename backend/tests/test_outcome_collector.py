from __future__ import annotations
import json
import sqlite3
import pytest

from app.batch.outcome_collector import OutcomeCollector
from app.batch.batch_runner import RunResult, BatchResult
from app.batch.parameter_set import ParameterSet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collector(tmp_path) -> OutcomeCollector:
    return OutcomeCollector(db_path=str(tmp_path / "test.db"))


def _make_run(
    run_index: int = 0,
    parameter_set_name: str = "default",
    rng_seed: int = 42,
    status: str = "COMPLETED",
    winner: str = "BLUE",
    total_turns: int = 10,
    blue_units_remaining: int = 3,
    red_units_remaining: int = 1,
    blue_avg_strength: float = 0.8,
    red_avg_strength: float = 0.4,
    execution_time_ms: int = 100,
    reproducibility_level: str = "DETERMINISTIC",
    error_message: str = "",
) -> RunResult:
    return RunResult(
        run_index=run_index,
        parameter_set_name=parameter_set_name,
        rng_seed=rng_seed,
        status=status,
        winner=winner,
        total_turns=total_turns,
        blue_units_remaining=blue_units_remaining,
        red_units_remaining=red_units_remaining,
        blue_avg_strength=blue_avg_strength,
        red_avg_strength=red_avg_strength,
        execution_time_ms=execution_time_ms,
        reproducibility_level=reproducibility_level,
        error_message=error_message,
    )


def _make_batch(batch_id: str = "b1", runs: list[RunResult] | None = None) -> BatchResult:
    if runs is None:
        runs = [_make_run()]
    return BatchResult(
        batch_id=batch_id,
        scenario_name="test_scenario",
        total_runs=len(runs),
        completed_runs=sum(1 for r in runs if r.status == "COMPLETED"),
        failed_runs=sum(1 for r in runs if r.status == "FAILED"),
        status="COMPLETED",
        runs=runs,
        execution_time_ms=200,
    )


def _make_params(**kwargs) -> ParameterSet:
    defaults = {"name": "default", "rng_seed": 42, "max_turns": 72, "use_llm": False}
    defaults.update(kwargs)
    return ParameterSet(**defaults)


# ---------------------------------------------------------------------------
# Table creation tests
# ---------------------------------------------------------------------------

def test_tables_created_batches(tmp_path):
    oc = _collector(tmp_path)
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "batches" in tables


def test_tables_created_batch_runs(tmp_path):
    oc = _collector(tmp_path)
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "batch_runs" in tables


def test_tables_created_batch_metrics(tmp_path):
    oc = _collector(tmp_path)
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "batch_metrics" in tables


# ---------------------------------------------------------------------------
# WAL mode
# ---------------------------------------------------------------------------

def test_wal_mode_active(tmp_path):
    oc = _collector(tmp_path)
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal"


# ---------------------------------------------------------------------------
# save_batch + get_batch roundtrip
# ---------------------------------------------------------------------------

def test_save_batch_get_batch_roundtrip(tmp_path):
    oc = _collector(tmp_path)
    batch = _make_batch("b1")
    oc.save_batch(batch)
    result = oc.get_batch("b1")
    assert result is not None
    assert result["batch_id"] == "b1"
    assert result["scenario_name"] == "test_scenario"
    assert result["total_runs"] == 1
    assert result["status"] == "COMPLETED"
    assert result["execution_time_ms"] == 200


def test_save_batch_completed_runs_count(tmp_path):
    oc = _collector(tmp_path)
    runs = [_make_run(run_index=i, winner="BLUE") for i in range(3)]
    batch = _make_batch("b2", runs=runs)
    oc.save_batch(batch)
    result = oc.get_batch("b2")
    assert result["completed_runs"] == 3
    assert result["failed_runs"] == 0


def test_save_batch_with_failed_run(tmp_path):
    oc = _collector(tmp_path)
    runs = [
        _make_run(run_index=0, winner="BLUE"),
        _make_run(run_index=1, status="FAILED", winner="", error_message="crash"),
    ]
    batch = BatchResult(
        batch_id="b3",
        scenario_name="test_scenario",
        total_runs=2,
        completed_runs=1,
        failed_runs=1,
        status="PARTIAL",
        runs=runs,
        execution_time_ms=300,
    )
    oc.save_batch(batch)
    result = oc.get_batch("b3")
    assert result["failed_runs"] == 1
    assert result["status"] == "PARTIAL"


# ---------------------------------------------------------------------------
# get_batch_runs order
# ---------------------------------------------------------------------------

def test_get_batch_runs_returns_correct_order(tmp_path):
    oc = _collector(tmp_path)
    runs = [_make_run(run_index=i, winner="BLUE") for i in range(5)]
    # shuffle to ensure order is enforced by DB
    import random
    shuffled = runs[:]
    random.shuffle(shuffled)
    batch = _make_batch("b4", runs=shuffled)
    oc.save_batch(batch)
    result = oc.get_batch_runs("b4")
    indices = [r["run_index"] for r in result]
    assert indices == sorted(indices)


def test_get_batch_runs_correct_count(tmp_path):
    oc = _collector(tmp_path)
    runs = [_make_run(run_index=i) for i in range(4)]
    batch = _make_batch("b5", runs=runs)
    oc.save_batch(batch)
    result = oc.get_batch_runs("b5")
    assert len(result) == 4


def test_get_batch_runs_fields(tmp_path):
    oc = _collector(tmp_path)
    run = _make_run(run_index=0, winner="RED", total_turns=15, blue_units_remaining=0, red_units_remaining=2)
    batch = _make_batch("b6", runs=[run])
    oc.save_batch(batch)
    rows = oc.get_batch_runs("b6")
    assert len(rows) == 1
    r = rows[0]
    assert r["winner"] == "RED"
    assert r["total_turns"] == 15
    assert r["blue_units_remaining"] == 0
    assert r["red_units_remaining"] == 2


# ---------------------------------------------------------------------------
# save_turn_metrics + get_run_metrics
# ---------------------------------------------------------------------------

def test_save_and_get_turn_metrics(tmp_path):
    oc = _collector(tmp_path)
    oc.save_turn_metrics("b7", 0, 1, {"blue_strength": 0.9, "red_strength": 0.7})
    result = oc.get_run_metrics("b7", 0)
    assert len(result) == 2
    names = {r["metric_name"] for r in result}
    assert "blue_strength" in names
    assert "red_strength" in names


def test_turn_metrics_ordered_by_turn_then_name(tmp_path):
    oc = _collector(tmp_path)
    oc.save_turn_metrics("b8", 0, 2, {"z_metric": 1.0, "a_metric": 2.0})
    oc.save_turn_metrics("b8", 0, 1, {"m_metric": 3.0})
    result = oc.get_run_metrics("b8", 0)
    turns = [r["turn"] for r in result]
    assert turns == sorted(turns)
    # turn 1 entry should come first
    assert result[0]["turn"] == 1


def test_turn_metrics_isolated_by_run_index(tmp_path):
    oc = _collector(tmp_path)
    oc.save_turn_metrics("b9", 0, 1, {"x": 1.0})
    oc.save_turn_metrics("b9", 1, 1, {"x": 2.0})
    run0 = oc.get_run_metrics("b9", 0)
    run1 = oc.get_run_metrics("b9", 1)
    assert len(run0) == 1
    assert len(run1) == 1
    assert run0[0]["metric_value"] == pytest.approx(1.0)
    assert run1[0]["metric_value"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# save_run_with_params
# ---------------------------------------------------------------------------

def test_save_run_with_params_stores_json(tmp_path):
    oc = _collector(tmp_path)
    # ensure batch exists
    batch = _make_batch("b10", runs=[])
    oc.save_batch(batch)
    run = _make_run(run_index=0)
    params = _make_params(name="variant_a", rng_seed=99)
    oc.save_run_with_params("b10", run, params)
    rows = oc.get_batch_runs("b10")
    assert len(rows) == 1
    stored_json = rows[0]["parameter_set_json"]
    assert stored_json is not None
    parsed = json.loads(stored_json)
    assert parsed["name"] == "variant_a"
    assert parsed["rng_seed"] == 99


def test_save_run_with_params_fields(tmp_path):
    oc = _collector(tmp_path)
    batch = _make_batch("b11", runs=[])
    oc.save_batch(batch)
    run = _make_run(run_index=0, winner="DRAW", total_turns=72)
    params = _make_params(name="draw_run")
    oc.save_run_with_params("b11", run, params)
    rows = oc.get_batch_runs("b11")
    r = rows[0]
    assert r["winner"] == "DRAW"
    assert r["total_turns"] == 72
    assert r["parameter_set_name"] == "default"


# ---------------------------------------------------------------------------
# get_all_batches
# ---------------------------------------------------------------------------

def test_get_all_batches_returns_all(tmp_path):
    oc = _collector(tmp_path)
    oc.save_batch(_make_batch("batch_a"))
    oc.save_batch(_make_batch("batch_b"))
    oc.save_batch(_make_batch("batch_c"))
    all_batches = oc.get_all_batches()
    ids = {b["batch_id"] for b in all_batches}
    assert {"batch_a", "batch_b", "batch_c"} == ids


def test_get_all_batches_empty(tmp_path):
    oc = _collector(tmp_path)
    assert oc.get_all_batches() == []


# ---------------------------------------------------------------------------
# get_batch for non-existent batch
# ---------------------------------------------------------------------------

def test_get_batch_nonexistent_returns_none(tmp_path):
    oc = _collector(tmp_path)
    assert oc.get_batch("does_not_exist") is None


# ---------------------------------------------------------------------------
# get_win_rates
# ---------------------------------------------------------------------------

def test_win_rates_all_blue(tmp_path):
    oc = _collector(tmp_path)
    runs = [_make_run(run_index=i, winner="BLUE") for i in range(4)]
    batch = _make_batch("wr1", runs=runs)
    oc.save_batch(batch)
    rates = oc.get_win_rates("wr1")
    assert rates["blue_wins"] == 4
    assert rates["red_wins"] == 0
    assert rates["draws"] == 0
    assert rates["total"] == 4
    assert rates["blue_win_rate"] == pytest.approx(1.0)
    assert rates["red_win_rate"] == pytest.approx(0.0)


def test_win_rates_mixed(tmp_path):
    oc = _collector(tmp_path)
    runs = [
        _make_run(run_index=0, winner="BLUE"),
        _make_run(run_index=1, winner="BLUE"),
        _make_run(run_index=2, winner="RED"),
        _make_run(run_index=3, winner="DRAW"),
    ]
    batch = _make_batch("wr2", runs=runs)
    oc.save_batch(batch)
    rates = oc.get_win_rates("wr2")
    assert rates["blue_wins"] == 2
    assert rates["red_wins"] == 1
    assert rates["draws"] == 1
    assert rates["total"] == 4
    assert rates["blue_win_rate"] == pytest.approx(0.5)
    assert rates["red_win_rate"] == pytest.approx(0.25)
    assert rates["draw_rate"] == pytest.approx(0.25)


def test_win_rates_no_completed_runs(tmp_path):
    oc = _collector(tmp_path)
    runs = [_make_run(run_index=0, status="FAILED", winner="")]
    batch = BatchResult(
        batch_id="wr3",
        scenario_name="test",
        total_runs=1,
        completed_runs=0,
        failed_runs=1,
        status="PARTIAL",
        runs=runs,
        execution_time_ms=50,
    )
    oc.save_batch(batch)
    rates = oc.get_win_rates("wr3")
    assert rates["total"] == 0
    assert rates["blue_wins"] == 0
    assert rates["red_wins"] == 0
    assert rates["draws"] == 0


def test_win_rates_nonexistent_batch(tmp_path):
    oc = _collector(tmp_path)
    rates = oc.get_win_rates("no_such_batch")
    assert rates["total"] == 0


# ---------------------------------------------------------------------------
# Empty batch handling
# ---------------------------------------------------------------------------

def test_save_batch_no_runs(tmp_path):
    oc = _collector(tmp_path)
    batch = BatchResult(
        batch_id="empty1",
        scenario_name="empty",
        total_runs=0,
        completed_runs=0,
        failed_runs=0,
        status="COMPLETED",
        runs=[],
        execution_time_ms=0,
    )
    oc.save_batch(batch)
    result = oc.get_batch("empty1")
    assert result is not None
    assert result["total_runs"] == 0
    runs = oc.get_batch_runs("empty1")
    assert runs == []


# ---------------------------------------------------------------------------
# Multiple batches isolation
# ---------------------------------------------------------------------------

def test_multiple_batches_isolation(tmp_path):
    oc = _collector(tmp_path)
    runs_a = [_make_run(run_index=i, winner="BLUE") for i in range(3)]
    runs_b = [_make_run(run_index=i, winner="RED") for i in range(2)]
    oc.save_batch(_make_batch("iso_a", runs=runs_a))
    oc.save_batch(_make_batch("iso_b", runs=runs_b))
    result_a = oc.get_batch_runs("iso_a")
    result_b = oc.get_batch_runs("iso_b")
    assert len(result_a) == 3
    assert len(result_b) == 2
    assert all(r["winner"] == "BLUE" for r in result_a)
    assert all(r["winner"] == "RED" for r in result_b)


def test_multiple_batches_win_rates_isolated(tmp_path):
    oc = _collector(tmp_path)
    runs_a = [_make_run(run_index=i, winner="BLUE") for i in range(2)]
    runs_b = [_make_run(run_index=i, winner="RED") for i in range(2)]
    oc.save_batch(_make_batch("iso_c", runs=runs_a))
    oc.save_batch(_make_batch("iso_d", runs=runs_b))
    rates_a = oc.get_win_rates("iso_c")
    rates_d = oc.get_win_rates("iso_d")
    assert rates_a["blue_win_rate"] == pytest.approx(1.0)
    assert rates_d["red_win_rate"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# save_batch idempotency (INSERT OR REPLACE)
# ---------------------------------------------------------------------------

def test_save_batch_replace_updates_existing(tmp_path):
    oc = _collector(tmp_path)
    batch = _make_batch("idem1")
    oc.save_batch(batch)
    # Save again with updated status
    updated = BatchResult(
        batch_id="idem1",
        scenario_name="test_scenario",
        total_runs=1,
        completed_runs=1,
        failed_runs=0,
        status="COMPLETED",
        runs=batch.runs,
        execution_time_ms=999,
    )
    oc.save_batch(updated)
    result = oc.get_batch("idem1")
    assert result["execution_time_ms"] == 999
    assert len(oc.get_all_batches()) == 1
