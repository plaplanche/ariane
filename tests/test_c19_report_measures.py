"""C19: `ariane report` shows human time, gates bypassed and shadow results (ADR 0038)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ariane import report, shadow
from ariane.tracker import InMemoryTracker, PullRequestState


def put(path: Path, number: int, started: str, **kw: Any) -> None:
    data = {
        "ticket": number,
        "mode": kw.pop("mode", "delivered"),
        "started": started,
        "sessions": [{"cost_usd": 0.1, "duration_s": 10}],
        "rounds": 0,
        "first_pass_verdict": kw.pop("verdict", "go"),
        "outcome": kw.pop("outcome", "delivered"),
    } | kw
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def merged(opened: str, ended: str, merged: bool = True) -> PullRequestState:
    return PullRequestState(opened, ended, merged)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    return path


def text(root: Path, tracker: InMemoryTracker | None = None) -> str:
    return "\n".join(report.build(root, None, tracker).lines)


def test_c19_report_human_waiting_time_from_the_tracker(root: Path) -> None:
    put(root / "work/5/metrics.json", 5, "2026-10-01T09:00:00Z")
    tracker = InMemoryTracker(
        pull_states={"ariane/5": merged("2026-10-01T10:00:00Z", "2026-10-01T12:30:00Z")}
    )
    out = text(root, tracker)
    assert "human time: waiting 2h30m, restarts 0h00m" in out
    assert "Human time: waiting 2h30m, restarts 0h00m, shadow judged 0 min, 2h30m per merged" in out


def test_c19_report_human_offline_is_not_available(root: Path) -> None:
    put(root / "work/5/metrics.json", 5, "2026-10-01T09:00:00Z")
    assert "waiting not available" in text(root, None)
    down = InMemoryTracker(unreachable=True)
    out = text(root, down)
    assert "Human time: waiting not available" in out
    assert "Totals: 1 tickets" in out


def test_c19_report_human_stop_to_restart_time(root: Path) -> None:
    steps = [{"name": "outcome: stopped", "at": "2026-10-01T10:00:00Z"}]
    put(root / "work/5/metrics.json", 5, "2026-10-01T09:00:00Z", steps=steps)
    put(root / "work/verify/ariane/5/metrics.json", 5, "2026-10-01T10:45:00Z", mode="verify")
    assert "restarts 0h45m" in text(root, None)


def test_c19_report_gates_hand_takeover_is_counted(root: Path) -> None:
    put(root / "work/5/metrics.json", 5, "2026-10-01T09:00:00Z")
    put(root / "work/verify/ariane/5/metrics.json", 5, "2026-10-02T09:00:00Z", mode="verify")
    out = text(root, None)
    assert "gates bypassed 1 (hand takeover)" in out
    assert "Gates bypassed: 1 over 1 delivered tickets." in out


def test_c19_report_gates_blocking_red_at_delivery(root: Path) -> None:
    put(root / "work/5/metrics.json", 5, "2026-10-01T09:00:00Z", blocking_red_at_delivery=2)
    assert "gates bypassed 1 (blocking check red at delivery)" in text(root, None)


def test_c19_report_gates_merged_no_go_counted_then_verify_go_not(root: Path) -> None:
    put(
        root / "work/5/metrics.json", 5, "2026-10-01T09:00:00Z", outcome="needs a human",
        verdict="no-go",
    )  # fmt: skip
    tracker = InMemoryTracker(
        pull_states={"ariane/5": merged("2026-10-01T10:00:00Z", "2026-10-01T11:00:00Z")}
    )
    assert "gates bypassed 1 (merged while review no-go)" in text(root, tracker)
    put(root / "work/verify/ariane/5/metrics.json", 5, "2026-10-01T10:30:00Z", mode="verify")
    out = text(root, tracker)
    assert "merged while review no-go" not in out
    assert "gates bypassed 1 (hand takeover)" in out


def test_c19_report_gates_unmerged_no_go_is_not_counted(root: Path) -> None:
    put(root / "work/5/metrics.json", 5, "2026-10-01T09:00:00Z", outcome="needs a human")
    tracker = InMemoryTracker(
        pull_states={"ariane/5": merged("2026-10-01T10:00:00Z", "2026-10-01T11:00:00Z", False)}
    )
    assert "gates bypassed 0" in text(root, tracker)


def shadows(root: Path, accepted: int, total: int, **kw: Any) -> None:
    for n in range(1, total + 1):
        verdict = "accept" if n <= accepted else "reject"
        put(
            shadow.clone_path(root, n) / f"work/{n}/metrics.json", n, f"2026-10-{n:02d}T09:00:00Z",
            mode="shadow", judgement={"verdict": verdict, "minutes": 5}, **kw,
        )  # fmt: skip


def test_c19_report_shadow_passing_set(root: Path) -> None:
    shadows(root, 8, 10)
    out = text(root)
    assert "Shadow: 10 tickets, accept rate 8/10 (80%), 0 not yet judged, 0 agent" in out
    assert "shadow pass: yes" in out
    assert "judged accept in 5 min" in out
    assert "shadow judged 50 min" in out


def test_c19_report_shadow_failing_sets(root: Path) -> None:
    shadows(root, 7, 10)
    assert "shadow pass: no" in text(root)


def test_c19_report_shadow_attempt_fails_the_pass(root: Path) -> None:
    shadows(root, 10, 10, attempts={"push": 1, "pull_request": 0, "guard_violations": 0})
    out = text(root)
    assert "10 agent push or pull-request attempts" in out
    assert "shadow pass: no" in out


def test_c19_report_shadow_unjudged_and_too_few(root: Path) -> None:
    put(
        shadow.clone_path(root, 3) / "work/3/metrics.json", 3, "2026-10-03T09:00:00Z", mode="shadow"
    )
    out = text(root)
    assert "accept rate 0/0, 1 not yet judged" in out
    assert "not yet judged" in out.splitlines()[0]
    assert "shadow pass: no" in out


def test_c19_report_shadow_clone_copies_of_other_tickets_are_not_counted_again(
    root: Path,
) -> None:
    put(root / "work/5/metrics.json", 5, "2026-10-01T09:00:00Z")
    clone = shadow.clone_path(root, 8)
    put(clone / "work/8/metrics.json", 8, "2026-10-02T09:00:00Z", mode="shadow")
    put(clone / "work/5/metrics.json", 5, "2026-10-01T09:00:00Z")
    out = text(root, None)
    assert "Totals: 2 tickets" in out
    assert "Gates bypassed: 0 over 1 delivered tickets." in out
