from __future__ import annotations
from collections import deque


class RollingMemory:
    """Zep Cloud replacement: deque-based recent turn memory for agents."""

    def __init__(self, window: int = 10):
        self.recent: deque = deque(maxlen=window)
        self.summary: str = ""
        self._consolidation_interval: int = 20
        self._turn_count: int = 0

    def add(self, turn: int, context_summary: str, actions: list[dict]) -> None:
        """Add a turn record."""
        self.recent.append({
            "turn": turn,
            "context_summary": context_summary,
            "actions": actions,
        })
        self._turn_count += 1

    def get_recent(self, n: int = 5) -> list[dict]:
        """Get the last n turn records."""
        items = list(self.recent)
        return items[-n:] if n < len(items) else items

    def needs_consolidation(self) -> bool:
        """Check if memory should be consolidated (every 20 turns)."""
        return self._turn_count > 0 and self._turn_count % self._consolidation_interval == 0

    def consolidate(self, summarize_fn) -> None:
        """Consolidate old memories using a summarization function.
        summarize_fn(current_summary: str, old_entries: list[dict]) -> str
        """
        if len(self.recent) < 5:
            return
        old_entries = list(self.recent)[:5]
        self.summary = summarize_fn(self.summary, old_entries)

    def to_context_string(self) -> str:
        """Format for agent prompt injection."""
        parts = []
        if self.summary:
            parts.append(f"Historical Summary: {self.summary}")
        parts.append("Recent Turns:")
        for entry in self.recent:
            turn = entry["turn"]
            ctx = entry["context_summary"]
            actions_str = ", ".join(
                a.get("action_type", "?") for a in entry["actions"]
            ) if entry["actions"] else "none"
            parts.append(f"  Turn {turn}: {ctx} | Actions: {actions_str}")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "recent": list(self.recent),
            "summary": self.summary,
            "turn_count": self._turn_count,
            "window": self.recent.maxlen,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RollingMemory:
        mem = cls(window=data.get("window", 10))
        for entry in data.get("recent", []):
            mem.recent.append(entry)
        mem.summary = data.get("summary", "")
        mem._turn_count = data.get("turn_count", 0)
        return mem
