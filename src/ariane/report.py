"""`ariane report`: where time and money went, over the tickets' metrics (C19, C23, ADR 0035)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ariane import metrics, ticket

PARTLY = "partly not reported"


@dataclass(frozen=True)
class Report:
    lines: list[str]
    exit_code: int


def build(root: Path, since: str | None) -> Report:
    """Read every metrics file under `root/work`, keep tickets started on or after `since`."""
    work = root / ticket.WORK_DIR
    paths = sorted(work.glob(f"*/{metrics.METRICS}")) + sorted(
        work.glob(f"verify/**/{metrics.METRICS}")
    )
    if not paths:
        return Report(["No metrics file found. Next: run ariane start <issue>."], 0)
    lines: list[str] = []
    rows: list[dict[str, Any]] = []
    failed = 0
    for path in paths:
        try:
            data = _read(path)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            failed += 1
            lines.append(
                f"Could not read {path.relative_to(root).as_posix()}: {_why(exc)}; skipped."
            )
            continue
        verify_dir = work / "verify"
        if path.is_relative_to(verify_dir):
            data["branch"] = path.parent.relative_to(verify_dir).as_posix()
        if since is None or data["started"][:10] >= since:
            rows.append(data)
    rows.sort(key=lambda d: (d["started"], d["ticket"], d.get("branch", "")))
    lines.extend(_row(d) for d in rows)
    cost, partial = _cost([s for d in rows for s in d["sessions"]])
    seconds = sum(_duration(d) for d in rows)
    rounds = sum(d["rounds"] for d in rows)
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
