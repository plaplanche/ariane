"""C19, C23: shadow mode runs a ticket in a separate clone and delivers nothing (ADR 0036)."""

from __future__ import annotations

import hashlib
import json
import os

from ariane import flow, shadow
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, make_config, sh


def run_shadow(project: Project, tracker: InMemoryTracker, runtime: FakeRuntime) -> flow.Outcome:
    return shadow.start(
        7,
        repo_root=project.root,
        config=make_config(),
        tracker=tracker,
        runtime=runtime,
        environ={**os.environ, "GH_TOKEN": "secret-token-for-tests"},
    )


def git_state(project: Project) -> dict[str, str]:
    """Every byte of the user's `.git`, by file, plus the worktree list."""
    state = {}
    git_dir = project.root / ".git"
    for path in sorted(p for p in git_dir.rglob("*") if p.is_file()):
        state[path.relative_to(git_dir).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    state["worktree list"] = sh(["git", "worktree", "list"], project.root)
    return state


def test_c19_shadow_pushes_opens_and_posts_nothing(
    project: Project, tracker: InMemoryTracker
) -> None:
    before = project.remote_branches()
    outcome = run_shadow(project, tracker, FakeRuntime())
    assert outcome.exit_code == 0, outcome.line
    assert tracker.opened == []
    assert tracker.statuses == []
    assert project.remote_branches() == before


def test_c19_shadow_leaves_the_users_git_byte_identical(
    project: Project, tracker: InMemoryTracker
) -> None:
    before = git_state(project)
    assert run_shadow(project, tracker, FakeRuntime()).exit_code == 0
    assert git_state(project) == before
    assert sh(["git", "branch", "--list", "ariane/*"], project.root) == ""


def test_c19_shadow_clone_has_no_origin_and_holds_the_work(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert run_shadow(project, tracker, FakeRuntime()).exit_code == 0
    clone = shadow.clone_path(project.root, 7)
    assert clone == project.root.parent / "proj.ariane" / "shadow" / "7"
    assert sh(["git", "remote"], clone) == ""
    assert (clone / "app.txt").read_text(encoding="utf-8") == "version 2\n"
    assert (clone / "work/7/brief.md").is_file()


def test_c19_shadow_final_line_names_the_clone_and_the_judge_command(
    project: Project, tracker: InMemoryTracker
) -> None:
    outcome = run_shadow(project, tracker, FakeRuntime())
    clone = shadow.clone_path(project.root, 7)
    assert outcome.line == (
        f"Shadow ticket #7 done (delivered, review go). Next: read {clone}/work/7/,"
        " then run ariane judge 7 accept|reject --minutes N."
    )


def test_c19_shadow_existing_clone_stops_the_run(
    project: Project, tracker: InMemoryTracker
) -> None:
    shadow.clone_path(project.root, 7).mkdir(parents=True)
    runtime = FakeRuntime()
    outcome = run_shadow(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "remove it to start over" in outcome.line
    assert runtime.sessions == []


def test_c19_shadow_metrics_have_the_shadow_mode(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert run_shadow(project, tracker, FakeRuntime()).exit_code == 0
    clone = shadow.clone_path(project.root, 7)
    data = json.loads((clone / "work/7/metrics.json").read_text(encoding="utf-8"))
    assert data["mode"] == "shadow"
    assert data["outcome"] == "delivered"
    assert data["attempts"] == {"push": 0, "pull_request": 0, "guard_violations": 0}
