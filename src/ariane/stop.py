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


def describe(exc: BaseException) -> tuple[str, str]:
    """The reason and the next action for whatever ended a run: a stop, Ctrl-C or an error."""
    if isinstance(exc, KeyboardInterrupt):
        return "interrupted by the user", "check the working tree, then start the ticket again"
    if isinstance(exc, Stop):
        return exc.reason, exc.next_action
    first = str(exc).splitlines()[0].rstrip(":") if str(exc) else type(exc).__name__
    return first, "read the error above and retry"
