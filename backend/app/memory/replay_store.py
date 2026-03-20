from __future__ import annotations
import json
import sqlite3
import uuid
from pathlib import Path


class ReplayStore:
    """SQLite-based turn state snapshots for replay and save/load."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS simulations (
                    id TEXT PRIMARY KEY,
                    scenario_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    config_json TEXT
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    simulation_id TEXT NOT NULL,
                    turn INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (simulation_id) REFERENCES simulations(id),
                    UNIQUE(simulation_id, turn)
                );
                CREATE TABLE IF NOT EXISTS action_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    simulation_id TEXT NOT NULL,
                    turn INTEGER NOT NULL,
                    commander_id TEXT,
                    action_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (simulation_id) REFERENCES simulations(id)
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def create_simulation(self, scenario_name: str, config: dict | None = None) -> str:
        sim_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO simulations (id, scenario_name, config_json) VALUES (?, ?, ?)",
                (sim_id, scenario_name, json.dumps(config or {})),
            )
        return sim_id

    def save_snapshot(self, simulation_id: str, turn: int, game_state) -> None:
        """Save game state snapshot at turn boundary."""
        snapshot = game_state.to_snapshot()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO snapshots (simulation_id, turn, state_json) VALUES (?, ?, ?)",
                (simulation_id, turn, json.dumps(snapshot)),
            )

    def load_snapshot(self, simulation_id: str, turn: int):
        """Load game state from snapshot. Returns dict or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM snapshots WHERE simulation_id = ? AND turn = ?",
                (simulation_id, turn),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def save_actions(self, simulation_id: str, turn: int, actions: list[dict]) -> None:
        with self._connect() as conn:
            for action in actions:
                conn.execute(
                    "INSERT INTO action_log (simulation_id, turn, commander_id, action_json) VALUES (?, ?, ?, ?)",
                    (simulation_id, turn, action.get("commander_id"), json.dumps(action)),
                )

    def get_turn_actions(self, simulation_id: str, turn: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT action_json FROM action_log WHERE simulation_id = ? AND turn = ? ORDER BY id",
                (simulation_id, turn),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def list_turns(self, simulation_id: str) -> list[int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT turn FROM snapshots WHERE simulation_id = ? ORDER BY turn",
                (simulation_id,),
            ).fetchall()
        return [row[0] for row in rows]

    def list_simulations(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, scenario_name, created_at FROM simulations ORDER BY created_at DESC"
            ).fetchall()
        return [{"id": r[0], "scenario_name": r[1], "created_at": r[2]} for r in rows]
