from __future__ import annotations
from pydantic import BaseModel


class TurnNarrative(BaseModel, frozen=True):
    turn: int
    summary: str = ""              # 1-2 paragraph overall summary
    combat_reports: list[str] = []  # Individual combat descriptions
    movement_summary: str = ""     # Movement activity summary
    strategic_analysis: str = ""   # Which side is winning and why
    key_events: list[str] = []     # Notable events (unit destroyed, supply cut, etc)
