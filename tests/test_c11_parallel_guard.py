"""C11 (ADR 0017): two tickets at once on one repository. The push guard tolerates another
Ariane run's own branch and its two branch keys, and nothing else; the run registry says which
runs those are."""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from ariane import flow, git, runs
from ariane.runtime import Session
from ariane.stop import Stop
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, edit_app, sh
from test_flow import start


def _registry(project: Project) -> Path:
    return runs.folder(project.root)


def _second_run_branch(project: Project, number: int = 8) -> None:
    """What `ariane start <number>` does to the repository's git when it prepares its ticket."""
    tree = flow.worktree_path(project.root, number)
    sh(
        ["git", "worktree", "add", "--quiet", "-b", f"ariane/{number}", str(tree), "origin/main"],
        project.root,
    )


@contextlib.contextmanager
def _registered_during_session(
    project: Project, then: Callable[[Session], None], number: int = 8
) -> Iterator[FakeRuntime]:
    """A runtime whose implementer session registers run `number`, then applies `then`; the
    run stays registered until the block ends."""
    with contextlib.ExitStack() as stack:

        def action(session: Session) -> None:
            edit_app(session)
            stack.enter_context(runs.registered(_registry(project), number, f"ariane/{number}"))
            then(session)

        yield FakeRuntime(action=action)


def _shared_keys(project: Project) -> str:
    return sh(["git", "config", "--file", ".git/config", "--list"], project.root)


def test_c11_parallel_guard_a_registered_run_creating_its_branch_does_not_stop_the_first(
    project: Project, tracker: InMemoryTracker
) -> None:
    def second(session: Session) -> None:
        _second_run_branch(project)
        tree = flow.worktree_path(project.root, 8)
        (tree / "app.txt").write_text("version 8\n", encoding="utf-8")
        sh(["git", "commit", "--quiet", "-am", "ticket 8"], tree)  # the branch moves too

    with _registered_during_session(project, second) as runtime:
        outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 0, (outcome.line, outcome.detail)
    keys = _shared_keys(project)
    assert "branch.ariane/8.remote=origin" in keys and "branch.ariane/8.merge=" in keys


def test_c11_parallel_guard_a_whole_second_run_during_the_session_does_not_stop_the_first(
    project: Project, tracker: InMemoryTracker
) -> None:
    tracker.add_issue(8, "Bump the app version again", "Set app.txt to version 2 as well.")
    inner: list[flow.Outcome] = []

    def run_ticket_8(session: Session) -> None:
        edit_app(session)
        inner.append(start(project, tracker, FakeRuntime(), number=8))

    outcome = start(project, tracker, FakeRuntime(action=run_ticket_8))
    assert inner and inner[0].exit_code == 0, inner[0].line
    # Ticket 8 started and ended inside the session: no longer registered, it is in the history.
    assert runs.running(_registry(project)) == {}
    assert outcome.exit_code == 0, (outcome.line, outcome.detail)


def test_c11_parallel_guard_the_same_keys_for_a_ticket_not_registered_stop_the_run(
    project: Project, tracker: InMemoryTracker
) -> None:
    def second(session: Session) -> None:
        edit_app(session)
        _second_run_branch(project)

    outcome = start(project, tracker, FakeRuntime(action=second))
    assert outcome.exit_code == 1
    assert "the agent session changed git configuration, hooks or local branches" in outcome.line
    assert "branch.ariane/8.remote=origin" in outcome.detail
    assert "added: ref refs/heads/ariane/8" in outcome.detail
    assert tracker.opened == []


@pytest.mark.parametrize("key", ["pushRemote", "rebase"])
def test_c11_parallel_guard_another_key_of_that_section_stops_even_for_a_registered_run(
    project: Project, tracker: InMemoryTracker, key: str
) -> None:
    def second(session: Session) -> None:
        _second_run_branch(project)
        sh(["git", "config", f"branch.ariane/8.{key}", "origin"], project.root)

    with _registered_during_session(project, second) as runtime:
        outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "changed git configuration, hooks or local branches" in outcome.line
    assert f"branch.ariane/8.{key.lower()}=origin" in outcome.detail
    assert tracker.opened == []


def test_c11_parallel_guard_a_hook_added_stops_with_another_run_registered(
    project: Project, tracker: InMemoryTracker
) -> None:
    def second(session: Session) -> None:
        _second_run_branch(project)
        hook = project.root / ".git" / "hooks" / "pre-push"
        hook.parent.mkdir(exist_ok=True)
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    with _registered_during_session(project, second) as runtime:
        outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "changed git configuration, hooks or local branches" in outcome.line
    # Only what is not the other run's own is named.
    assert "hooks/pre-push" in outcome.detail
    assert "ariane/8" not in outcome.detail


def test_c11_parallel_guard_the_registry_entry_is_removed_when_a_run_ends_normally(
    project: Project, tracker: InMemoryTracker
) -> None:
    seen: list[dict[int, runs.Run]] = []

    def look(session: Session) -> None:
        edit_app(session)
        seen.append(runs.running(_registry(project)))

    assert start(project, tracker, FakeRuntime(action=look)).exit_code == 0
    assert seen[0][7].pid == os.getpid() and seen[0][7].branch == "ariane/7"
    assert not (_registry(project) / "7").exists()
    ended = (_registry(project) / runs.ENDED).read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["number"] for line in ended] == [7]


def test_c11_parallel_guard_the_registry_entry_is_removed_when_a_run_stops_or_raises(
    project: Project, tracker: InMemoryTracker
) -> None:
    def nothing(session: Session) -> None:
        assert (_registry(project) / "7").exists()

    assert start(project, tracker, FakeRuntime(action=nothing)).exit_code == 1  # changed no file
    assert not (_registry(project) / "7").exists()

    tracker.add_issue(8, "Crash", "The runtime fails.")

    def crash(session: Session) -> None:
        raise RuntimeError("runtime crashed")

    with pytest.raises(RuntimeError):
        start(project, tracker, FakeRuntime(action=crash), number=8)
    assert runs.running(_registry(project)) == {}
    assert sorted(p.name for p in _registry(project).iterdir()) == [runs.LOCK, runs.ENDED]


def _dead_pid() -> int:
    done = subprocess.run(
        [sys.executable, "-c", "import os; print(os.getpid())"],
        capture_output=True,
        text=True,
        check=True,
    )
    return int(done.stdout)


def _write_entry(where: Path, number: int, pid: int) -> None:
    where.mkdir(parents=True, exist_ok=True)
    entry = {"number": number, "branch": f"ariane/{number}", "pid": pid, "started": runs.now()}
    (where / str(number)).write_text(json.dumps(entry), encoding="utf-8")


def test_c11_parallel_guard_a_stale_entry_is_ignored_and_cleaned(
    project: Project, tracker: InMemoryTracker
) -> None:
    where = _registry(project)
    _write_entry(where, 9, _dead_pid())
    _write_entry(where, 7, _dead_pid())  # a crashed run of the same ticket: replaced

    def second(session: Session) -> None:
        edit_app(session)
        _second_run_branch(project, 9)

    outcome = start(project, tracker, FakeRuntime(action=second))
    assert outcome.exit_code == 1  # ticket 9's run is dead: its branch is not tolerated
    assert "added: ref refs/heads/ariane/9" in outcome.detail
    assert not (where / "9").exists() and not (where / "7").exists()


def test_c11_parallel_guard_a_live_run_of_the_same_ticket_is_refused(
    project: Project, tracker: InMemoryTracker
) -> None:
    _write_entry(_registry(project), 7, os.getpid())
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == 1
    assert f"ticket #7 is already running (process {os.getpid()})" in outcome.line
    assert (_registry(project) / "7").exists()  # the other run's entry stays
    assert not flow.worktree_path(project.root, 7).exists()


def test_c11_parallel_guard_registered_refuses_a_live_entry(tmp_path: Path) -> None:
    with (
        runs.registered(tmp_path, 5, "ariane/5"),
        pytest.raises(Stop),
        runs.registered(tmp_path, 5, "ariane/5"),
    ):
        pass
    assert not (tmp_path / "5").exists()


def test_c11_parallel_guard_during_keeps_runs_that_ended_since_the_snapshot(
    tmp_path: Path,
) -> None:
    with runs.registered(tmp_path, 3, "ariane/3"):
        pass
    time.sleep(0.01)  # the clock moves on: run 3 ended strictly before `since`
    since = runs.now()
    with runs.registered(tmp_path, 4, "ariane/4"):
        pass
    with runs.registered(tmp_path, 5, "ariane/5"):
        assert runs.during(tmp_path, since) == {4, 5}


def _snapshot(project: Project) -> dict[str, str]:
    return git.config_snapshot(project.root, ignore_ref="main")


def test_c11_parallel_guard_compares_the_shared_config_by_key(project: Project) -> None:
    before = _snapshot(project)
    sh(["git", "config", "branch.ariane/8.remote", "origin"], project.root)
    sh(["git", "config", "branch.ariane/8.merge", "refs/heads/ariane/8"], project.root)
    after = _snapshot(project)
    assert git.snapshot_changes(before, after)
    assert runs.foreign_changes(before, after, {8}, "main") == []
    assert runs.foreign_changes(before, after, {9}, "main") != []
    # The same keys removed again (the other run's branch deleted) are tolerated as well.
    sh(["git", "branch", "--quiet", "ariane/8", "main"], project.root)
    sh(["git", "branch", "--quiet", "-D", "ariane/8"], project.root)
    assert runs.foreign_changes(after, _snapshot(project), {8}, "main") == []


def test_c11_parallel_guard_a_wrong_value_or_a_bare_edit_is_not_tolerated(
    project: Project,
) -> None:
    before = _snapshot(project)
    sh(["git", "config", "branch.ariane/8.remote", "elsewhere"], project.root)
    assert any(
        "ariane/8.remote=elsewhere" in c
        for c in runs.foreign_changes(before, _snapshot(project), {8}, "main")
    )
    before = _snapshot(project)
    with (project.root / ".git" / "config").open("a", encoding="utf-8") as config:
        config.write("# a comment changes the file, not its keys\n")
    changes = runs.foreign_changes(before, _snapshot(project), {8}, "main")
    assert [c for c in changes if c.startswith("changed: file ")]


def test_c11_parallel_guard_reads_git_before_the_runs_that_authorize_it(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run 8 registers and creates its branch right after the first run reads the registry:
    the guard's git snapshot must not see changes newer than the registrations it uses."""
    real_during = runs.during
    stack, started = contextlib.ExitStack(), list[int]()

    def during(where: Path, since: str) -> set[int]:
        numbers = real_during(where, since)
        if not started:  # once: the other run starts just after this read
            started.append(8)
            stack.enter_context(runs.registered(_registry(project), 8, "ariane/8"))
            _second_run_branch(project)
        return numbers

    monkeypatch.setattr(runs, "during", during)
    with stack:
        outcome = start(project, tracker, FakeRuntime(action=edit_app))
    assert outcome.exit_code == 0, (outcome.line, outcome.detail)


def test_c11_parallel_guard_a_run_ending_is_always_in_the_registry_or_its_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    since = runs.now()
    seen: list[set[int]] = []
    real_release = runs._release

    def release(entry: Path, run: runs.Run) -> None:  # a reader between the two writes
        seen.append(set(runs._live(tmp_path)) | runs._ended(tmp_path, since))
        real_release(entry, run)

    monkeypatch.setattr(runs, "_release", release)
    with runs.registered(tmp_path, 3, "ariane/3"):
        pass
    assert seen == [{3}]
    assert runs.during(tmp_path, since) == {3}
    assert not (tmp_path / "3").exists()


def test_c11_parallel_guard_a_run_never_removes_an_entry_that_is_not_its_own(
    tmp_path: Path,
) -> None:
    with runs.registered(tmp_path, 3, "ariane/3"):
        _write_entry(tmp_path, 3, os.getpid())  # replaced meanwhile: another run's entry
        other = (tmp_path / "3").read_text(encoding="utf-8")
    assert (tmp_path / "3").read_text(encoding="utf-8") == other


class _Paused:
    """`runs.alive` pausing its first call for `pid` until `go` is set."""

    def __init__(self, pid: int) -> None:
        self.pid, self.inside, self.go = pid, threading.Event(), threading.Event()
        self.real = runs.alive

    def __call__(self, pid: int) -> bool:
        if pid == self.pid and not self.inside.is_set():
            self.inside.set()
            assert self.go.wait(10)
        return self.real(pid)


def _hold(
    where: Path, number: int, held: threading.Event, leave: threading.Event, results: list[object]
) -> None:
    try:
        with runs.registered(where, number, f"ariane/{number}") as run:
            results.append(run)
            held.set()
            assert leave.wait(10)
    except Stop as stop:
        results.append(stop)
        held.set()


def test_c11_parallel_guard_two_starters_reclaiming_one_stale_entry_admit_one_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_entry(tmp_path, 3, dead := _dead_pid())
    paused = _Paused(dead)
    monkeypatch.setattr(runs, "alive", paused)
    leave, results = threading.Event(), list[object]()
    held = [threading.Event(), threading.Event()]
    first = threading.Thread(target=_hold, args=(tmp_path, 3, held[0], leave, results))
    first.start()
    assert paused.inside.wait(10)  # the first starter read the stale entry
    second = threading.Thread(target=_hold, args=(tmp_path, 3, held[1], leave, results))
    second.start()
    time.sleep(0.2)
    paused.go.set()
    assert held[0].wait(10) and held[1].wait(10)
    admitted = [r for r in results if isinstance(r, runs.Run)]
    assert len(admitted) == 1 and len(results) == 2
    assert runs.running(tmp_path) == {3: admitted[0]}
    leave.set()
    first.join(10)
    second.join(10)
    assert not (tmp_path / "3").exists()


def test_c11_parallel_guard_cleaning_a_stale_entry_never_erases_a_new_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_entry(tmp_path, 3, dead := _dead_pid())
    paused = _Paused(dead)
    monkeypatch.setattr(runs, "alive", paused)
    found: list[dict[int, runs.Run]] = []
    reader = threading.Thread(target=lambda: found.append(runs.running(tmp_path)))
    reader.start()
    assert paused.inside.wait(10)  # the reader judged the old entry stale
    held, leave, results = threading.Event(), threading.Event(), list[object]()
    starter = threading.Thread(target=_hold, args=(tmp_path, 3, held, leave, results))
    starter.start()
    time.sleep(0.2)
    paused.go.set()
    reader.join(10)
    assert held.wait(10)
    assert found == [{}]
    assert isinstance(results[0], runs.Run)
    assert runs.running(tmp_path) == {3: results[0]}
    leave.set()
    starter.join(10)
