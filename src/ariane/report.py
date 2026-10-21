"""`ariane report`: where time and money went, over the tickets' metrics (C19, C23, ADR 0035)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ariane import measures, metrics, review_escapes, shadow, ticket
from ariane.risk import DEFAULT_MAX_ESCAPE_RATE
from ariane.tracker import Tracker

PARTLY = "partly not reported"
COVERED = "covered by plan"
OUTSIDE = "kept outside"  # a row's key: a stop kept outside the repository, its own record
WORKTREES = "worktrees"  # `<repo>.ariane/worktrees/<n>`, as `flow.worktree_path`


@dataclass(frozen=True)
class Report:
    lines: list[str]
    exit_code: int


def build(
    root: Path,
    since: str | None,
    tracker: Tracker | None = None,
    max_escape_rate: float = DEFAULT_MAX_ESCAPE_RATE,
) -> Report:
    """Read every metrics file under `root/work`, the ticket worktrees, the shadow clones and
    the stops kept outside the repository (`<repo>.ariane/stopped/`, `<repo>.ariane/verify/`),
    keep tickets started on or after `since`. Without a `tracker` the waiting time reads "not
    available"; the selective checks warn above `max_escape_rate`."""
    work = root / ticket.WORK_DIR
    shadows = shadow.clone_path(root, 0).parent
    worktrees = shadows.parent / WORKTREES
    kept_verify = shadows.parent / "verify"  # a verification that ended without committing
    stopped = shadows.parent / "stopped"
    paths = (
        sorted(work.glob(f"*/{metrics.METRICS}"))
        + sorted(work.glob(f"verify/**/{metrics.METRICS}"))
        + sorted(_own_paths(worktrees))
        + sorted(_own_paths(shadows))
        + sorted(stopped.glob(f"**/{metrics.METRICS}"))  # ADR 0031, ADR 0058
        + sorted(kept_verify.glob(f"*/{metrics.METRICS}"))
    )
    if not paths:
        return Report(["No metrics file found. Next: run ariane start <issue>."], 0)
    lines: list[str] = []
    rows: list[dict[str, Any]] = []
    local: dict[tuple[Any, Any], dict[str, Any]] = {}  # a ticket worktree's run, by its start
    recent: list[dict[str, Any]] = []  # every shadow ticket, whatever `since` says
    failed = 0
    for path in paths:
        try:
            data = _read(path)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            failed += 1
            shown = path.relative_to(root if path.is_relative_to(root) else shadows.parent)
            lines.append(f"Could not read {shown.as_posix()}: {_why(exc)}; skipped.")
            continue
        verify_dir = work / "verify"
        if path.is_relative_to(verify_dir):
            data["branch"] = path.parent.relative_to(verify_dir).as_posix()
        elif path.is_relative_to(kept_verify):
            data["branch"] = path.parent.name  # the branch's slug, `ariane-7`
        if path.is_relative_to(stopped) or path.is_relative_to(kept_verify):
            data[OUTSIDE] = True  # its own attempt: never merged with a run of the same start
        if path.is_relative_to(shadows) and data["mode"] != "shadow":
            continue
        if path.is_relative_to(worktrees):
            if data["mode"] != "shadow":
                local[(data["ticket"], data["started"])] = data
            continue
        if data["mode"] == "shadow":
            recent.append(data)
        if since is None or data["started"][:10] >= since:
            rows.append(data)
    rows = _with_local(rows, local, since)
    rows.sort(key=lambda d: (d["started"], d["ticket"], d.get("branch", "")))
    takeovers = [d for d in rows if "branch" in d]
    delivered = [d for d in rows if d["mode"] == "delivered"]
    people: dict[int, measures.Human] = {}
    for d in delivered:
        people[id(d)] = measures.human(d, tracker, takeovers)
        if people[id(d)].waiting_s is None:
            tracker = None  # the tracker failed once: do not wait for it again per ticket
    flagged = {id(d): measures.bypassed(d, takeovers, people[id(d)].merged) for d in delivered}
    lines.extend(_row(d) + _extra(d, people, flagged) for d in rows)
    all_sessions = [s for d in rows for s in d["sessions"]]
    cost, partial = _cost(all_sessions)
    plan = _has_plan(all_sessions)
    seconds = sum(_duration(d) for d in rows)
    rounds = sum(d["rounds"] for d in rows)
    lines.extend(_measure_lines(rows, recent, delivered, people, flagged))
    lines.extend(measures.selective_lines(rows, max_escape_rate))
    lines.extend(review_escapes.lines(rows, tracker))
    lines.extend(review_escapes.category_lines(rows))
    reviewed = [d for d in rows if d["first_pass_verdict"] != metrics.NOT_REVIEWED]
    go = sum(1 for d in reviewed if d["first_pass_verdict"] == "go")
    rate = f"{go}/{len(reviewed)}" + (f" ({100 * go // len(reviewed)}%)" if reviewed else "")
    lines.append(
        f"Totals: {len(rows)} tickets, cost {_money(cost, partial, plan)},"
        f" agent time {_time(seconds)}, {rounds} rounds, first-pass go rate {rate}."
    )
    since_text = f" since {since}" if since else ""
    problem = f", {failed} unreadable file(s) skipped" if failed else ""
    lines.append(
        f"Reported {len(rows)} tickets{since_text}{problem}. Next: "
        + ("fix the files named above." if failed else "nothing.")
    )
    return Report(lines, 1 if failed else 0)


def _own_paths(clones: Path) -> list[Path]:
    """Only a ticket worktree's or shadow clone's own ticket: it also holds every record that
    was on the base branch."""
    found = []
    for clone in clones.glob("*"):
        own = clone / ticket.WORK_DIR / clone.name / metrics.METRICS
        if clone.name.isdigit() and own.is_file():
            found.append(own)
    return found


def _with_local(
    rows: list[dict[str, Any]], local: dict[tuple[Any, Any], dict[str, Any]], since: str | None
) -> list[dict[str, Any]]:
    """A ticket worktree holds the latest record of its run (the full replay after delivery is
    only committed there, ADR 0056): it replaces the merged record of the same run, and a run
    not merged yet is added. A takeover's record and a stop kept outside the repository are
    their own attempts, never replaced: a refused start can share a run's `started` second."""

    def merged_run(d: dict[str, Any]) -> bool:  # not a takeover, nor a stop kept outside
        return "branch" not in d and OUTSIDE not in d

    merged = {(d["ticket"], d["started"]) for d in rows if merged_run(d)}
    kept = [local.get((d["ticket"], d["started"]), d) if merged_run(d) else d for d in rows]
    return kept + [
        d
        for key, d in local.items()
        if key not in merged and (since is None or d["started"][:10] >= since)
    ]


def _read(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("not a JSON object")
    for key in ("ticket", "mode", "started", "outcome", "rounds", "first_pass_verdict"):
        data[key]
    if not isinstance(data["started"], str) or not isinstance(data["sessions"], list):
        raise TypeError("wrong field type")
    for key in ("ticket", "rounds"):
        if isinstance(data[key], bool) or not isinstance(data[key], int):
            raise TypeError(f"{key} is not an integer")
    for key in ("mode", "outcome", "first_pass_verdict"):
        if not isinstance(data[key], str):
            raise TypeError(f"{key} is not a string")
    if "category" in data and not isinstance(data["category"], str):
        raise TypeError("category is not a string")
    recurring = data.get("recurring_findings", 0)
    if isinstance(recurring, bool) or not isinstance(recurring, int):
        raise TypeError("recurring_findings is not an integer")
    for session in data["sessions"]:
        if not isinstance(session, dict):
            raise TypeError("a session is not an object")
        _duration_of(session)
    measures.check_full_replay(data.get("full_replay"))
    return data


def _why(exc: Exception) -> str:
    if isinstance(exc, KeyError):
        return f"missing field {exc}"
    return str(exc) or type(exc).__name__


def _duration_of(session: dict[str, Any]) -> float:
    value = session.get("duration_s", 0)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("duration_s is not a number")
    return float(value)


def _duration(data: dict[str, Any]) -> float:
    return sum(_duration_of(s) for s in data["sessions"])


def _is_plan(session: dict[str, Any]) -> bool:
    return session.get("billing") == "plan"


def _cost(sessions: list[dict[str, Any]]) -> tuple[float, bool]:
    """The reported cost, and whether some is missing; plan-billed sessions have no dollar cost."""
    costs = [s.get("cost_usd") for s in sessions if not _is_plan(s)]
    return sum(c for c in costs if isinstance(c, int | float)), any(
        not isinstance(c, int | float) for c in costs
    )


def _money(cost: float, partial: bool, plan: bool = False) -> str:
    text = f"${cost:.2f}" + (f" ({PARTLY})" if partial else "")
    if not plan:
        return text
    return f"{text}, {COVERED}" if cost or partial else COVERED


def _has_plan(sessions: list[dict[str, Any]]) -> bool:
    return any(_is_plan(s) for s in sessions)


def _time(seconds: float) -> str:
    whole = round(seconds)
    return f"{whole // 60}m{whole % 60:02d}s"


def _row(data: dict[str, Any]) -> str:
    cost, partial = _cost(data["sessions"])
    cost_text = PARTLY if partial else _money(cost, False)
    if partial and cost:
        cost_text = f"{_money(cost, False)}, {PARTLY}"
    if _has_plan(data["sessions"]):
        cost_text = COVERED if cost_text == "$0.00" else f"{cost_text}, {COVERED}"
    branch = f" ({data['branch']})" if "branch" in data else ""
    return (
        f"#{data['ticket']}{branch} {data['mode']} {data['outcome']}: cost {cost_text},"
        f" agent time {_time(_duration(data))}, {data['rounds']} rounds,"
        f" first pass {data['first_pass_verdict']}"
        + (
            f", recurring_findings {data['recurring_findings']}"
            if "recurring_findings" in data
            else ""
        )
    )


def _extra(
    data: dict[str, Any], people: dict[int, measures.Human], flagged: dict[int, list[str]]
) -> str:
    if id(data) in people:
        found = flagged[id(data)]
        return f", {people[id(data)].text()}, gates bypassed {len(found)}" + (
            f" ({', '.join(found)})" if found else ""
        )
    if data["mode"] != "shadow":
        return ""
    judged = measures.judgement(data)
    if judged is None:
        return ", not yet judged"
    return f", judged {judged.get('verdict')} in {judged.get('minutes')} min"


def _measure_lines(
    rows: list[dict[str, Any]],
    recent: list[dict[str, Any]],
    delivered: list[dict[str, Any]],
    people: dict[int, measures.Human],
    flagged: dict[int, list[str]],
) -> list[str]:
    """Human time and gates bypassed in total, then the shadow results."""
    shadows = [d for d in rows if d["mode"] == "shadow"]
    judged = sum(
        int((measures.judgement(d) or {}).get("minutes") or 0)
        for d in shadows
        if measures.judgement(d)
    )
    waits = [p.waiting_s for p in people.values()]
    missing = any(w is None for w in waits)
    wait = sum(w for w in waits if w is not None)
    restart = sum(p.restart_s for p in people.values())
    merged = sum(1 for p in people.values() if p.merged)
    shown = measures.NOT_AVAILABLE if missing and not wait else measures.clock(wait)
    partial = " (partly not available)" if missing and wait else ""
    per = f", {measures.clock((wait + restart) / merged)} per merged pull request" if merged else ""
    lines = [
        f"Human time: waiting {shown}{partial}, restarts {measures.clock(restart)},"
        f" shadow judged {judged} min{per}.",
        f"Gates bypassed: {sum(len(f) for f in flagged.values())} over {len(delivered)}"
        " delivered tickets.",
    ]
    return lines + measures.shadow_lines(shadows, recent)
