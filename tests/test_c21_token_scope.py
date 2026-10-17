"""C21: the tracker token lives only in the tracker and the push (ADR 0017)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from ariane import cli, git, process

TOKEN = "tok-secret-value-123"


def test_c21_token_scope_cli_removes_the_token_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(os.environ, "ARIANE_SCOPE_TOKEN", TOKEN)
    monkeypatch.setattr(cli, "_TOKENS", {})
    assert cli._take_token("ARIANE_SCOPE_TOKEN") == TOKEN
    assert "ARIANE_SCOPE_TOKEN" not in os.environ
    assert cli._environment_with("ARIANE_SCOPE_TOKEN", TOKEN)["ARIANE_SCOPE_TOKEN"] == TOKEN


def test_c21_token_scope_non_push_git_has_no_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(os.environ, "MY_TRACKER_TOKEN", TOKEN)
    monkeypatch.setitem(os.environ, "SSH_AUTH_SOCK", "/tmp/agent")
    seen: list[dict[str, str]] = []

    def stub(argv, *, env=None, **_kw):  # type: ignore[no-untyped-def]
        seen.append(dict(env or {}))
        return process.Completed(tuple(argv), 0, "", "", False, 0.0)

    monkeypatch.setattr(process, "run", stub)
    git.git(["status"], tmp_path)
    git.out(["diff"], tmp_path)
    git.git(["fetch", "origin"], tmp_path)
    git.git(["worktree", "list"], tmp_path)
    git.git(["ls-remote", "origin"], tmp_path)
    assert len(seen) == 5
    for env in seen:
        assert "MY_TRACKER_TOKEN" not in env and "SSH_AUTH_SOCK" not in env
        assert TOKEN not in env.values()
        assert "PATH" in env


def test_c21_token_scope_push_still_authenticates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[dict[str, str]] = []

    def stub(argv, *, env=None, **_kw):  # type: ignore[no-untyped-def]
        seen.append(dict(env or {}))
        return process.Completed(tuple(argv), 0, "", "", False, 0.0)

    monkeypatch.setattr(process, "run", stub)
    git.push(tmp_path, "https://example.invalid/r.git", "abc", "b", token=TOKEN)
    values = [v for k, v in seen[0].items() if k.startswith("GIT_CONFIG_VALUE_")]
    assert any(v.startswith("Authorization: Basic ") for v in values)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux only")
@pytest.mark.skipif(
    sys.platform.startswith("linux") and os.geteuid() == 0,
    reason="root can read any environment block (the README states this residual)",
)
def test_c21_token_scope_environment_block_is_not_readable_by_a_child() -> None:
    code = (
        "import os,subprocess,sys\n"
        "from ariane import process\n"
        "process.make_undumpable()\n"
        "r = subprocess.run(['cat', f'/proc/{os.getpid()}/environ'], capture_output=True)\n"
        "sys.exit(0 if b'tok-secret-value-123' not in r.stdout else 1)\n"
    )
    env = {**os.environ, "ARIANE_SCOPE_TOKEN": TOKEN}
    done = subprocess.run([sys.executable, "-c", code], env=env, check=False)
    assert done.returncode == 0


def test_c21_token_scope_failing_prctl_is_a_warning_not_fatal(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import ctypes

    class Broken:
        def prctl(self, *_args: int) -> int:
            return -1

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(ctypes, "CDLL", lambda *_a, **_k: Broken())
    process.make_undumpable()  # must not raise
