"""C10: Ariane runs no agent, setup or check when it cannot become the subreaper (ADR 0031)."""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable

import pytest

from ariane import cli, process
from ariane.process import set_child_subreaper as real_set_child_subreaper

from conftest import Project

REASON = "[Errno 1] prctl(PR_SET_CHILD_SUBREAPER) failed"


def test_c10_subreaper_failure_refuses_start_and_verify(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project.root)
    monkeypatch.setattr(process, "set_child_subreaper", lambda on=True: REASON)
    ran: list[str] = []

    def recorder(name: str) -> Callable[..., int]:
        def run(*args: object, **kwargs: object) -> int:
            ran.append(name)
            return 0

        return run

    for name in ("start", "verify", "status"):
        monkeypatch.setattr(cli, f"_{name}", recorder(name))
    assert cli.main(["start", "7"]) == cli.EXIT_USAGE
    assert cli.main(["verify", "hand/fix"]) == cli.EXIT_USAGE
    out = capsys.readouterr().out
    assert out.count("could not become the subreaper") == 2
    assert REASON in out
    assert cli.main(["status", "7"]) == 0  # runs no agent, setup or check
    assert ran == ["status"]


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="the subreaper is Linux only")
def test_c10_subreaper_prctl_failure_is_returned_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Refusing:
        def prctl(self, *args: int) -> int:
            return -1

    monkeypatch.setattr(ctypes, "CDLL", lambda *args, **kwargs: Refusing())
    failure = real_set_child_subreaper(True)
    assert failure is not None
    assert "PR_SET_CHILD_SUBREAPER" in failure


def test_c10_subreaper_elsewhere_or_allowed_returns_none() -> None:
    try:
        assert real_set_child_subreaper(True) is None
    finally:
        real_set_child_subreaper(False)
