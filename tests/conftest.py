"""Shared fixtures: real git repositories with a local bare remote, and test doubles."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from ariane.config import AgentConfig, CheckConfig, Config, TrackerConfig
from ariane.runtime import Session, SessionResult, StopReason
from ariane.tracker import InMemoryTracker

PY = sys.executable


def sh(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    done = subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", check=False
    )
    assert done.returncode == 0, f"{args} failed: {done.stdout}{done.stderr}"
    return done.stdout.strip()


@pytest.fixture(autouse=True)
def isolated_git(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test gets a git identity and no user or system git configuration."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key in [
        k
        for k in os.environ
        if k.startswith("GIT_CONFIG_KEY_") or k.startswith("GIT_CONFIG_VALUE_")
    ]:
        monkeypatch.delenv(key)
    monkeypatch.delenv("GIT_CONFIG_COUNT", raising=False)
    for name in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{name}_NAME", "Ariane Test")
        monkeypatch.setenv(f"GIT_{name}_EMAIL", "ariane-test@example.invalid")


@dataclass
class Project:
    """A checkout of a repository whose `origin` is a local bare repository."""

    root: Path
    remote: Path

    def remote_branches(self) -> dict[str, str]:
        listing = sh(["git", "ls-remote", "--heads", str(self.remote)], self.root)
        heads = {}
        for line in listing.splitlines():
            sha, _, ref = line.partition("\t")
            heads[ref.removeprefix("refs/heads/")] = sha
        return heads

    def show(self, ref: str, path: str) -> str:
        return sh(["git", "--git-dir", str(self.remote), "show", f"{ref}:{path}"], self.root)


@pytest.fixture
def project(tmp_path: Path) -> Project:
    remote = tmp_path / "origin.git"
    sh(["git", "init", "--quiet", "--bare", "--initial-branch=main", str(remote)], tmp_path)
    root = tmp_path / "proj"
    sh(["git", "clone", "--quiet", str(remote), str(root)], tmp_path)
    sh(["git", "checkout", "--quiet", "-b", "main"], root)
    (root / ".gitignore").write_text("ignored-by-git/\n", encoding="utf-8")
    (root / "app.txt").write_text("version 1\n", encoding="utf-8")
    sh(["git", "add", "--all"], root)
    sh(["git", "commit", "--quiet", "-m", "initial"], root)
    sh(["git", "push", "--quiet", "origin", "main"], root)
    return Project(root=root.resolve(), remote=remote)


def make_config(
    *,
    setup: tuple[str, ...] | None = None,
    checks: tuple[CheckConfig, ...] | None = None,
) -> Config:
    return Config(
        base_branch="main",
        setup=setup,
        tracker=TrackerConfig("github", "owner/name", "GH_TOKEN", "https://api.github.com"),
        implementer=AgentConfig(
            runtime="claude-code",
            model="test-model",
            tools=("Read", "Edit", "Bash"),
            max_budget_usd=1.0,
            timeout_minutes=1.0,
        ),
        checks=checks
        or (
            CheckConfig(
                "app has version 2",
                (PY, "-c", "import sys; sys.exit(0 if '2' in open('app.txt').read() else 1)"),
                True,
                1.0,
            ),
        ),
    )


Action = Callable[[Session], None]


def edit_app(session: Session) -> None:
    (session.cwd / "app.txt").write_text("version 2\n", encoding="utf-8")


@dataclass
class FakeRuntime:
    """An agent runtime that applies `action` to the working tree instead of calling a model."""

    action: Action = edit_app
    stop_reason: StopReason = StopReason.FINISHED
    summary: str = "changed app.txt"
    name: str = "fake"
    sessions: list[Session] = field(default_factory=list)

    def run(self, session: Session) -> SessionResult:
        self.sessions.append(session)
        self.action(session)
        return SessionResult(self.stop_reason, 0.42, 10, 20, 30, 40, self.summary)


@pytest.fixture
def tracker() -> Iterator[InMemoryTracker]:
    memory = InMemoryTracker()
    memory.add_issue(7, "Bump the app version", "Set app.txt to version 2.")
    yield memory
