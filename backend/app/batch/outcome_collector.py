from __future__ import annotations
import json
import sqlite3
import logging
from app.batch.batch_runner import RunResult, BatchResult
from app.batch.parameter_set import ParameterSet

logger = logging.getLogger(__name__)


class OutcomeCollector:
    """Collects and stores batch simulation outcomes in SQLite."""

    def __init__(self, db_path: str = "data/wargame.db"):
        self.db_path = db_path
        self._init_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        conn = self._connect()
        conn.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS batches (
                batch_id TEXT PRIMARY KEY,
                scenario_name TEXT NOT NULL,
                total_runs INTEGER NOT NULL,
                completed_runs INTEGER DEFAULT 0,
                failed_runs INTEGER DEFAULT 0,
                status TEXT DEFAULT 'PENDING',
                execution_time_ms INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS batch_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                run_index INTEGER NOT NULL,
                parameter_set_name TEXT,
                parameter_set_json TEXT,
                rng_seed INTEGER,
                status TEXT DEFAULT 'PENDING',
                error_message TEXT DEFAULT '',
                winner TEXT DEFAULT '',
                total_turns INTEGER DEFAULT 0,
                blue_units_remaining INTEGER DEFAULT 0,
                red_units_remaining INTEGER DEFAULT 0,
                blue_avg_strength REAL DEFAULT 0.0,
                red_avg_strength REAL DEFAULT 0.0,
                execution_time_ms INTEGER DEFAULT 0,
                reproducibility_level TEXT DEFAULT 'DETERMINISTIC',
                FOREIGN KEY (batch_id) REFERENCES batches(batch_id),
                UNIQUE(batch_id, run_index)
            );

            CREATE TABLE IF NOT EXISTS batch_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                run_index INTEGER NOT NULL,
                turn INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
            );

            CREATE INDEX IF NOT EXISTS idx_batch_runs_batch ON batch_runs(batch_id);
            CREATE INDEX IF NOT EXISTS idx_batch_metrics_batch ON batch_metrics(batch_id, run_index);
        """)
        conn.commit()
        conn.close()

    def save_batch(self, batch_result: BatchResult) -> None:
        """Save entire batch result (summary + individual runs)."""
        conn = self._connect()
        conn.execute(
            "INSERT OR REPLACE INTO batches (batch_id, scenario_name, total_runs, completed_runs, failed_runs, status, execution_time_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (batch_result.batch_id, batch_result.scenario_name, batch_result.total_runs,
             batch_result.completed_runs, batch_result.failed_runs, batch_result.status,
             batch_result.execution_time_ms),
        )
        for run in batch_result.runs:
            conn.execute(
                "INSERT OR REPLACE INTO batch_runs (batch_id, run_index, parameter_set_name, rng_seed, status, error_message, winner, total_turns, blue_units_remaining, red_units_remaining, blue_avg_strength, red_avg_strength, execution_time_ms, reproducibility_level) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (batch_result.batch_id, run.run_index, run.parameter_set_name, run.rng_seed,
                 run.status, run.error_message, run.winner, run.total_turns,
                 run.blue_units_remaining, run.red_units_remaining,
                 run.blue_avg_strength, run.red_avg_strength,
                 run.execution_time_ms, run.reproducibility_level),
            )
        conn.commit()
        conn.close()

    def save_run_with_params(self, batch_id: str, run: RunResult, params: ParameterSet) -> None:
        """Save a single run with its parameter set JSON."""
        conn = self._connect()
        conn.execute(
            "INSERT OR REPLACE INTO batch_runs (batch_id, run_index, parameter_set_name, parameter_set_json, rng_seed, status, error_message, winner, total_turns, blue_units_remaining, red_units_remaining, blue_avg_strength, red_avg_strength, execution_time_ms, reproducibility_level) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (batch_id, run.run_index, run.parameter_set_name, params.model_dump_json(),
             run.rng_seed, run.status, run.error_message, run.winner, run.total_turns,
             run.blue_units_remaining, run.red_units_remaining,
             run.blue_avg_strength, run.red_avg_strength,
             run.execution_time_ms, run.reproducibility_level),
        )
        conn.commit()
        conn.close()

    def save_turn_metrics(self, batch_id: str, run_index: int, turn: int, metrics: dict[str, float]) -> None:
        """Save per-turn metrics for a run."""
        conn = self._connect()
        for name, value in metrics.items():
            conn.execute(
                "INSERT INTO batch_metrics (batch_id, run_index, turn, metric_name, metric_value) VALUES (?, ?, ?, ?, ?)",
                (batch_id, run_index, turn, name, value),
            )
        conn.commit()
        conn.close()

    def get_batch(self, batch_id: str) -> dict | None:
        """Get batch summary."""
        conn = self._connect()
        row = conn.execute("SELECT * FROM batches WHERE batch_id = ?", (batch_id,)).fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    def get_batch_runs(self, batch_id: str) -> list[dict]:
        """Get all runs for a batch."""
        conn = self._connect()
        rows = conn.execute("SELECT * FROM batch_runs WHERE batch_id = ? ORDER BY run_index", (batch_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_run_metrics(self, batch_id: str, run_index: int) -> list[dict]:
        """Get all turn metrics for a specific run."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM batch_metrics WHERE batch_id = ? AND run_index = ? ORDER BY turn, metric_name",
            (batch_id, run_index),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_all_batches(self) -> list[dict]:
        """List all batches."""
        conn = self._connect()
        rows = conn.execute("SELECT * FROM batches ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_win_rates(self, batch_id: str) -> dict:
        """Calculate win rates for a batch."""
        runs = self.get_batch_runs(batch_id)
        completed = [r for r in runs if r["status"] == "COMPLETED"]
        total = len(completed)
        if total == 0:
            return {"blue_wins": 0, "red_wins": 0, "draws": 0, "total": 0}
        blue = sum(1 for r in completed if r["winner"] == "BLUE")
        red = sum(1 for r in completed if r["winner"] == "RED")
        draws = sum(1 for r in completed if r["winner"] == "DRAW")
        return {
            "blue_wins": blue,
            "red_wins": red,
            "draws": draws,
            "total": total,
            "blue_win_rate": round(blue / total, 3),
            "red_win_rate": round(red / total, 3),
            "draw_rate": round(draws / total, 3),
        }
