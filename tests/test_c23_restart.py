"""`ariane start <n> --restart`: a stopped or interrupted ticket starts over, its previous branch
kept, never while another process runs it (C5, C19, C23, ADR 0047)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from ariane import flow, git, report, restart
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import PY, FakeRuntime, Project, make_config, sh
from test_flow import environ, worktree

HOLD = """
import sys
from pathlib import Path
from ariane.restart import locked
with locked(Path(sys.argv[1]), 7):
    print("held", flush=True)
    sys.stdin.read()
"""


def start(
    project: Project, tracker: InMemoryTracker, runtime: FakeRuntime, *, restarting: bool = False
) -> flow.Outcome:
    return flow.start(
        7,
        repo_root=project.root,
        config=make_config(),
        tracker=tracker,
        runtime=runtime,
        environ=environ(),
        restarting=restarting,
    )


def nothing(session: Session) -> None:
    """An implementer session that changes no file: the ticket stops."""


def kept_branches(project: Project) -> list[str]:
    listing = sh(["git", "branch", "--list", "--format=%(refname:short)", "ariane-*"], project.root)
    return listing.split()


def worktrees(project: Project) -> list[str]:
    listing = sh(["git", "worktree", "list", "--porcelain"], project.root)
    lines = listing.splitlines()
    return [
        Path(line.removeprefix("worktree ")).name for line in lines if line.startswith("worktree ")
    ]


def leave_killed_run(project: Project) -> str:
    """What a run killed during its review leaves: its tree and branch, a replay and a reviewer
    tree. Returns the branch's head."""
    tree = worktree(project)
    git.add_worktree(project.root, tree, "ariane/7", "origin/main")
    head = git.head(tree)
    for name in ("7-replay-1", "7-review"):
        git.add_detached_worktree(project.root, tree.with_name(name), head)
    return head


@pytest.fixture
def holder(project: Project) -> Iterator[subprocess.Popen[str]]:
    """Another process holding ticket 7's lock, as a live `ariane start 7` does."""
    child = subprocess.Popen(
        [PY, "-c", HOLD, str(restart.lock_path(project.root, 7))],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert child.stdout is not None and child.stdout.readline().strip() == "held"
    yield child
    child.kill()
    child.wait()


def test_c23_restart_after_a_stop_start_refuses_and_restart_keeps_the_branch_and_delivers(
    project: Project, tracker: InMemoryTracker
) -> None:
    stopped = start(project, tracker, FakeRuntime(action=nothing))
    assert stopped.exit_code == 1
    assert "the agent changed no file" in stopped.line
    assert "run `ariane start 7 --restart`" in stopped.line
    old_head = sh(["git", "rev-parse", "ariane/7"], project.root)

    refused = start(project, tracker, FakeRuntime())
    assert refused.exit_code == 1
    assert "Did not start ticket #7" in refused.line
    assert "Next: run `ariane start 7 --restart`." in refused.line

    done = start(project, tracker, FakeRuntime(), restarting=True)
    assert done.exit_code == 0, done.line
    [kept] = kept_branches(project)
    assert kept.startswith("ariane-restarted/7-") and kept.endswith("Z")
    assert sh(["git", "rev-parse", kept], project.root) == old_head
    journal = project.show("ariane/7", "work/7/journal.md")
    assert journal.index("Ticket started over") < journal.index("Ticket started\n")
    assert f"Previous branch kept as `{kept}` at `{old_head}`." in journal
    assert "Previous run's last action: stopped (the agent changed no file)" in journal
    assert f"`{worktree(project)}`" in journal
    data = json.loads(project.show("ariane/7", "work/7/metrics.json"))
    assert data["restarted_from"]["branch"] == kept
    previous = json.loads(sh(["git", "show", f"{kept}:work/7/metrics.json"], project.root))
    assert data["restarted_from"]["stopped_at"] == previous["steps"][-1]["at"]


def test_c23_restart_removes_the_replay_and_review_trees_of_a_killed_run(
    project: Project, tracker: InMemoryTracker
) -> None:
    head = leave_killed_run(project)
    refused = start(project, tracker, FakeRuntime())
    assert "already exists" in refused.line and "--restart" in refused.line

    done = start(project, tracker, FakeRuntime(), restarting=True)
    assert done.exit_code == 0, done.line
    assert not worktree(project).with_name("7-replay-1").exists()
    assert not worktree(project).with_name("7-review").exists()
    assert "7-replay-1" not in worktrees(project) and "7-review" not in worktrees(project)
    [kept] = kept_branches(project)
    assert sh(["git", "rev-parse", kept], project.root) == head
    journal = project.show("ariane/7", "work/7/journal.md")
    assert "7-replay-1`" in journal and "7-review`" in journal
    assert "Previous run's last action: unknown" in journal
    data = json.loads(project.show("ariane/7", "work/7/metrics.json"))
    assert data["restarted_from"] == {"branch": kept}  # no readable metrics: no stopped_at


@pytest.mark.parametrize("restarting", [False, True])
def test_c23_restart_refused_while_another_process_holds_the_lock(
    project: Project,
    tracker: InMemoryTracker,
    holder: subprocess.Popen[str],
    restarting: bool,
) -> None:
    head = leave_killed_run(project)
    runtime = FakeRuntime()
    outcome = start(project, tracker, runtime, restarting=restarting)
    assert outcome.exit_code == 1
    assert "ticket #7 is running in another Ariane process" in outcome.line
    assert "--restart" not in outcome.line
    assert runtime.sessions == []
    for name in ("7", "7-replay-1", "7-review"):
        assert worktree(project).with_name(name).is_dir()
    assert sh(["git", "rev-parse", "ariane/7"], project.root) == head
    assert kept_branches(project) == []


def test_c23_restart_lock_is_free_once_the_holder_died(
    project: Project, tracker: InMemoryTracker, holder: subprocess.Popen[str]
) -> None:
    holder.kill()
    holder.wait()
    assert start(project, tracker, FakeRuntime(), restarting=True).exit_code == 0


def test_c23_restart_refused_when_the_branch_is_on_the_remote(
    project: Project, tracker: InMemoryTracker
) -> None:
    leave_killed_run(project)
    sh(["git", "push", "--quiet", "origin", "ariane/7"], project.root)
    outcome = start(project, tracker, FakeRuntime(), restarting=True)
    assert outcome.exit_code == 1
    assert "branch ariane/7 already exists on origin" in outcome.line
    assert worktree(project).with_name("7-review").is_dir()
    assert kept_branches(project) == []


def test_c23_restart_without_anything_to_remove_is_a_plain_start(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert start(project, tracker, FakeRuntime(), restarting=True).exit_code == 0
    assert "Ticket started over" not in project.show("ariane/7", "work/7/journal.md")
    assert "restarted_from" not in json.loads(project.show("ariane/7", "work/7/metrics.json"))
    assert kept_branches(project) == []


def test_c23_restart_with_shadow_is_refused(project: Project) -> None:
    done = subprocess.run(
        [PY, "-m", "ariane", "start", "7", "--restart", "--shadow"],
        cwd=project.root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 2
    line = done.stdout.strip()
    assert "--restart does not apply to shadow tickets" in line
    assert "remove the clone" in line


def test_c23_restart_an_interrupt_names_restart(project: Project, tracker: InMemoryTracker) -> None:
    def interrupt(session: Session) -> None:
        raise KeyboardInterrupt

    outcome = start(project, tracker, FakeRuntime(action=interrupt))
    assert outcome.exit_code == 130
    assert "Next: check the working tree; to start over, run `ariane start 7 --restart`." in (
        outcome.line
    )


def test_c23_restart_a_tree_left_during_the_run_names_restart_once(
    project: Project, tracker: InMemoryTracker
) -> None:
    def leave_replay(session: Session) -> None:
        (session.cwd.parent / "7-replay-1").mkdir()
        (session.cwd / "app.txt").write_text("version 2\n", encoding="utf-8")

    outcome = start(project, tracker, FakeRuntime(action=leave_replay))
    assert "the replay working tree already exists" in outcome.line
    assert outcome.line.count("--restart") == 1


def test_c23_restart_report_counts_the_time_from_the_previous_stop(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    path = root / "work/7/metrics.json"
    path.parent.mkdir(parents=True)
    data = {
        "ticket": 7,
        "mode": "delivered",
        "started": "2026-10-01T10:30:00Z",
        "sessions": [],
        "rounds": 0,
        "first_pass_verdict": "go",
        "outcome": "delivered",
        "restarted_from": {"branch": "ariane-restarted/7-x", "stopped_at": "2026-10-01T09:15:00Z"},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    assert "restarts 1h15m" in "\n".join(report.build(root, None).lines)
