"""C9: with `project.parallel_checks` above 1, independent checks are replayed at the same time,
each in its own tree and run slot (ADR 0052)."""

from __future__ import annotations

import _thread
import dataclasses
import json
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from test_config import VALID, with_change

from ariane import checks, config, process, replay, slots, verify
from ariane.config import CheckConfig, Config
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, make_config, sh
from test_flow import environ, journal, start, worktree

PY = sys.executable
# Sleeps argv[2] seconds, then records the slot it was given and when it ran in its own
# `<argv[1]>.<pid>`: no two checks write to one file.
RECORD = """
import json, os, sys, time
began = time.time()
time.sleep(float(sys.argv[2]))
with open(f"{sys.argv[1]}.{os.getpid()}", "w", encoding="utf-8") as out:
    out.write(json.dumps({"slot": os.environ.get("ARIANE_SLOT"), "began": began,
                          "ended": time.time()}) + "\\n")
"""
# Writes argv[1] once started, sleeps argv[3] seconds, then writes argv[2].
SLOW = """
import pathlib, sys, time
pathlib.Path(sys.argv[1]).write_text("started")
time.sleep(float(sys.argv[3]))
pathlib.Path(sys.argv[2]).write_text("finished")
"""


def parallel(config_: Config, count: int) -> Config:
    return dataclasses.replace(config_, parallel_checks=count)


def recording(out: Path, *seconds: float) -> tuple[CheckConfig, ...]:
    return tuple(
        CheckConfig(f"check {k}", (PY, "-c", RECORD, str(out), str(s)), True, 1)
        for k, s in enumerate(seconds, 1)
    )


def records(out: Path) -> list[dict[str, Any]]:
    """The record of each check, one `<out>.<pid>` file each, sorted by name."""
    files = sorted(out.parent.glob(f"{out.name}.*"), key=lambda p: p.name)
    return [json.loads(p.read_text(encoding="utf-8")) for p in files]


def trees(project: Project) -> str:
    return sh(["git", "worktree", "list"], project.root)


@pytest.mark.parametrize(("workers", "fast"), [((0, 1, 2), True), ((), False)])
def test_c9_parallel_checks_three_one_second_checks_take_one_second_at_three_at_a_time(
    tmp_path: Path, workers: tuple[int, ...], fast: bool
) -> None:
    """The replay itself, without git: its trees are plain folders (the guard is not timed)."""
    sleep = (PY, "-c", "import time; time.sleep(1)")
    all_checks = [CheckConfig(f"sleep {k}", sleep, True, 1) for k in (1, 2, 3)]
    made: list[replay.ReplayTree] = []
    began = time.monotonic()
    results = replay.replay_each(
        all_checks,
        lambda k: tmp_path / f"tree-{k}",
        create=lambda tree: tree.mkdir(),
        setup=lambda check, tree, env: "",
        verify=lambda tree: None,
        remove=shutil.rmtree,
        env=None,
        trees=made,
        slots=workers,
    )
    spent = time.monotonic() - began
    assert [r.passed for r in results] == [True, True, True]
    assert not list(tmp_path.iterdir())
    if fast:
        assert spent < 2.5, spent
    else:
        assert spent >= 3, spent


def test_c9_parallel_checks_flow_with_three_takes_less_than_one_by_one(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    spent: list[float] = []
    real = replay.replay

    def timed(*args: Any) -> list[checks.CheckResult]:
        began = time.monotonic()
        try:
            return real(*args)
        finally:
            spent.append(time.monotonic() - began)

    monkeypatch.setattr(replay, "replay", timed)
    for number, count in ((7, 1), (8, 3)):
        if number != 7:  # the fixture's issue
            tracker.add_issue(number, f"Ticket {number}", "Body.")
        config_ = parallel(make_config(checks=recording(tmp_path / f"{number}", 1, 1, 1)), count)
        outcome = start(project, tracker, FakeRuntime(), config_, number=number)
        assert outcome.exit_code == 0, outcome.line
    assert spent[0] >= 3
    assert spent[1] < spent[0] - 1.5, spent


def test_c9_parallel_checks_each_recording_check_writes_its_own_file(tmp_path: Path) -> None:
    out = tmp_path / "out"
    running = [subprocess.Popen(list(c.command)) for c in recording(out, 0.5, 0.5, 0.5)]
    assert [p.wait(timeout=30) for p in running] == [0, 0, 0]
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == sorted(f"out.{p.pid}" for p in running)
    assert not out.exists()
    assert len(records(out)) == 3


def test_c9_parallel_checks_report_keeps_the_declared_order(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    # The first declared check finishes last.
    config_ = parallel(make_config(checks=recording(out, 1.5, 0.8, 0)), 3)
    assert start(project, tracker, FakeRuntime(), config_).exit_code == 0
    assert len(records(out)) == 3
    report = (worktree(project) / "work/7/checks.md").read_text(encoding="utf-8")
    sections = [report.index(f"## check {k}\n") for k in (1, 2, 3)]
    assert sections == sorted(sections)
    rows = [name for name, _, _ in checks.parse_summary_table(report)]
    assert rows == ["check 1", "check 2", "check 3"]
    worktrees = journal(project).split("Checks working trees", 1)[1]
    assert worktrees.index("check 1") < worktrees.index("check 2") < worktrees.index("check 3")


def test_c9_parallel_checks_running_at_once_see_different_slots(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    config_ = parallel(make_config(checks=recording(out, 1, 1, 1)), 3)
    assert start(project, tracker, FakeRuntime(), config_).exit_code == 0
    seen = records(out)
    assert max(r["began"] for r in seen) < min(r["ended"] for r in seen)  # all ran at once
    assert len({r["slot"] for r in seen}) == 3
    assert None not in {r["slot"] for r in seen}
    assert "Checks replayed 3 at a time" in journal(project)


@pytest.mark.parametrize("how", ["raised in a worker", "ctrl-c in the main thread"])
def test_c9_parallel_checks_interrupt_leaves_no_process_and_no_tree(
    project: Project,
    tracker: InMemoryTracker,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    how: str,
) -> None:
    slow = [
        CheckConfig(
            f"slow {k}",
            (PY, "-c", SLOW, str(tmp_path / f"started-{k}"), str(tmp_path / f"done-{k}"), "6"),
            True,
            1,
        )
        for k in (1, 2)
    ]
    trigger = CheckConfig("trigger", (PY, "-c", "import time; time.sleep(30)"), True, 1)
    real = checks.run_check
    interrupted: list[float] = []

    def interrupt(check: CheckConfig, cwd: Path, env: Any = None) -> checks.CheckResult:
        if check.name != "trigger":
            return real(check, cwd, env)
        deadline = time.monotonic() + 60
        while not all((tmp_path / f"started-{k}").exists() for k in (1, 2)):
            assert time.monotonic() < deadline
            time.sleep(0.05)
        interrupted.append(time.monotonic())
        if how == "raised in a worker":
            raise KeyboardInterrupt
        _thread.interrupt_main()
        return real(check, cwd, env)  # killed with the others, or refused

    monkeypatch.setattr(checks, "run_check", interrupt)
    config_ = parallel(make_config(checks=(*slow, trigger)), 3)
    outcome = start(project, tracker, FakeRuntime(), config_)
    assert outcome.exit_code == 130, outcome.line
    assert time.monotonic() - interrupted[0] < 5  # the slow checks were killed, not waited for
    assert "-replay-" not in trees(project)
    assert not list(worktree(project).parent.glob("7-replay-*"))
    time.sleep(max(0.0, interrupted[0] + 7 - time.monotonic()))
    assert not any((tmp_path / f"done-{k}").exists() for k in (1, 2))


def test_c9_parallel_checks_setup_failure_stops_the_others(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    slow = CheckConfig(
        "slow",
        (PY, "-c", SLOW, str(tmp_path / "started"), str(tmp_path / "done"), "30"),
        True,
        1,
    )
    wait = f"import pathlib, time\nwhile not pathlib.Path({str(tmp_path / 'started')!r}).exists():"
    wait += "\n    time.sleep(0.05)\nraise SystemExit(3)"
    broken = CheckConfig("broken", (PY, "-c", "pass"), True, 1, setup=(PY, "-c", wait))
    began = time.monotonic()
    outcome = start(
        project, tracker, FakeRuntime(), parallel(make_config(checks=(slow, broken)), 2)
    )
    assert outcome.exit_code == 1
    assert "'broken'" in outcome.line
    assert time.monotonic() - began < 25  # the 30 s check was killed, with room for slow runners
    assert "-replay-" not in trees(project)
    time.sleep(1)
    assert not (tmp_path / "done").exists()


def test_c9_parallel_checks_fewer_free_slots_still_complete_and_are_journaled(
    project: Project, tracker: InMemoryTracker, tmp_path: Path, isolated_slots: Path
) -> None:
    out = tmp_path / "out"
    config_ = parallel(make_config(checks=recording(out, 0.5, 0.5, 0.5)), 3)
    # Other runs hold all slots but two: the run's own and one more.
    with slots.several(slots.COUNT - 2, isolated_slots) as taken:
        assert len(taken) == slots.COUNT - 2
        outcome = start(project, tracker, FakeRuntime(), config_)
    assert outcome.exit_code == 0, outcome.line
    assert len(records(out)) == 3
    assert len({r["slot"] for r in records(out)}) == 2
    text = journal(project)
    assert "Checks replayed 2 at a time" in text
    assert "`project.parallel_checks` asked for 3; only 2 run slot(s) were free." in text


def test_c9_parallel_checks_one_by_one_is_not_journaled(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert start(project, tracker, FakeRuntime()).exit_code == 0
    assert "Checks in parallel" not in journal(project)


def test_c9_parallel_checks_verify_follows_the_key(
    project: Project, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sh(["git", "branch", "hand/par"], project.root)
    out = tmp_path / "out"
    outcome = verify.verify(
        "hand/par",
        repo_root=project.root,
        config=parallel(make_config(checks=recording(out, 1, 1)), 2),
        runtime=FakeRuntime(),
        environ=environ(),
    )
    assert outcome.exit_code == 0, outcome.line
    seen = records(out)
    assert max(r["began"] for r in seen) < min(r["ended"] for r in seen)
    assert len({r["slot"] for r in seen}) == 2
    review = sh(
        ["git", "show", f"hand/par:{verify.relative_folder('hand/par')}/review.md"], project.root
    )
    assert "Checks replayed 2 at a time" in review
    assert "-par-" not in trees(project)


def test_c9_parallel_checks_a_scan_spares_another_threads_command(tmp_path: Path) -> None:
    """A survivor scan after one check ends does not kill the check another worker runs."""
    before = set(process.descendants(exited=True))
    done: list[process.Completed] = []
    code = "import time; time.sleep(1.5)"
    other = threading.Thread(
        target=lambda: done.append(process.run([PY, "-c", code], cwd=tmp_path))
    )
    other.start()
    time.sleep(0.5)
    assert process.kill_survivors(before) == {}
    other.join(30)
    assert done[0].ok


def test_c9_parallel_checks_cancel_kills_and_refuses_a_threads_commands(tmp_path: Path) -> None:
    done: list[Any] = []
    started = threading.Event()

    def work() -> None:
        started.set()
        done.append(process.run([PY, "-c", "import time; time.sleep(30)"], cwd=tmp_path))
        try:
            process.run([PY, "-c", "pass"], cwd=tmp_path)
        except process.Cancelled as exc:
            done.append(exc)
        with process.shielded():
            done.append(process.run([PY, "-c", "pass"], cwd=tmp_path))

    worker = threading.Thread(target=work)
    worker.start()
    started.wait(10)
    time.sleep(0.5)
    assert worker.ident is not None
    process.cancel({worker.ident})
    worker.join(30)
    process.resume({worker.ident})
    assert not done[0].ok and done[0].duration_s < 20
    assert isinstance(done[1], process.Cancelled)
    assert done[2].ok


def test_c9_parallel_checks_config_key() -> None:
    assert config.parse(VALID).parallel_checks == 1
    assert config.parse(with_change("project.parallel_checks", 3)).parallel_checks == 3
    for bad in (0, -1, 1.5, True, "2"):
        with pytest.raises(config.ConfigError, match=r"project\.parallel_checks"):
            config.parse(with_change("project.parallel_checks", bad))


def test_c9_parallel_checks_ctrl_c_waits_for_the_workers_cleanup(tmp_path: Path) -> None:
    """Ctrl-C returns only once every worker has removed its tree, even when that is slow: on
    Python 3.11 a `Thread.join` interrupted by Ctrl-C took a running thread for stopped."""
    created: list[Path] = []
    removed: list[Path] = []
    main = threading.main_thread().ident
    assert main is not None

    def ctrl_c() -> None:  # a real SIGINT to the waiting thread, which wakes a blocked join
        if hasattr(signal, "pthread_kill"):
            signal.pthread_kill(main, signal.SIGINT)
        else:
            _thread.interrupt_main()

    def setup(check: CheckConfig, tree: Path, env: Any) -> str:
        if check.name == "a":
            time.sleep(0.3)  # the caller is waiting for the workers by now
            ctrl_c()
            time.sleep(0.5)  # Ctrl-C reaches the waiting caller meanwhile
        return ""

    def create(tree: Path) -> None:
        tree.mkdir()
        created.append(tree)

    def remove(tree: Path) -> None:
        time.sleep(0.5)
        tree.rmdir()
        removed.append(tree)

    with pytest.raises(KeyboardInterrupt):
        replay.replay_each(
            [CheckConfig(name, (PY, "-c", "pass"), True, 1) for name in ("a", "b")],
            lambda k: tmp_path / f"tree-{k}",
            create=create,
            setup=setup,
            verify=lambda tree: None,
            remove=remove,
            env=None,
            trees=[],
            slots=(1, 2),
        )
    assert tmp_path / "tree-1" in created
    assert sorted(removed) == sorted(created)


def test_c9_parallel_checks_a_worker_that_fails_to_start_stops_and_waits_for_the_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A later `Thread.start` that raises stops the workers already started and waits until
    they have removed their trees, before the slots are released: none still runs on return."""
    created: list[Path] = []
    removed: list[Path] = []
    running = threading.Event()
    real_start = threading.Thread.start
    starts: list[int] = []

    def start(self: threading.Thread) -> None:
        starts.append(1)
        if len(starts) == 2:
            assert running.wait(10)  # the first worker is in its setup
            raise RuntimeError("can't start new thread")
        real_start(self)

    def setup(check: CheckConfig, tree: Path, env: Any) -> str:
        running.set()
        time.sleep(0.5)
        return ""

    def create(tree: Path) -> None:
        tree.mkdir()
        created.append(tree)

    def remove(tree: Path) -> None:
        time.sleep(0.3)
        tree.rmdir()
        removed.append(tree)

    monkeypatch.setattr(threading.Thread, "start", start)
    with pytest.raises(RuntimeError, match="can't start new thread"):
        replay.replay_each(
            [CheckConfig(name, (PY, "-c", "pass"), True, 1) for name in ("a", "b", "c")],
            lambda k: tmp_path / f"tree-{k}",
            create=create,
            setup=setup,
            verify=lambda tree: None,
            remove=remove,
            env=None,
            trees=[],
            slots=(1, 2),
        )
    assert created == [tmp_path / "tree-1"]  # the first worker stopped: no other check began
    assert removed == created
