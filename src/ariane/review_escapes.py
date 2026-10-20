"""Review escapes per model pair, and stopped tickets per category, for `ariane report` (C10,
C19, ADR 0058)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ariane.stop import CATEGORIES
from ariane.tracker import Tracker, TrackerError

MIN_TICKETS = 5  # no rate is shown over fewer tickets
BY_HAND = "by hand"  # the implementer of a hand takeover (`ariane verify`)
NO_CI = (
    "Review escapes: CI not read (no CI data recorded on the reviewed heads); escapes count"
    " human changes requested and pull requests closed without merge."
)
NO_TRACKER = "Review escapes: tracker not available; escapes not counted."
_Pair = tuple[str, str, str]  # implementer model, reviewer model, reviewer runtime


@dataclass
class _Group:
    reviews: int = 0
    go: int = 0
    findings: int = 0
    outcomes: dict[int, bool] = field(default_factory=dict)  # per `go` ticket told: escaped
    seen: set[int] = field(default_factory=set)  # tickets with a review in this group

    @property
    def tickets(self) -> int:  # distinct tickets: several records of one ticket count once
        return len(self.outcomes)

    @property
    def escapes(self) -> int:
        return sum(self.outcomes.values())

    def rate(self) -> str:
        if self.tickets < MIN_TICKETS:
            return f"escape rate not shown ({self.tickets} tickets, fewer than {MIN_TICKETS})"
        return (
            f"escape rate {self.escapes}/{self.tickets}"
            f" ({100 * self.escapes // self.tickets}%) over {self.tickets} tickets"
        )


def implementer_model(data: dict[str, Any]) -> str:
    """The first implementer session's model; a hand takeover has none."""
    for session in data["sessions"]:
        if session.get("role") == "implementer":
            return str(session.get("model") or "unknown")
    return BY_HAND if "branch" in data else "unknown"


def _ci_red(data: dict[str, Any]) -> bool | None:
    """Whether the pull request's CI was red on the reviewed head; None without CI data."""
    found = data.get("ci_failures")
    if found is None:
        return None
    return bool(found) if isinstance(found, list | int) and not isinstance(found, bool) else None


def escaped(data: dict[str, Any], tracker: Tracker) -> bool | None:
    """Whether the `go` that delivered `data` was wrong: a red CI on the reviewed head, or after
    the `go`, a human "changes requested" review or the pull request closed without merge. None
    when there is no pull request to tell; `TrackerError` when the tracker fails. The pull
    request is the branch's latest (one per ticket branch, ADR 0058)."""
    branch = data.get("branch") or f"ariane/{data['ticket']}"
    state = tracker.pull_request_state(branch)
    if state is None:
        return None
    reviews = [s for s in data["sessions"] if s.get("role") == "reviewer" and "verdict" in s]
    since = str(reviews[-1].get("at") or data["started"])  # a record from before `at`: its start
    if _ci_red(data) or (state.ended >= since and not state.merged):
        return True
    return bool(state.number) and tracker.changes_requested(state.number, since)


def _delivered_go(data: dict[str, Any], reviews: list[dict[str, Any]]) -> bool:
    """The record ended delivered green on a `go` (its last review) and has a pull request."""
    return (
        data["mode"] != "shadow"
        and data["outcome"] == "delivered"
        and not data.get("category")
        and bool(reviews)
        and reviews[-1].get("verdict") == "go"
    )


def lines(rows: list[dict[str, Any]], tracker: Tracker | None) -> list[str]:
    """One line per model pair and reviewer runtime that has recorded verdicts, a note on what
    was not read, and the rates side by side when two pairs or more show one."""
    groups: dict[_Pair, _Group] = {}
    ci_read = False
    for data in rows:
        reviews = [s for s in data["sessions"] if s.get("role") == "reviewer" and "verdict" in s]
        implementer = implementer_model(data)
        for session in reviews:
            pair = (implementer, str(session.get("model")), str(session.get("runtime")))
            group = groups.setdefault(pair, _Group())
            group.reviews += 1
            group.go += session["verdict"] == "go"
            found = session.get("findings")
            group.findings += found if isinstance(found, int) and not isinstance(found, bool) else 0
            group.seen.add(data["ticket"])
        if tracker is None or not _delivered_go(data, reviews):
            continue
        last = reviews[-1]
        try:
            result = escaped(data, tracker)
        except (TrackerError, ValueError, OSError):
            tracker = None  # the tracker failed once: do not wait for it again per ticket
            continue
        ci_read = ci_read or _ci_red(data) is not None
        if result is not None:
            group = groups[(implementer, str(last.get("model")), str(last.get("runtime")))]
            ticket = int(data["ticket"])  # a ticket's records count once: escaped if any is
            group.outcomes[ticket] = group.outcomes.get(ticket, False) or result
    if not groups:
        return []
    out = []
    for (implementer, reviewer, runtime), group in sorted(groups.items()):
        per = f"{group.findings / group.reviews:.1f}"
        out.append(
            f"Review escapes, implementer {implementer}, reviewer {reviewer} ({runtime}):"
            f" {group.reviews} reviews over {len(group.seen)} tickets, {group.go} go,"
            f" {per} findings per review, {group.escapes} escapes, {group.rate()}."
        )
    out.append(NO_TRACKER if tracker is None else "" if ci_read else NO_CI)
    shown = [(p, g) for p, g in sorted(groups.items()) if g.tickets >= MIN_TICKETS]
    if len(shown) > 1:
        out.append(
            "Escape rates compared: "
            + "; ".join(
                f"{i} / {r} ({rt}) {100 * g.escapes // g.tickets}% over {g.tickets} tickets"
                for (i, r, rt), g in shown
            )
            + "."
        )
    return [line for line in out if line]


def category_lines(rows: list[dict[str, Any]]) -> list[str]:
    """The tickets that did not end delivered green, per stop category, then per implementer
    model; a record from before categories is `not recorded`."""
    stopped = [d for d in rows if d["outcome"] not in ("delivered", "running") or d.get("category")]
    if not stopped:
        return []

    def counts(found: list[dict[str, Any]]) -> str:
        tally = Counter(str(d.get("category") or "not recorded") for d in found)
        order = [*CATEGORIES, *sorted(set(tally) - set(CATEGORIES))]
        return ", ".join(f"{name} {tally[name]}" for name in order if tally[name])

    out = [f"Stopped by category: {counts(stopped)} over {len(stopped)} tickets."]
    models = sorted({implementer_model(d) for d in stopped})
    out.extend(
        f"Stopped by category, implementer {model}:"
        f" {counts([d for d in stopped if implementer_model(d) == model])}."
        for model in models
    )
    return out
