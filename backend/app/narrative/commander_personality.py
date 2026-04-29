from __future__ import annotations
from pydantic import BaseModel


class CommanderPersonality(BaseModel, frozen=True):
    name: str
    rank: str
    side: str
    traits: list[str] = []
    speech_style: str = "formal military"
    catchphrases: list[str] = []
    background: str = ""


KOREAN_PENINSULA_COMMANDERS: dict[str, CommanderPersonality] = {
    "BLUE": CommanderPersonality(
        name="Gen. Park Sung-jin",
        rank="Theater Commander",
        side="BLUE",
        traits=["methodical", "cautious", "experienced"],
        speech_style="calm, measured, analytical",
        catchphrases=[
            "Patience wins battles, haste loses wars.",
            "Secure the flanks before pressing forward.",
            "Every casualty is a failure of planning.",
        ],
        background="30-year veteran, served in multiple UN peacekeeping operations. Known for meticulous planning.",
    ),
    "RED": CommanderPersonality(
        name="Gen. Kim Tae-hyun",
        rank="Theater Commander",
        side="RED",
        traits=["aggressive", "bold", "charismatic"],
        speech_style="intense, direct, defiant",
        catchphrases=[
            "Strike fast, strike hard. Hesitation is defeat.",
            "They underestimate our resolve.",
            "Victory belongs to the bold.",
        ],
        background="Rose through the ranks on the Eastern front. Believes in overwhelming force and rapid maneuver.",
    ),
}


def get_commander_personality(side: str, scenario: str = "korean_peninsula") -> CommanderPersonality:
    personality = KOREAN_PENINSULA_COMMANDERS.get(side)
    if personality:
        return personality
    return CommanderPersonality(
        name=f"Commander ({side})",
        rank="Theater Commander",
        side=side,
        speech_style="formal military",
    )
