"""C10: up to two fix rounds after a negative review, then a draft pull request."""

from __future__ import annotations

import pytest

from ariane import git
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, edit_app, go_answer
from test_flow import start, worktree

FINDING = {
    "severity": "blocking",
    "file": "app.txt",
    "line": 1,
    "title": "Wrong value",
    "detail": "Because of reasons.",
}
NO_GO = {**go_answer(), "verdict": "no-go", "findings": [FINDING]}


def implementers(runtime: FakeRuntime) -> list[Session]:
    return [s for s in runtime.sessions if s.role == "implementer"]


def reviewers(runtime: FakeRuntime) -> list[Session]:
    return [s for s in runtime.sessions if s.role == "reviewer"]


@pytest.fixture
def pushes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    done: list[str] = []
    real = git.push

    def counting(*args: object, **kwargs: object) -> str:
        done.append("push")
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(git, "push", counting)
    return done


def test_c10_fix_round_no_go_then_go_delivers_a_normal_pull_request(
    project: Project, tracker: InMemoryTracker, pushes: list[str]
) -> None:
    runtime = FakeRuntime(answers=[NO_GO, go_answer()])
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 0, outcome.line
    assert len(implementers(runtime)) == 2
    assert len(reviewers(runtime)) == 2
    assert len(tracker.opened) == 1
    assert tracker.opened[0]["draft"] is False
    assert "Verdict: **go**" in tracker.opened[0]["body"]
    assert pushes == ["push"]
    assert "ariane/7" in project.remote_branches()
    assert "**no-go**" in project.show("ariane/7", "work/7/review-0.md")
    assert "**go**" in project.show("ariane/7", "work/7/review-1.md")
    assert "Fix session 1 started" in project.show("ariane/7", "work/7/journal.md")


def test_c10_fix_round_three_no_go_give_a_draft_pull_request_with_the_findings(
    project: Project, tracker: InMemoryTracker, pushes: list[str]
) -> None:
    runtime = FakeRuntime(answers=[NO_GO])
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "finish by hand, then run `ariane verify`" in outcome.line
    assert len(reviewers(runtime)) == 3
    assert len(implementers(runtime)) == 3
    assert len(tracker.opened) == 1
    pull = tracker.opened[0]
    assert pull["draft"] is True
    assert "Needs a human" in pull["body"]
    assert "Verdict: **no-go**" in pull["body"]
    assert "Wrong value" in pull["body"]
    assert pushes == ["push"]
    for n in range(3):
        assert f"# Review {n}" in project.show("ariane/7", f"work/7/review-{n}.md")
    status = (worktree(project) / "work/7/status.md").read_text(encoding="utf-8")
    assert "Last action: needs a human" in status
    assert "finish by hand, then run `ariane verify`" in status
    journal = (worktree(project) / "work/7/journal.md").read_text(encoding="utf-8")
    assert "Review 2: no-go" in journal


def test_c10_fix_round_the_fix_session_receives_the_findings_as_data(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime(answers=[NO_GO, go_answer()])
    start(project, tracker, runtime)
    first, fix = implementers(runtime)
    assert "fix round" not in first.prompt
    assert "fix round 1" in fix.prompt
    assert '<untrusted-ticket kind="findings">' in fix.prompt
    assert "Wrong value: Because of reasons." in fix.prompt
    assert fix.cwd == worktree(project)
    assert fix.role == "implementer"


def test_c10_fix_round_blocking_checks_failing_after_a_fix_round_count_as_negative(
    project: Project, tracker: InMemoryTracker
) -> None:
    def action(session: Session) -> None:
        broken = "fix round 1" in session.prompt
        (session.cwd / "app.txt").write_text("broken\n" if broken else "version 2\n")

    runtime = FakeRuntime(action=action, answers=[NO_GO, go_answer()])
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 0, outcome.line
    assert len(implementers(runtime)) == 3
    assert len(reviewers(runtime)) == 2  # no review of the round whose checks failed
    assert "blocking check failed: app has version 2" in implementers(runtime)[2].prompt
    assert "Wrong value" in implementers(runtime)[2].prompt


def test_c10_fix_round_checks_failing_after_the_last_round_give_a_draft(
    project: Project, tracker: InMemoryTracker
) -> None:
    def action(session: Session) -> None:
        broken = "fix round" in session.prompt
        (session.cwd / "app.txt").write_text("broken\n" if broken else "version 2\n")

    runtime = FakeRuntime(action=action, answers=[NO_GO])
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert tracker.opened[0]["draft"] is True
    assert len(reviewers(runtime)) == 1
    assert "Wrong value" in tracker.opened[0]["body"]
    assert "1 failed (1 blocking)" in tracker.opened[0]["body"]


def test_c10_fix_round_a_go_first_time_runs_no_fix_session(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime(action=edit_app)
    assert start(project, tracker, runtime).exit_code == 0
    assert len(implementers(runtime)) == 1
    assert tracker.opened[0]["draft"] is False
