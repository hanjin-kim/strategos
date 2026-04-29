from __future__ import annotations
from enum import Enum
from pydantic import BaseModel


class CommandMode(str, Enum):
    STRATEGIC = "STRATEGIC"
    TACTICAL = "TACTICAL"
    HYBRID = "HYBRID"


class FogMode(str, Enum):
    FULL = "FULL"
    SOFT = "SOFT"
    OMNISCIENT = "OMNISCIENT"


class AIDifficulty(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class GameConfig(BaseModel, frozen=True):
    player_side: str | None = None
    command_mode: CommandMode = CommandMode.HYBRID
    fog_mode: FogMode = FogMode.SOFT
    ai_difficulty: AIDifficulty = AIDifficulty.MEDIUM
