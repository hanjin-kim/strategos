from __future__ import annotations
from enum import Enum
from pydantic import BaseModel
from app.models.domain import HexCoord


class ActionType(str, Enum):
    MOVE = "MOVE"
    ATTACK = "ATTACK"
    DEFEND = "DEFEND"
    RETREAT = "RETREAT"
    HOLD = "HOLD"
    DO_NOTHING = "DO_NOTHING"


class MilitaryAction(BaseModel, frozen=True):
    action_id: str
    turn: int
    commander_id: str
    unit_id: str
    action_type: ActionType
    target_hex: HexCoord | None = None
    target_unit_id: str | None = None
    priority: int = 3
    reasoning: str = ""


class MissionType(str, Enum):
    ATTACK = "ATTACK"
    DEFEND = "DEFEND"
    DELAY = "DELAY"
    RESERVE = "RESERVE"
    WITHDRAW = "WITHDRAW"


class OrderDirective(BaseModel, frozen=True):
    """Mission-type order from superior commander to subordinate unit."""
    order_id: str
    turn: int
    issuer_id: str
    target_unit_id: str
    mission: MissionType
    objective_hex: HexCoord | None = None
    priority: int = 3
    constraints: list[str] = []
    reasoning: str = ""

    def to_battalion_context(self) -> dict:
        """Convert to context dict for battalion commander's LLM prompt."""
        return {
            "mission": self.mission.value,
            "objective_hex": {"q": self.objective_hex.q, "r": self.objective_hex.r} if self.objective_hex else None,
            "priority": self.priority,
            "constraints": self.constraints,
            "reasoning": self.reasoning,
        }
