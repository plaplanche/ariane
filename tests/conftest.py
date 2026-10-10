"""Shared fixtures: real git repositories with a local bare remote, and test doubles."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from ariane.config import (
    DEFAULT_DEFINITION_OF_DONE,
    AgentConfig,
    CheckConfig,
    Config,
    TrackerConfig,
)
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
        reviewer=AgentConfig(
            runtime="claude-code",
            model="test-reviewer",
            tools=("Read", "Glob", "Grep"),
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


def go_answer(items: tuple[str, ...] | None = None) -> dict[str, Any]:
    """A reviewer's `go` answer that meets every sentence of the default definition of done."""
    texts = items or tuple(str(i.text) for i in DEFAULT_DEFINITION_OF_DONE)
    return {
        "verdict": "go",
        "findings": [],
        "definition_of_done": [{"item": t, "met": True, "evidence": "seen"} for t in texts],
        "learnings": [],
    }


@dataclass
class FakeRuntime:
    """An agent runtime that applies `action` to the working tree instead of calling a model."""

    action: Action = edit_app
    stop_reason: StopReason = StopReason.FINISHED
    summary: str = "changed app.txt"
    name: str = "fake"
    login_variables: tuple[str, ...] = ("ANTHROPIC_", "CLAUDE_")
    sessions: list[Session] = field(default_factory=list)
    # What a reviewer session does and answers, one entry per session; the last repeats.
    review_actions: list[Action] = field(default_factory=list)
    answers: list[Any] = field(default_factory=lambda: [go_answer()])

    def run(self, session: Session) -> SessionResult:
        self.sessions.append(session)
        if session.role == "reviewer":
            return self.review(session)
        self.action(session)
        return SessionResult(self.stop_reason, 0.42, 10, 20, 30, 40, self.summary)

    def review(self, session: Session) -> SessionResult:
        index = sum(1 for s in self.sessions if s.role == "reviewer") - 1
        if self.review_actions:
            self.review_actions[min(index, len(self.review_actions) - 1)](session)
        answer = self.answers[min(index, len(self.answers) - 1)]
        text = answer if isinstance(answer, str) else json.dumps(answer)
        structured = None if isinstance(answer, str) else answer
        return SessionResult(
            StopReason.FINISHED, 0.1, 1, 2, 3, 4, text, structured_output=structured
        )


@pytest.fixture
def tracker() -> Iterator[InMemoryTracker]:
    memory = InMemoryTracker()
    memory.add_issue(7, "Bump the app version", "Set app.txt to version 2.")
    yield memory
