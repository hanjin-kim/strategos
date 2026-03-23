from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, field_validator


class HexCoord(BaseModel, frozen=True):
    q: int  # axial coordinate
    r: int

    @property
    def s(self) -> int:
        return -self.q - self.r

    def __hash__(self) -> int:
        return hash((self.q, self.r))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HexCoord):
            return NotImplemented
        return self.q == other.q and self.r == other.r


class Side(str, Enum):
    BLUE = "BLUE"
    RED = "RED"


class UnitType(str, Enum):
    INFANTRY = "INFANTRY"
    MECHANIZED = "MECHANIZED"
    ARMOR = "ARMOR"
    ARTILLERY = "ARTILLERY"
    AIR_DEFENSE = "AIR_DEFENSE"
    ENGINEER = "ENGINEER"
    HQ = "HQ"
    RECON = "RECON"
    SAM = "SAM"
    AAA = "AAA"


class UnitSize(str, Enum):
    BATTALION = "BATTALION"
    BRIGADE = "BRIGADE"
    DIVISION = "DIVISION"


class UnitStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    ROUTED = "ROUTED"
    DESTROYED = "DESTROYED"


class TerrainType(str, Enum):
    PLAIN = "PLAIN"
    MOUNTAIN = "MOUNTAIN"
    URBAN = "URBAN"
    FOREST = "FOREST"
    RIVER = "RIVER"
    WATER = "WATER"
    BRIDGE = "BRIDGE"


class Unit(BaseModel, frozen=True):
    id: str
    name: str
    side: Side
    unit_type: UnitType
    size: UnitSize
    position: HexCoord
    strength: float          # 0.0~1.0
    morale: float            # 0.0~1.0
    movement_points: int
    max_movement_points: int
    attack_power: float
    defense_power: float
    effective_range: int     # hex units
    ammo: float              # 0.0~1.0
    fuel: float              # 0.0~1.0
    status: UnitStatus
    parent_unit_id: str | None = None
    subordinate_ids: list[str] = []

    @field_validator("strength", "morale", "ammo", "fuel")
    @classmethod
    def validate_ratio(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Value must be between 0.0 and 1.0, got {v}")
        return v


class Commander(BaseModel, frozen=True):
    id: str
    name: str
    side: Side
    rank: str                        # "Theater", "Division", "Battalion"
    unit_id: str
    personality_traits: dict[str, float] = {}


class TerrainHex(BaseModel, frozen=True):
    coord: HexCoord
    terrain_type: TerrainType
    elevation: int = 0
    movement_cost: int = 1
    defense_modifier: float = 1.0
    name: str | None = None


class Force(BaseModel, frozen=True):
    side: Side
    name: str
    commander_ids: list[str] = []
    unit_ids: list[str] = []
    victory_points: int = 0
