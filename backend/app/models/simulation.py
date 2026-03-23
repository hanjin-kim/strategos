from __future__ import annotations
from enum import Enum
from pydantic import BaseModel
from app.models.domain import HexCoord


class TurnPhase(str, Enum):
    COMMAND = "COMMAND"
    EXECUTION = "EXECUTION"
    RESOLUTION = "RESOLUTION"


class CombatResult(str, Enum):
    ATTACKER_RETREAT = "AR"
    STALEMATE = "S"
    DEFENDER_RETREAT = "DR"
    DEFENDER_EXPELLED = "DE"
    DEFENDER_ROUT = "DRt"


class CombatOutcome(BaseModel, frozen=True):
    attacker_id: str
    defender_id: str
    hex_coord: HexCoord
    force_ratio: float
    die_roll: int
    result: CombatResult
    attacker_losses: float
    defender_losses: float
    defender_retreat_hexes: int
    narrative: str = ""


class MovementResult(BaseModel, frozen=True):
    unit_id: str
    path: list[HexCoord]
    final_position: HexCoord
    movement_spent: int
    remaining_mp: int
    triggered_combats: list[tuple[str, str]] = []  # (moving unit, enemy unit)


class TurnResult(BaseModel):
    turn: int
    phase_results: dict[TurnPhase, dict] = {}
    movements: list[MovementResult] = []
    combats: list[CombatOutcome] = []
    destroyed_units: list[str] = []
    state_snapshot_path: str | None = None
    narrative: str = ""
