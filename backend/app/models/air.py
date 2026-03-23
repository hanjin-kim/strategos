from __future__ import annotations
from enum import Enum
from pydantic import BaseModel
from app.models.domain import HexCoord, Side


class AirMissionType(str, Enum):
    CAS = "CAS"                     # Close Air Support
    INTERDICTION = "INTERDICTION"   # Supply line disruption
    AIR_SUPERIORITY = "AIR_SUPERIORITY"  # Air dominance
    RECON = "RECON"                 # Aerial reconnaissance


class AirAsset(BaseModel, frozen=True):
    id: str
    name: str
    side: Side
    asset_type: str  # "F-16", "Su-25", etc.
    missions_capable: list[AirMissionType]
    sortie_count: int       # sorties per turn
    attack_power: float
    defense_against_sam: float  # 0.0~1.0 evasion capability


class AirMission(BaseModel, frozen=True):
    mission_id: str
    turn: int
    side: Side
    mission_type: AirMissionType
    asset_id: str
    target_hex: HexCoord | None = None
    target_unit_id: str | None = None
    result: str = ""  # SUCCESS, INTERCEPTED, ABORTED


class SortiePool(BaseModel, frozen=True):
    side: Side
    total_sorties: int
    remaining_sorties: int
    air_superiority: float = 0.5  # 0.0~1.0
