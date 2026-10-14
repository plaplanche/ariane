"""The reason a ticket stops (C23): what went wrong and the next action."""

from __future__ import annotations


class Stop(Exception):
    """The ticket stops here; `reason` and `next_action` go to the user and the journal."""

    def __init__(
        self, reason: str, next_action: str, detail: str = "", status: str = "stopped"
    ) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason
        self.next_action = next_action
        self.detail = detail
