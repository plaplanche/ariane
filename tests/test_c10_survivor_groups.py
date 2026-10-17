"""C10: survivors are stopped and killed by process group and session too (ADR 0031, #188)."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from ariane import process
from ariane.process import _Proc
from ariane.process import set_child_subreaper as real_set_child_subreaper

# `signal.SIGKILL` and `signal.SIGSTOP` do not exist on Windows, where mypy also runs.
SIGKILL: int = getattr(signal, "SIGKILL", 9)
SIGSTOP: int = getattr(signal, "SIGSTOP", 19)

linux_only = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="survivors are found on Linux only"
)


@pytest.fixture
def subreaper() -> Iterator[None]:
    real_set_child_subreaper(True)
    try:
        yield
    finally:
        real_set_child_subreaper(False)


@pytest.fixture
def killpg(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[tuple[int, int]]]:
    """Record the group signals instead of sending them; pid signals are dropped."""
    sent: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "killpg", lambda group, signum: sent.append((group, signum)))
    monkeypatch.setattr(process, "_signal", lambda pids, signum: None)
    monkeypatch.setattr(process, "_REAP_SECONDS", 0.05)
    yield sent
    process.take_killed()


# Each generation forks the next and exits at once (no pause, harder than the 1 ms of #188):
# a scan may find only exited ones, and never see the running generation.
_HOPPER = (
    "import os, sys, time\n"
    "end = time.monotonic() + 20\n"
    "if os.fork(): os._exit(0)\n"
    "os.setsid()\n"
    "with open(sys.argv[1], 'w') as file: file.write(str(os.getsid(0)))\n"
    "while time.monotonic() < end:\n"
    "    if os.fork(): os._exit(0)\n"
)


def _in_session(session: int) -> set[int]:
    return {
        pid
        for pid, proc in process._process_table().items()
        if proc.session == session and proc.state not in ("Z", "X")
    }


@linux_only
@pytest.mark.usefixtures("subreaper")
def test_c10_survivor_groups_a_process_that_keeps_forking_is_killed_20_times_in_a_row(
    tmp_path: Path,
) -> None:
    if sys.platform == "win32":  # skipped there; for mypy, which also runs on Windows
        return
    for attempt in range(20):
        sid_file = tmp_path / f"sid-{attempt}"
        before = set(process.descendants(exited=True))
        subprocess.run([sys.executable, "-c", _HOPPER, str(sid_file)], check=True)
        deadline = time.monotonic() + 5
        while not sid_file.exists() or not sid_file.read_text(encoding="utf-8"):
            assert time.monotonic() < deadline
            time.sleep(0.01)
        session = int(sid_file.read_text(encoding="utf-8"))
        try:
            assert process.kill_survivors(before), f"attempt {attempt}"
            time.sleep(0.05)
            assert _in_session(session) == set(), f"attempt {attempt}"
            assert set(process.descendants()) - before == set(), f"attempt {attempt}"
        finally:
            with contextlib.suppress(ProcessLookupError):  # a failed attempt leaves none behind
                os.killpg(session, SIGKILL)
            process.take_killed()


@linux_only
def test_c10_survivor_groups_a_group_of_a_process_from_before_is_never_signalled(
    monkeypatch: pytest.MonkeyPatch, killpg: list[tuple[int, int]]
) -> None:
    if sys.platform == "win32":  # skipped there; for mypy, which also runs on Windows
        return
    me = os.getpid()
    own = os.getpgid(0)
    table = {
        999_990: _Proc(me, "S", "older", 100_000, 100_001),
        999_991: _Proc(me, "S", "joined", 100_000, 100_001),  # in the older one's group
        999_992: _Proc(me, "S", "mine", own, os.getsid(0)),  # in Ariane's own group
        999_993: _Proc(me, "S", "escaped", 200_000, 200_000),
    }
    monkeypatch.setattr(process, "_process_table", lambda: table)
    found = process.kill_survivors({999_990})
    assert set(found) == {999_991, 999_992, 999_993}
    signalled = {group for group, _ in killpg}
    assert signalled == {200_000}
    assert (200_000, SIGSTOP) in killpg


@linux_only
def test_c10_survivor_groups_a_zombie_group_is_read_before_it_is_reaped(
    monkeypatch: pytest.MonkeyPatch, killpg: list[tuple[int, int]]
) -> None:
    zombie = 999_994
    procs = {zombie: _Proc(os.getpid(), "Z", "gone", 300_000, 300_001)}
    monkeypatch.setattr(process, "_process_table", lambda: dict(procs))

    def reap(pid: int) -> bool:
        return procs.pop(pid, None) is not None  # once reaped, no later scan lists it

    monkeypatch.setattr(process, "_wait", reap)
    assert process.kill_survivors(set()) == {}
    assert (300_000, SIGSTOP) in killpg
    assert (300_001, SIGSTOP) in killpg


@linux_only
def test_c10_survivor_groups_at_the_deadline_the_groups_found_get_sigkill(
    monkeypatch: pytest.MonkeyPatch, killpg: list[tuple[int, int]]
) -> None:
    stuck = 999_995
    table = {stuck: _Proc(os.getpid(), "D", "stuck", 400_000, 400_001)}
    monkeypatch.setattr(process, "_process_table", lambda: table)
    assert process.kill_survivors(set()) == {stuck: "stuck"}
    assert (400_000, SIGKILL) in killpg
    assert (400_001, SIGKILL) in killpg
