"""C19: each ticket records its measurements in work/<n>/metrics.json."""

from __future__ import annotations

import json
from typing import Any

from test_fix_rounds import NO_GO

from ariane.runtime import Session, SessionResult, StopReason
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, go_answer, sh
from test_flow import start, worktree


def metrics(project: Project, ref: str = "ariane/7") -> dict[str, Any]:
    data = json.loads(project.show(ref, "work/7/metrics.json"))
    assert isinstance(data, dict)
    return data


def test_c19_metrics_delivered_ticket_has_both_sessions_and_the_go_verdict(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert start(project, tracker, FakeRuntime()).exit_code == 0
    data = metrics(project)
    assert data["ticket"] == 7
    assert data["mode"] == "delivered"
    assert data["outcome"] == "delivered"
    assert data["first_pass_verdict"] == "go"
    assert data["rounds"] == 0
    assert data["started"].endswith("Z")
    assert [s["role"] for s in data["sessions"]] == ["implementer", "reviewer"]
    implementer = data["sessions"][0]
    assert implementer["cost_usd"] == 0.42
    assert implementer["input_tokens"] == 10
    assert implementer["output_tokens"] == 20
    assert implementer["cache_read_tokens"] == 30
    assert implementer["cache_write_tokens"] == 40
    assert implementer["stop_reason"] == "finished"
    assert implementer["runtime"] == "fake"
    assert implementer["duration_s"] >= 0
    assert data["steps"][0]["name"] == "folder opened"
    assert data["steps"][-1]["name"] == "outcome: delivered"


def test_c19_metrics_fix_round_counts_rounds_and_keeps_the_first_pass_no_go(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert start(project, tracker, FakeRuntime(answers=[NO_GO, go_answer()])).exit_code == 0
    data = metrics(project)
    assert data["rounds"] == 1
    assert data["first_pass_verdict"] == "no-go"
    assert [(s["role"], s["round"]) for s in data["sessions"]] == [
        ("implementer", 0),
        ("reviewer", 0),
        ("implementer", 1),
        ("reviewer", 1),
    ]


def test_c19_metrics_stopped_ticket_is_committed_as_stopped(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime(stop_reason=StopReason.BUDGET)
    assert start(project, tracker, runtime).exit_code == 1
    data = json.loads(sh(["git", "show", "ariane/7:work/7/metrics.json"], project.root))
    assert data["outcome"] == "stopped"
    assert data["first_pass_verdict"] == "not reviewed"
    assert data["sessions"][0]["stop_reason"] == "budget"


def test_c19_metrics_unreported_cost_and_tokens_are_null(
    project: Project, tracker: InMemoryTracker
) -> None:
    class Silent(FakeRuntime):
        def run(self, session: Session) -> SessionResult:
            done = super().run(session)
            return SessionResult(
                done.stop_reason,
                None,
                None,
                None,
                None,
                None,
                done.summary,
                structured_output=done.structured_output,
            )

    assert start(project, tracker, Silent()).exit_code == 0
    session = metrics(project)["sessions"][0]
    assert session["cost_usd"] is None
    assert session["input_tokens"] is None
    assert session["cache_write_tokens"] is None


def test_c19_metrics_file_is_in_the_committed_records(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert start(project, tracker, FakeRuntime()).exit_code == 0
    text = (worktree(project) / "work/7/metrics.json").read_text(encoding="utf-8")
    assert text == sh(["git", "show", "ariane/7:work/7/metrics.json"], project.root) + "\n"
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
