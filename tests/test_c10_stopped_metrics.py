"""C10, C19: a stop before the ticket folder exists still records its metrics (ADR 0031)."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import pytest

from ariane import flow, metrics, process, replay
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project
from test_flow import start, worktree

SIGKILL = 9  # POSIX; `signal.SIGKILL` does not exist on Windows, where mypy also runs


def test_c10_stopped_metrics_an_interrupted_first_setup_keeps_its_survivors(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupted(*args: Any, **kwargs: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(replay, "run_setup", interrupted)
    monkeypatch.setattr(process, "kill_survivors", lambda *args, **kwargs: {})
    monkeypatch.setattr(process, "take_killed", lambda: {4242: "detached"})
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == flow.EXIT_INTERRUPTED, outcome.line
    assert not (worktree(project) / "work/7").exists()  # the folder is not created to record it
    path = metrics.stopped_metrics_path(worktree(project), 7)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["outcome"] == "stopped"
    assert data["surviving_processes"] == 1


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="survivors are found on Linux")
def test_c10_stopped_metrics_a_survivor_that_never_stops_still_gets_sigkill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0031: at the deadline, a survivor stuck in uninterruptible I/O (`D`) is killed too."""
    stuck = 999_999
    table = {stuck: process._Proc(os.getpid(), "D", "stuck")}
    monkeypatch.setattr(process, "_process_table", lambda: table)
    monkeypatch.setattr(process, "_REAP_SECONDS", 0.05)
    sent: list[tuple[set[int], int]] = []
    monkeypatch.setattr(process, "_signal", lambda pids, signum: sent.append((set(pids), signum)))
    found = process.kill_survivors(set())
    assert found == {stuck: "stuck"}
    assert ({stuck}, SIGKILL) in sent
    process.take_killed()
