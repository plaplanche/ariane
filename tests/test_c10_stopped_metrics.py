"""C10, C19: a stop before the ticket folder exists still records its metrics (ADR 0031)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from ariane import flow, process
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project
from test_flow import start, worktree


def test_c10_stopped_metrics_an_interrupted_first_setup_keeps_its_survivors(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupted(*args: Any, **kwargs: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(flow._TicketRun, "setup", interrupted)
    monkeypatch.setattr(process, "kill_survivors", lambda *args, **kwargs: {})
    monkeypatch.setattr(process, "take_killed", lambda: {4242: "detached"})
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == flow.EXIT_INTERRUPTED, outcome.line
    assert not (worktree(project) / "work/7").exists()  # the folder is not created to record it
    path = flow.stopped_metrics_path(worktree(project), 7)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["outcome"] == "stopped"
    assert data["surviving_processes"] == 1
