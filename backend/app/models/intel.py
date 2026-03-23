from __future__ import annotations
from enum import Enum
from pydantic import BaseModel

from app.models.domain import HexCoord


class IntelLevel(str, Enum):
    CONFIRMED = "CONFIRMED"   # Seen this turn — accurate info
    ESTIMATED = "ESTIMATED"   # 1-2 turns old — position/strength may be stale
    UNKNOWN = "UNKNOWN"       # 3+ turns since last seen


# Base visibility radius by unit type
VISIBILITY_TABLE: dict[str, int] = {
    "INFANTRY": 2,
    "MECHANIZED": 2,
    "ARMOR": 2,
    "ARTILLERY": 1,
    "AIR_DEFENSE": 2,
    "ENGINEER": 1,
    "HQ": 3,
    "RECON": 4,
}

# Terrain modifiers to visibility radius
TERRAIN_VISIBILITY_MODIFIERS: dict[str, int] = {
    "MOUNTAIN": 1,   # High ground bonus (observer on mountain)
    "FOREST": -1,    # Reduced visibility into forests
}

# Elevation threshold for bonus visibility
ELEVATION_BONUS_THRESHOLD = 300


class IntelReport(BaseModel, frozen=True):
    unit_id: str
    last_seen_turn: int
    last_known_position: HexCoord
    confidence: IntelLevel
    reported_strength: float
    reported_type: str


class VisibilityProfile(BaseModel, frozen=True):
    base_radius: int
    elevation_bonus: bool = False
