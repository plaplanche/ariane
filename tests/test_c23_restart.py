"""`ariane start <n> --restart`: a stopped or interrupted ticket starts over, its previous branch
kept, never while another process runs it (C5, C19, C23, ADR 0047)."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path

import pytest

from ariane import flow, git, report, restart, runs
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import PY, FakeRuntime, Project, edit_app, make_config, sh
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

    # The folder is not a registered working tree: the recommended restart still clears it.
    done = start(project, tracker, FakeRuntime(), restarting=True)
    assert done.exit_code == 0, done.line
    assert not worktree(project).with_name("7-replay-1").exists()
    assert "7-replay-1`" in project.show("ariane/7", "work/7/journal.md")


def test_c23_restart_another_ticket_restarting_meanwhile_does_not_stop_this_one(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ticket 8 restarts during ticket 7's session: its kept branch is its own bookkeeping."""
    monkeypatch.setattr(runs, "_started_as", lambda pid, number: True)  # runs in this process
    monkeypatch.setattr(runs, "WATCH_SECONDS", 0.01)
    tracker.add_issue(8, "Bump the app version again", "Set app.txt to version 2 as well.")
    tree = flow.worktree_path(project.root, 8)
    git.add_worktree(project.root, tree, "ariane/8", "origin/main")  # ticket 8's stopped run
    inner: list[flow.Outcome] = []

    def restart_ticket_8(session: Session) -> None:
        edit_app(session)
        inner.append(
            flow.start(
                8,
                repo_root=project.root,
                config=make_config(),
                tracker=tracker,
                runtime=FakeRuntime(),
                environ=environ(),
                restarting=True,
            )
        )

    outcome = start(project, tracker, FakeRuntime(action=restart_ticket_8))
    assert inner and inner[0].exit_code == 0, inner[0].line
    assert [b for b in kept_branches(project) if b.startswith("ariane-restarted/8-")]
    assert outcome.exit_code == 0, (outcome.line, outcome.detail)


def test_c23_restart_a_kept_branch_counts_only_when_its_run_registered_it(
    project: Project,
) -> None:
    before = git.config_snapshot(project.root, ignore_ref="refs/heads/ariane/7")
    sh(["git", "branch", "ariane-restarted/8-20261018T000000Z"], project.root)
    after = git.config_snapshot(project.root, ignore_ref="refs/heads/ariane/7")
    assert runs.foreign_changes(before, after, {8}, {"ariane-restarted/8-20261018T000000Z"}) == []
    assert runs.foreign_changes(before, after, {8}), "unregistered: still a change"
    assert runs.foreign_changes(before, after, {8}, {"ariane-restarted/8-20261018T000001Z"})


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


def kept_file(project: Project, kept: str, path: str) -> str:
    return sh(["git", "show", f"{kept}:{path}"], project.root)


def test_c23_restart_keeps_the_uncommitted_work_of_a_killed_run(
    project: Project, tracker: InMemoryTracker
) -> None:
    """A run killed during the implementer session, before Ariane committed: the modified and
    the untracked files exist only in its tree, and the kept branch holds them."""
    head = leave_killed_run(project)
    tree = worktree(project)
    (tree / "app.txt").write_text("version 2\n", encoding="utf-8")
    (tree / "notes").mkdir()
    (tree / "notes" / "new.txt").write_text("untracked work\n", encoding="utf-8")

    done = start(project, tracker, FakeRuntime(), restarting=True)
    assert done.exit_code == 0, done.line
    [kept] = kept_branches(project)
    saved = sh(["git", "rev-parse", kept], project.root)
    assert saved != head
    assert sh(["git", "rev-parse", f"{kept}^"], project.root) == head
    assert kept_file(project, kept, "app.txt") == "version 2"
    assert kept_file(project, kept, "notes/new.txt") == "untracked work"
    journal = project.show("ariane/7", "work/7/journal.md")
    assert f"saved in commit `{saved}`" in journal


def test_c23_restart_keeps_the_work_of_an_interrupted_session(
    project: Project, tracker: InMemoryTracker
) -> None:
    def edit_then_interrupt(session: Session) -> None:
        (session.cwd / "app.txt").write_text("version 2\n", encoding="utf-8")
        (session.cwd / "draft.txt").write_text("half done\n", encoding="utf-8")
        raise KeyboardInterrupt

    assert start(project, tracker, FakeRuntime(action=edit_then_interrupt)).exit_code == 130
    assert start(project, tracker, FakeRuntime(), restarting=True).exit_code == 0
    [kept] = kept_branches(project)
    assert kept_file(project, kept, "app.txt") == "version 2"
    assert kept_file(project, kept, "draft.txt") == "half done"


def test_c23_restart_keeps_commits_of_a_tree_detached_from_its_branch(
    project: Project, tracker: InMemoryTracker
) -> None:
    head = leave_killed_run(project)
    tree = worktree(project)
    sh(["git", "checkout", "--quiet", "--detach"], tree)
    (tree / "app.txt").write_text("version 3\n", encoding="utf-8")
    sh(["git", "commit", "--quiet", "-am", "off the branch"], tree)
    detached = git.head(tree)

    assert start(project, tracker, FakeRuntime(), restarting=True).exit_code == 0
    [kept] = kept_branches(project)
    parents = sh(["git", "rev-list", "--parents", "-n", "1", kept], project.root).split()[1:]
    assert parents == [head, detached]
    assert kept_file(project, kept, "app.txt") == "version 3"


def test_c23_restart_a_forged_kept_branch_of_a_live_run_is_never_exempt(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ticket 8 is genuinely running; ticket 7's agent rewrites its entry to exempt `main`."""
    monkeypatch.setattr(runs, "_started_as", lambda pid, number: True)  # runs in this process
    where = runs.folder(project.root)
    where.mkdir(parents=True)
    genuine = runs.Run(8, "ariane/8", os.getpid(), runs.now())
    entry = where / "8"
    entry.write_text(json.dumps(asdict(genuine)), encoding="utf-8")
    witnessed: dict[int, runs.Run] = {}
    assert runs.during(where, runs.now(), witnessed) == {8}

    before = git.config_snapshot(project.root, ignore_ref="refs/heads/ariane/7")
    forged = {**asdict(genuine), "kept": "main"}
    entry.write_text(json.dumps(forged), encoding="utf-8")
    sh(["git", "commit", "--quiet", "--allow-empty", "-m", "moved main"], project.root)
    assert runs.during(where, runs.now(), witnessed) == {8}
    assert witnessed[8] == genuine  # the rewrite is not the run's
    after = git.config_snapshot(project.root, ignore_ref="refs/heads/ariane/7")
    exempt = runs.kept_branches(witnessed, {8})
    assert runs.foreign_changes(before, after, {8}, exempt), "main moved: a change"

    # Forged from the start: only a name a restart of that ticket chose when it started counts.
    started = "2026-10-18T10:00:05.000000+00:00"
    for name in ("main", "ariane-restarted/9-20261018T100000Z", "ariane-restarted/8-x"):
        assert runs.kept_branches({8: runs.Run(8, "ariane/8", 1, started, name)}, {8}) == set()
    late = "ariane-restarted/8-20261018T100010Z"  # after the run started
    old = "ariane-restarted/8-20261018T090000Z"  # an earlier restart's branch
    assert runs.kept_branches({8: runs.Run(8, "ariane/8", 1, started, late)}, {8}) == set()
    assert runs.kept_branches({8: runs.Run(8, "ariane/8", 1, started, old)}, {8}) == set()
    own = "ariane-restarted/8-20261018T100004Z"
    assert runs.kept_branches({8: runs.Run(8, "ariane/8", 1, started, own)}, {8}) == {own}


def test_c23_restart_keeps_staged_work_that_differs_from_the_files(
    project: Project, tracker: InMemoryTracker
) -> None:
    """Version 2 staged, then version 1 restored in the file only: both versions are kept, the
    staged one in a commit of its own below the files' one."""
    head = leave_killed_run(project)
    tree = worktree(project)
    (tree / "app.txt").write_text("version 2\n", encoding="utf-8")
    sh(["git", "add", "app.txt"], tree)
    (tree / "app.txt").write_text("version 1\n", encoding="utf-8")

    assert start(project, tracker, FakeRuntime(), restarting=True).exit_code == 0
    [kept] = kept_branches(project)
    assert kept_file(project, kept, "app.txt") == "version 1"
    assert kept_file(project, f"{kept}^", "app.txt") == "version 2"
    assert sh(["git", "rev-parse", f"{kept}^^"], project.root) == head


def test_c23_restart_the_saved_work_is_reachable_before_any_tree_is_removed(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A restart that dies while removing the trees has already written the kept branch."""
    head = leave_killed_run(project)
    tree = worktree(project)
    (tree / "app.txt").write_text("version 2\n", encoding="utf-8")

    def killed(*args: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(restart, "_remove_tree", killed)
    kept = "ariane-restarted/7-20261018T000000Z"
    with pytest.raises(KeyboardInterrupt):
        restart.clear(project.root, tree, 7, "ariane/7", kept)
    assert kept_file(project, kept, "app.txt") == "version 2"
    assert sh(["git", "rev-parse", f"{kept}^"], project.root) == head
    assert tree.is_dir()


def test_c23_restart_an_existing_kept_name_stops_before_removing_anything(
    project: Project,
) -> None:
    head = leave_killed_run(project)
    tree = worktree(project)
    kept = "ariane-restarted/7-20261018T000000Z"
    sh(["git", "branch", kept, "main"], project.root)
    with pytest.raises(git.GitError):
        restart.clear(project.root, tree, 7, "ariane/7", kept)
    for name in ("7", "7-replay-1", "7-review"):
        assert tree.with_name(name).is_dir()
    assert sh(["git", "rev-parse", "ariane/7"], project.root) == head
    assert sh(["git", "rev-parse", kept], project.root) == sh(
        ["git", "rev-parse", "main"], project.root
    )


def test_c23_restart_refuses_an_unregistered_ticket_folder_that_holds_files(
    project: Project, tracker: InMemoryTracker
) -> None:
    """A folder at the ticket's tree path that git does not know holds files: a restart can
    neither save them nor delete them, so it stops and leaves the folder as it is."""
    tree = worktree(project)
    tree.mkdir(parents=True)
    (tree / "app.txt").write_text("work git does not know\n", encoding="utf-8")

    outcome = start(project, tracker, FakeRuntime(), restarting=True)
    assert outcome.exit_code == 1
    assert "is not registered with git and holds files" in outcome.line
    assert "--restart" in outcome.line
    assert (tree / "app.txt").read_text(encoding="utf-8") == "work git does not know\n"
    assert kept_branches(project) == []
