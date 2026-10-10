"""C23: `ariane verify` checks and reviews a branch finished by hand (ADR 0028)."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_fix_rounds import NO_GO

from ariane import git, verify
from ariane.flow import Outcome
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, make_config, sh
from test_flow import environ

BRANCH = "hand/fix"


@pytest.fixture
def branch(project: Project) -> str:
    """A local branch with one commit that makes the default check pass, not checked out."""
    sh(["git", "branch", BRANCH], project.root)
    other = project.root.parent / "hand-tree"
    sh(["git", "worktree", "add", "--quiet", str(other), BRANCH], project.root)
    (other / "app.txt").write_text("version 2\n", encoding="utf-8")
    sh(["git", "commit", "--quiet", "-am", "Bump the version by hand"], other)
    sh(["git", "worktree", "remove", str(other)], project.root)
    return BRANCH


@pytest.fixture
def pushes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    done: list[str] = []
    monkeypatch.setattr(git, "push", lambda *a, **k: done.append("push"))
    return done


def run(
    project: Project,
    runtime: FakeRuntime,
    tracker: InMemoryTracker | None = None,
    issue: int | None = None,
    name: str = BRANCH,
) -> Outcome:
    return verify.verify(
        name,
        repo_root=project.root,
        config=make_config(),
        runtime=runtime,
        environ=environ(),
        tracker=tracker,
        issue_number=issue,
    )


def test_c23_verify_green_branch_with_go_commits_the_records_and_exits_0(
    project: Project, branch: str, pushes: list[str]
) -> None:
    before = project.remote_branches()
    outcome = run(project, FakeRuntime())
    assert outcome.exit_code == 0, outcome.line
    assert outcome.line.endswith("Next: push the branch and open the pull request.")
    assert "1 passed, 0 failed (0 blocking)" in outcome.line and "Review go" in outcome.line
    assert "Verify hand/fix" in sh(["git", "log", "-1", "--format=%s", BRANCH], project.root)
    shown = sh(["git", "show", f"{BRANCH}:work/verify/{BRANCH}/review.md"], project.root)
    assert "Verdict: **go**" in shown
    assert "app has version 2" in sh(
        ["git", "show", f"{BRANCH}:work/verify/{BRANCH}/checks.md"], project.root
    )
    assert pushes == [] and project.remote_branches() == before


def test_c23_verify_failing_check_exits_1_with_the_next_action(
    project: Project, pushes: list[str]
) -> None:
    sh(["git", "branch", BRANCH], project.root)  # app.txt still says version 1
    outcome = run(project, FakeRuntime())
    assert outcome.exit_code == 1
    assert "0 passed, 1 failed (1 blocking)" in outcome.line
    assert outcome.line.endswith("Next: fix the findings, then run verify again.")
    assert "**fail**" in sh(
        ["git", "show", f"{BRANCH}:work/verify/{BRANCH}/checks.md"], project.root
    )
    assert pushes == []


def test_c23_verify_no_go_exits_1_with_the_next_action(
    project: Project, branch: str, pushes: list[str]
) -> None:
    runtime = FakeRuntime(answers=[NO_GO])
    outcome = run(project, runtime)
    assert outcome.exit_code == 1
    assert "Review no-go" in outcome.line
    assert outcome.line.endswith("Next: fix the findings, then run verify again.")
    assert "Wrong value" in sh(
        ["git", "show", f"{BRANCH}:work/verify/{BRANCH}/review.md"], project.root
    )
    assert len(runtime.sessions) == 1 and pushes == []


def test_c23_verify_dirty_checked_out_branch_is_refused_naming_the_changes(
    project: Project, branch: str
) -> None:
    sh(["git", "checkout", "--quiet", BRANCH], project.root)
    (project.root / "app.txt").write_text("edited\n", encoding="utf-8")
    runtime = FakeRuntime()
    outcome = run(project, runtime)
    assert outcome.exit_code == 1
    assert "uncommitted changes (M app.txt)" in outcome.line
    assert runtime.sessions == []


def test_c23_verify_clean_checked_out_branch_gets_the_commit_in_its_tree(
    project: Project, branch: str
) -> None:
    sh(["git", "checkout", "--quiet", BRANCH], project.root)
    assert run(project, FakeRuntime()).exit_code == 0
    assert (project.root / "work" / "verify" / BRANCH / "review.md").is_file()


def test_c23_verify_gives_the_reviewer_the_issue_or_the_commit_messages(
    project: Project, branch: str, tracker: InMemoryTracker
) -> None:
    by_commits = FakeRuntime()
    run(project, by_commits)
    assert "Bump the version by hand" in by_commits.sessions[0].prompt
    by_issue = FakeRuntime()
    assert run(project, by_issue, tracker, 7, name=BRANCH).exit_code == 0
    assert "Set app.txt to version 2." in by_issue.sessions[0].prompt


def test_c23_verify_unknown_branch_is_refused(project: Project) -> None:
    outcome = run(project, FakeRuntime(), name="nope")
    assert outcome.exit_code == 1 and "does not exist locally" in outcome.line


def test_c23_verify_leaves_no_working_tree_behind(project: Project, branch: str) -> None:
    run(project, FakeRuntime())
    assert not verify.replay_path(project.root, BRANCH).exists()
    assert str(Path(project.root.parent / "hand-tree")) not in sh(
        ["git", "worktree", "list"], project.root
    )


def test_c23_verify_records_a_project_ignoring_work_gets_exit_1_and_nothing_recorded(
    project: Project, branch: str
) -> None:
    exclude = project.root / ".git" / "info" / "exclude"
    exclude.write_text("work/\n", encoding="utf-8")
    outcome = run(project, FakeRuntime())
    assert outcome.exit_code == 1
    assert "nothing was recorded" in outcome.line
    assert "check that work/ is not ignored, then run verify again" in outcome.line
    assert "Records committed" not in outcome.line
    assert sh(["git", "log", "-1", "--format=%s", BRANCH], project.root).startswith("Bump")


def test_c23_verify_records_a_branch_committed_to_during_the_run_commits_nothing(
    project: Project, branch: str
) -> None:
    def commit_elsewhere(session: Session) -> None:
        other = project.root.parent / "racing-tree"
        sh(["git", "worktree", "add", "--quiet", str(other), BRANCH], project.root)
        (other / "app.txt").write_text("version 3\n", encoding="utf-8")
        sh(["git", "commit", "--quiet", "-am", "Racing commit"], other)
        sh(["git", "worktree", "remove", str(other)], project.root)

    runtime = FakeRuntime(review_actions=[commit_elsewhere])
    outcome = run(project, runtime)
    assert outcome.exit_code == 1
    assert "Did not verify" in outcome.line
    assert sh(["git", "log", "-1", "--format=%s", BRANCH], project.root) == "Racing commit"


def test_c23_verify_records_a_branch_checked_out_elsewhere_during_the_run_commits_nothing(
    project: Project, branch: str
) -> None:
    other = project.root.parent / "late-tree"

    def check_out(session: Session) -> None:
        sh(["git", "worktree", "add", "--quiet", str(other), BRANCH], project.root)

    outcome = run(project, FakeRuntime(review_actions=[check_out]))
    assert outcome.exit_code == 1
    assert "now checked out" in outcome.line
    assert sh(["git", "log", "-1", "--format=%s", BRANCH], project.root).startswith("Bump")
    sh(["git", "worktree", "remove", "--force", str(other)], project.root)
