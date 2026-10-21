"""The reason a ticket stops (C23): what went wrong and the next action."""

from __future__ import annotations

# Why a ticket did not end delivered green (C19, ADR 0058): one of these goes to `metrics.json`.
SPEC = "spec"  # the ticket is unclear: the implementer changed nothing
GUARD = "guard"  # the push guard or the tree guard refused a change
BUDGET = "budget"  # a cost, token or time limit stopped an agent
RUNTIME = "runtime"  # the agent CLI failed: error, login, quota, invalid answer
CHECKS = "checks"  # blocking checks still red after the rounds
REVIEW = "review"  # the review still no-go after the rounds
MERGE = "merge"  # a conflict while updating the branch
CI = "ci"  # the pull request's CI still red after the CI rounds
INFRA = "infra"  # setup, slot, lock, tracker, git or an interrupt
CATEGORIES = (SPEC, GUARD, BUDGET, RUNTIME, CHECKS, REVIEW, MERGE, CI, INFRA)


class Stop(Exception):
    """The ticket stops here; `reason` and `next_action` go to the user and the journal, the
    `category` to `metrics.json`."""

    def __init__(
        self,
        reason: str,
        next_action: str,
        detail: str = "",
        status: str = "stopped",
        category: str = INFRA,
    ) -> None:
        super().__init__(reason)
        self.status = status
        self.category = category
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


def category_of(exc: BaseException) -> str:
    """The stop category of whatever ended a run; anything but a `Stop` is `infra`."""
    return exc.category if isinstance(exc, Stop) else INFRA
