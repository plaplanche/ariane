"""C1, C11, C23: the record of a delivery ends with the pull request, committed locally only."""

from __future__ import annotations

from pathlib import Path

import pytest

from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, go_answer, sh
from test_flow import start, worktree

FINDING = {"severity": "blocking", "file": "app.txt", "line": 1, "title": "T", "detail": "D."}
NO_GO = {**go_answer(), "verdict": "no-go", "findings": [FINDING]}


def _git(tree: Path, *args: str) -> str:
    return sh(["git", *args], tree)


def _runtime(draft: bool) -> FakeRuntime:
    return FakeRuntime(answers=[NO_GO]) if draft else FakeRuntime()


@pytest.mark.parametrize("draft", [False, True], ids=["ready", "draft"])
def test_c1_delivery_record_leaves_the_ticket_working_tree_clean(
    project: Project, tracker: InMemoryTracker, draft: bool
) -> None:
    start(project, tracker, _runtime(draft))
    assert tracker.opened
    assert _git(worktree(project), "status", "--porcelain") == ""


@pytest.mark.parametrize("draft", [False, True], ids=["ready", "draft"])
def test_c1_delivery_record_is_one_local_commit_on_the_ticket_folder_after_the_push(
    project: Project, tracker: InMemoryTracker, draft: bool
) -> None:
    start(project, tracker, _runtime(draft))
    tree = worktree(project)
    pushed = project.remote_branches()["ariane/7"]
    assert _git(tree, "rev-parse", "HEAD~1") == pushed
    assert _git(tree, "log", "-1", "--format=%s") == "#7: record the pull request"
    changed = _git(tree, "diff", "--name-only", pushed, "HEAD").splitlines()
    assert changed and all(path.startswith("work/7/") for path in changed)
    journal = _git(tree, "show", "HEAD:work/7/journal.md")
    assert "Pushed `ariane/7`" in journal
    assert "Pull request #1001: memory://pulls/1001" in journal
    assert "Pull request #" not in project.show("ariane/7", "work/7/journal.md")


@pytest.mark.parametrize("draft", [False, True], ids=["ready", "draft"])
def test_c1_delivery_record_statuses_stay_on_the_pushed_commit(
    project: Project, tracker: InMemoryTracker, draft: bool
) -> None:
    start(project, tracker, _runtime(draft))
    pushed = project.remote_branches()["ariane/7"]
    assert _git(worktree(project), "rev-parse", "HEAD") != pushed
    assert tracker.statuses
    assert {s["sha"] for s in tracker.statuses} == {pushed}


def test_c1_delivery_record_pushed_status_says_pushing_and_local_says_delivered(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert start(project, tracker, FakeRuntime()).exit_code == 0
    remote = project.show("ariane/7", "work/7/status.md")
    assert "Last action: pushing" in remote
    assert "pushing ariane/7, then opening the pull request" in remote
    assert "pull request #" not in remote
    local = _git(worktree(project), "show", "HEAD:work/7/status.md")
    assert "Last action: delivered" in local
    assert "pull request #1001 opened: memory://pulls/1001" in local
    assert "see the pull request, or run ariane status 7" in local


def test_c1_delivery_record_draft_status_says_needs_a_human_before_and_after(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert start(project, tracker, _runtime(True)).exit_code == 1
    remote = project.show("ariane/7", "work/7/status.md")
    assert "Last action: needs a human" in remote
    assert (
        "pushing ariane/7, then opening a draft pull request: the review is still no-go" in remote
    )
    local = _git(worktree(project), "show", "HEAD:work/7/status.md")
    assert "Last action: needs a human" in local
    assert "draft pull request #1001 opened: memory://pulls/1001" in local
    assert "finish by hand, then run `ariane verify`" in local


def test_c1_delivery_record_commits_the_refused_statuses_warning(
    project: Project, tracker: InMemoryTracker
) -> None:
    tracker.refuse_statuses = True
    assert start(project, tracker, FakeRuntime()).exit_code == 0
    tree = worktree(project)
    assert _git(tree, "status", "--porcelain") == ""
    assert "Warning: commit statuses refused" in _git(tree, "show", "HEAD:work/7/journal.md")
