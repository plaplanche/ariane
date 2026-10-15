"""`ariane report`: where time and money went, over the tickets' metrics (C19, C23, ADR 0035)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ariane import measures, metrics, shadow, ticket
from ariane.tracker import Tracker

PARTLY = "partly not reported"


@dataclass(frozen=True)
class Report:
    lines: list[str]
    exit_code: int


def build(root: Path, since: str | None, tracker: Tracker | None = None) -> Report:
    """Read every metrics file under `root/work` and the shadow clones, keep tickets started on
    or after `since`. Without a `tracker` the waiting time reads "not available"."""
    work = root / ticket.WORK_DIR
    shadows = shadow.clone_path(root, 0).parent
    paths = (
        sorted(work.glob(f"*/{metrics.METRICS}"))
        + sorted(work.glob(f"verify/**/{metrics.METRICS}"))
        + sorted(_shadow_paths(shadows))
    )
    if not paths:
        return Report(["No metrics file found. Next: run ariane start <issue>."], 0)
    lines: list[str] = []
    rows: list[dict[str, Any]] = []
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
        if path.is_relative_to(shadows) and data["mode"] != "shadow":
            continue
        if data["mode"] == "shadow":
            recent.append(data)
        if since is None or data["started"][:10] >= since:
            rows.append(data)
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
    cost, partial = _cost([s for d in rows for s in d["sessions"]])
    seconds = sum(_duration(d) for d in rows)
    rounds = sum(d["rounds"] for d in rows)
    lines.extend(_measure_lines(rows, recent, delivered, people, flagged))
    reviewed = [d for d in rows if d["first_pass_verdict"] != metrics.NOT_REVIEWED]
    go = sum(1 for d in reviewed if d["first_pass_verdict"] == "go")
    rate = f"{go}/{len(reviewed)}" + (f" ({100 * go // len(reviewed)}%)" if reviewed else "")
    lines.append(
        f"Totals: {len(rows)} tickets, cost {_money(cost, partial)}, agent time {_time(seconds)},"
        f" {rounds} rounds, first-pass go rate {rate}."
    )
    since_text = f" since {since}" if since else ""
    problem = f", {failed} unreadable file(s) skipped" if failed else ""
    lines.append(
        f"Reported {len(rows)} tickets{since_text}{problem}. Next: "
        + ("fix the files named above." if failed else "nothing.")
    )
    return Report(lines, 1 if failed else 0)


def _shadow_paths(shadows: Path) -> list[Path]:
    """Only a clone's own ticket: the clone also holds every record that was on the base branch."""
    found = []
    for clone in shadows.glob("*"):
        own = clone / ticket.WORK_DIR / clone.name / metrics.METRICS
        if clone.name.isdigit() and own.is_file():
            found.append(own)
    return found


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
    for session in data["sessions"]:
        if not isinstance(session, dict):
            raise TypeError("a session is not an object")
        _duration_of(session)
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


def _cost(sessions: list[dict[str, Any]]) -> tuple[float, bool]:
    costs = [s.get("cost_usd") for s in sessions]
    return sum(c for c in costs if isinstance(c, int | float)), any(
        not isinstance(c, int | float) for c in costs
    )


def _money(cost: float, partial: bool) -> str:
    return f"${cost:.2f}" + (f" ({PARTLY})" if partial else "")


def _time(seconds: float) -> str:
    whole = round(seconds)
    return f"{whole // 60}m{whole % 60:02d}s"


def _row(data: dict[str, Any]) -> str:
    cost, partial = _cost(data["sessions"])
    cost_text = PARTLY if partial else _money(cost, False)
    if partial and cost:
        cost_text = f"{_money(cost, False)}, {PARTLY}"
    branch = f" ({data['branch']})" if "branch" in data else ""
    return (
        f"#{data['ticket']}{branch} {data['mode']} {data['outcome']}: cost {cost_text},"
        f" agent time {_time(_duration(data))}, {data['rounds']} rounds,"
        f" first pass {data['first_pass_verdict']}"
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
