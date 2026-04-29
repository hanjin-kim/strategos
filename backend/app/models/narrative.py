from __future__ import annotations
from pydantic import BaseModel


class TurnNarrative(BaseModel, frozen=True):
    turn: int
    summary: str = ""
    combat_reports: list[str] = []
    movement_summary: str = ""
    strategic_analysis: str = ""
    key_events: list[str] = []
    enemy_dialogue: list[dict] = []
    staff_briefing: str = ""
    event_reactions: list[str] = []
