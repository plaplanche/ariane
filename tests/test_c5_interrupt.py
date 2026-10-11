"""Ctrl-C stops the agent's whole process tree and is recorded (C5, C23)."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from ariane import flow, process, ticket
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import PY, FakeRuntime, Project
from test_flow import journal, start, worktree

# Starts a grandchild, both write their pid to the files named in argv, then sleeps.
TREE = """
import os, pathlib, subprocess, sys, time
pathlib.Path(sys.argv[1]).write_text(str(os.getpid()))
child = (
    "import os, pathlib, sys, time\\n"
    "pathlib.Path(sys.argv[1]).write_text(str(os.getpid()))\\n"
    "time.sleep(60)\\n"
)
subprocess.Popen([sys.executable, "-c", child, sys.argv[2]])
time.sleep(60)
"""


def _alive(pid: int) -> bool:
    try:
        import os

        os.kill(pid, 0)
    except OSError:
        return False
    # A zombie still answers signal 0: look at its state.
    state = Path(f"/proc/{pid}/stat")
    return not (state.exists() and state.read_text().rsplit(")", 1)[1].split()[0] == "Z")


def _pid(path: Path) -> int:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if path.exists() and path.read_text():
            return int(path.read_text())
        time.sleep(0.05)
    raise AssertionError(f"{path} was never written")


def _interrupt_wait(monkeypatch: pytest.MonkeyPatch, started: list[Path]) -> None:
    real = subprocess.Popen.wait

    def wait(self: subprocess.Popen[bytes], timeout: float | None = None) -> int:
        if timeout != process._DRAIN_SECONDS:
            for path in started:
                _pid(path)
            raise KeyboardInterrupt
        return real(self, timeout)

    monkeypatch.setattr(subprocess.Popen, "wait", wait)


@pytest.mark.skipif(not Path("/proc").exists(), reason="needs /proc")
def test_c5_interrupt_kills_the_process_tree_and_reraises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, grandchild = tmp_path / "parent.pid", tmp_path / "grandchild.pid"
    _interrupt_wait(monkeypatch, [parent, grandchild])
    with pytest.raises(KeyboardInterrupt):
        process.run([PY, "-c", TREE, str(parent), str(grandchild)], cwd=tmp_path)
    pids = [int(parent.read_text()), int(grandchild.read_text())]
    deadline = time.monotonic() + 10
    while any(_alive(pid) for pid in pids) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not any(_alive(pid) for pid in pids)


def test_c5_interrupt_during_the_agent_session_is_recorded_and_exits_130(
    project: Project, tracker: InMemoryTracker
) -> None:
    def interrupt(session: Session) -> None:
        raise KeyboardInterrupt

    outcome = start(project, tracker, FakeRuntime(action=interrupt))
    assert outcome.exit_code == flow.EXIT_INTERRUPTED == 130
    assert "interrupted by the user" in outcome.line
    assert "interrupted by the user" in journal(project)
    status = (worktree(project) / ticket.relative_folder(7) / "status.md").read_text()
    assert "interrupted by the user" in status
