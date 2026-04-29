from __future__ import annotations
import logging
from app.models.actions import MilitaryAction, OrderDirective
from app.models.game_config import CommandMode

logger = logging.getLogger(__name__)


class HumanCommander:
    """Stores player-submitted commands and returns them during the command phase.

    Replaces AI agents for the player's side. Commands are submitted
    via REST API and consumed on the next turn step.
    """

    def __init__(self, side: str, command_mode: CommandMode = CommandMode.HYBRID):
        self.side = side
        self.command_mode = command_mode
        self._pending_orders: list[OrderDirective] = []
        self._pending_actions: list[MilitaryAction] = []

    def submit_orders(self, orders: list[OrderDirective]) -> None:
        self._pending_orders = list(orders)

    def submit_actions(self, actions: list[MilitaryAction]) -> None:
        self._pending_actions = list(actions)

    def get_pending_orders(self) -> list[OrderDirective]:
        return list(self._pending_orders)

    def get_pending_actions(self) -> list[MilitaryAction]:
        return list(self._pending_actions)

    def clear_pending(self) -> None:
        self._pending_orders = []
        self._pending_actions = []

    def has_pending(self) -> bool:
        return bool(self._pending_orders or self._pending_actions)

    def validate_commands(
        self,
        orders: list[OrderDirective] | None = None,
        actions: list[MilitaryAction] | None = None,
    ) -> list[str]:
        """Validate commands against command mode. Returns list of error strings."""
        errors: list[str] = []
        orders = orders or []
        actions = actions or []

        if self.command_mode == CommandMode.STRATEGIC and actions:
            errors.append(
                "Tactical actions (MilitaryAction) not allowed in STRATEGIC mode"
            )
        if self.command_mode == CommandMode.TACTICAL and orders:
            errors.append(
                "Strategic orders (OrderDirective) not allowed in TACTICAL mode"
            )
        if not orders and not actions:
            errors.append("No commands submitted")

        return errors
