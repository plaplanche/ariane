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
    earlier = previous.get("earlier_s") if isinstance(previous, dict) else None
    if isinstance(earlier, int | float) and earlier > 0:  # the earlier restarts of a chain
        total += float(earlier)
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


def _rounds(data: dict[str, Any]) -> list[dict[str, Any]]:
    found = data.get("replays")
    return [r for r in found if isinstance(r, dict)] if isinstance(found, list) else []


def _seconds(value: Any) -> float:
    ok = isinstance(value, int | float) and not isinstance(value, bool)
    return float(value) if ok else 0.0


def full_replay(data: dict[str, Any]) -> dict[str, Any] | None:
    """The `full_replay` object of a ticket's metrics when it ran to its end, or None."""
    found = data.get("full_replay")
    if not isinstance(found, dict) or found.get("ran") is not True or found.get("stopped"):
        return None
    return found


def selective_lines(rows: list[dict[str, Any]], max_escape_rate: float) -> list[str]:
    """The "Selective checks" lines (#186): the tickets with a round that skipped a check or ran
    one partly, their replay time, the full replays' time against the selective rounds they
    replayed, the escapes and their rate per full replay, and a warning above
    `max_escape_rate`. No such ticket gives no line."""
    chosen = [d for d in rows if any(r.get("skipped") or r.get("partial") for r in _rounds(d))]
    if not chosen:
        return []
    with_selection = sum(_seconds(r.get("duration_s")) for d in chosen for r in _rounds(d))
    sampled = [(d, f) for d in chosen if (f := full_replay(d)) is not None]
    selective = sum(_seconds(_rounds(d)[-1].get("duration_s")) for d, _ in sampled)
    full = sum(_seconds(f.get("duration_s")) for _, f in sampled)
    escapes = sum(len(f.get("escapes") or []) for _, f in sampled)
    rate = escapes / len(sampled) if sampled else 0.0
    shown = f"{escapes}/{len(sampled)} ({100 * rate:.1f}%)" if sampled else "not measured"
    lines = [
        f"Selective checks: {len(chosen)} tickets with selection, replay time"
        f" {with_selection:.1f} s; on the {len(sampled)} sampled tickets {selective:.1f} s"
        f" selective versus {full:.1f} s full ({full - selective:.1f} s saved);"
        f" {len(sampled)} full replays, {escapes} escapes, escape rate {shown}."
    ]
    if sampled and rate > max_escape_rate:
        lines.append(
            f"Warning: the escape rate {100 * rate:.1f}% is above max_escape_rate"
            f" {100 * max_escape_rate:g}%: skipped or partial checks let failures through;"
            " consider turning selection off (`paths`, `[checks_policy]`)."
        )
    return lines
