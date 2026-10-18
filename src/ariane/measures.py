"""The success measure of `ariane report`: human time, gates bypassed, shadow results (C19,
ADR 0038)."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ariane.tracker import Tracker, TrackerError

SHADOW_WINDOW = 10
SHADOW_ACCEPTED = 8
NOT_AVAILABLE = "not available"
_NOT_STOPS = {"delivered", "needs a human", "running"}


def moment(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def clock(seconds: float) -> str:
    whole = round(seconds)
    return f"{whole // 3600}h{whole % 3600 // 60:02d}m"


@dataclass(frozen=True)
class Human:
    """Human time of one delivered ticket: waiting on its pull request, and stop to restart."""

    waiting_s: float | None  # None: the tracker could not tell
    restart_s: float
    merged: bool = False

    def text(self) -> str:
        wait = NOT_AVAILABLE if self.waiting_s is None else clock(self.waiting_s)
        return f"human time: waiting {wait}, restarts {clock(self.restart_s)}"


def restart_seconds(data: dict[str, Any], restarts: list[dict[str, Any]]) -> float:
    """Each stop (from `steps`) to the next `verify` record of the same ticket or branch, and
    the previous run's last step to this run's start when it started over (ADR 0047)."""
    total = 0.0
    previous = data.get("restarted_from")
    stopped_at = previous.get("stopped_at") if isinstance(previous, dict) else None
    if isinstance(stopped_at, str):
        with contextlib.suppress(ValueError):
            total += max(0.0, (moment(data["started"]) - moment(stopped_at)).total_seconds())
    for step in data.get("steps") or []:
        name = step.get("name", "")
        if not name.startswith("outcome: ") or name.removeprefix("outcome: ") in _NOT_STOPS:
            continue
        stop = moment(step["at"])
        later = [moment(r["started"]) for r in restarts if moment(r["started"]) > stop]
        if later:
            total += (min(later) - stop).total_seconds()
    return total


def waiting(tracker: Tracker | None, branch: str) -> tuple[float | None, bool]:
    """Seconds from the pull request's opening to its merge or close, and whether it merged.

    None when the tracker is missing or unreachable; 0 when the pull request is open or absent."""
    if tracker is None:
        return None, False
    try:
        state = tracker.pull_request_state(branch)
    except (TrackerError, ValueError, OSError):
        return None, False
    if state is None or not state.ended:
        return 0.0, False
    return (moment(state.ended) - moment(state.opened)).total_seconds(), state.merged


def human(data: dict[str, Any], tracker: Tracker | None, takeovers: list[dict[str, Any]]) -> Human:
    branch = f"ariane/{data['ticket']}"
    wait, merged = waiting(tracker, branch)
    restarts = [r for r in takeovers if r["ticket"] == data["ticket"] or r["branch"] == branch]
    return Human(wait, restart_seconds(data, restarts), merged)


def bypassed(data: dict[str, Any], takeovers: list[dict[str, Any]], merged: bool) -> list[str]:
    """The gates bypassed on one delivered ticket: hand takeovers, blocking checks red at
    delivery, a merge while the last review on the branch is no-go."""
    branch = f"ariane/{data['ticket']}"
    own = [t for t in takeovers if t["branch"] == branch]
    found = ["hand takeover"] * len(own)
    if data.get("blocking_red_at_delivery"):
        found.append("blocking check red at delivery")
    last = max(own, key=lambda t: t["started"], default=None)
    verdict = last["first_pass_verdict"] if last else None
    if merged and (verdict == "no-go" or (verdict is None and data["outcome"] == "needs a human")):
        found.append("merged while review no-go")
    return found


def judgement(data: dict[str, Any]) -> dict[str, Any] | None:
    found = data.get("judgement")
    return found if isinstance(found, dict) else None


def attempts(data: dict[str, Any]) -> tuple[int, int, int]:
    found = data.get("attempts")
    found = found if isinstance(found, dict) else {}
    return tuple(  # type: ignore[return-value]
        int(found.get(k) or 0) for k in ("push", "pull_request", "guard_violations")
    )


def shadow_lines(shadows: list[dict[str, Any]], recent: list[dict[str, Any]]) -> list[str]:
    """Totals over `shadows`; the pass line over the last `SHADOW_WINDOW` of `recent`, all the
    shadow tickets whatever the report's `--since`."""
    if not shadows:
        return []
    judged = [d for d in shadows if judgement(d)]
    accepted = [d for d in judged if (judgement(d) or {}).get("verdict") == "accept"]
    push = sum(attempts(d)[0] + attempts(d)[1] for d in shadows)
    violations = sum(attempts(d)[2] for d in shadows)
    rate = f"{len(accepted)}/{len(judged)}" + (
        f" ({100 * len(accepted) // len(judged)}%)" if judged else ""
    )
    lines = [
        f"Shadow: {len(shadows)} tickets, accept rate {rate}, {len(shadows) - len(judged)} not yet"
        f" judged, {push} agent push or pull-request attempts, {violations} guard violations."
    ]
    last = sorted(recent, key=lambda d: (d["started"], d["ticket"]))[-SHADOW_WINDOW:]
    ok = (
        len(last) == SHADOW_WINDOW
        and all(attempts(d)[0] + attempts(d)[1] + attempts(d)[2] == 0 for d in last)
        and sum(1 for d in last if (judgement(d) or {}).get("verdict") == "accept")
        >= SHADOW_ACCEPTED
    )
    lines.append(f"shadow pass: {'yes' if ok else 'no'}")
    return lines
