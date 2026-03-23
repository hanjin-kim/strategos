from __future__ import annotations
from enum import Enum
from pydantic import BaseModel
from app.models.domain import HexCoord


class SupplyLevel(str, Enum):
    FULL = "FULL"           # Connected to HQ
    REDUCED = "REDUCED"     # Partial blockage or distance penalty
    CUT_OFF = "CUT_OFF"     # Supply line fully cut


class SupplyStatus(BaseModel, frozen=True):
    unit_id: str
    level: SupplyLevel
    turns_without_supply: int = 0
    supply_route_length: int = 0  # hex distance to HQ


class SupplyLine(BaseModel, frozen=True):
    source_id: str  # HQ unit id
    target_id: str  # supplied unit id
    path_hexes: list[HexCoord] = []
    is_interdicted: bool = False
    interdiction_hex: HexCoord | None = None
