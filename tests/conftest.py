"""Shared fixtures: real git repositories with a local bare remote, and test doubles."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from ariane import process
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

IDENTITY = {
    f"GIT_{name}_{part}": value
    for name in ("AUTHOR", "COMMITTER")
    for part, value in (("NAME", "Ariane Test"), ("EMAIL", "ariane-test@example.invalid"))
}


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
    for key, value in IDENTITY.items():
        monkeypatch.setenv(key, value)


@pytest.fixture(autouse=True)
def no_subreaper(monkeypatch: pytest.MonkeyPatch) -> None:
    """`cli.main` would make the test process the subreaper of every orphan for the rest of the
    run; the tests that need it call the real `process.set_child_subreaper` themselves."""
    monkeypatch.setattr(process, "set_child_subreaper", lambda on=True: None)
    process.take_killed()  # nothing an earlier test left behind is counted in this one


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


@pytest.fixture(scope="session")
def project_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The bare remote and its clone, built once per xdist worker (ADR 0049).

    Its base temp directory is the worker's own, and no test gets its path: `project` copies it.
    It runs before the per-test `isolated_git`, so it sets its own isolated configuration.
    """
    base = tmp_path_factory.mktemp("project-template")
    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
        **IDENTITY,
        "GIT_CONFIG_GLOBAL": str(base / "gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    remote = base / "origin.git"
    sh(["git", "init", "--quiet", "--bare", "--initial-branch=main", str(remote)], base, env)
    root = base / "proj"
    sh(["git", "clone", "--quiet", str(remote), str(root)], base, env)
    sh(["git", "checkout", "--quiet", "-b", "main"], root, env)
    (root / ".gitignore").write_text("ignored-by-git/\n", encoding="utf-8")
    (root / "app.txt").write_text("version 1\n", encoding="utf-8")
    sh(["git", "add", "--all"], root, env)
    sh(["git", "commit", "--quiet", "-m", "initial"], root, env)
    sh(["git", "push", "--quiet", "origin", "main"], root, env)
    return base


def _config_value(text: str) -> str:
    """`text` quoted as a value of a git configuration file."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def copy_template(template: Path, dest: Path) -> Project:
    """A copy of `template` under `dest` whose `origin` is the copy's own remote, without git."""
    remote = dest / "origin.git"
    shutil.copytree(template / "origin.git", remote, symlinks=True)
    root = dest / "proj"
    shutil.copytree(template / "proj", root, symlinks=True)
    config = root / ".git" / "config"
    lines = config.read_text(encoding="utf-8").splitlines(keepends=True)
    urls = [i for i, line in enumerate(lines) if line.strip().startswith("url = ")]
    assert len(urls) == 1, lines
    lines[urls[0]] = f"\turl = {_config_value(str(remote))}\n"
    config.write_text("".join(lines), encoding="utf-8")
    return Project(root=root.resolve(), remote=remote)


@pytest.fixture
def project(tmp_path: Path, project_template: Path) -> Project:
    """A repository and a remote of the test's own, copied from the worker's template."""
    return copy_template(project_template, tmp_path)


def commit_on_branch(
    repo: Path, branch: str, message: str, files: dict[str, str], *, parent: str | None = None
) -> None:
    """Add one commit to `branch` without checking it out, with one git process.

    The commit's parent is `parent` (by default the branch itself, which must exist) and it sets
    `files`, a path to its content, keeping every other file of the parent. A path whose content
    starts with `symlink:` becomes a symbolic link to the rest of the content.
    """
    lines = [
        f"commit refs/heads/{branch}",
        f"committer {os.environ['GIT_COMMITTER_NAME']} <{os.environ['GIT_COMMITTER_EMAIL']}> now",
        f"data {len(message.encode())}",
        message,
        f"from {parent or 'refs/heads/' + branch}^0",
    ]
    for path, content in files.items():
        mode = "120000" if content.startswith("symlink:") else "100644"
        data = content.removeprefix("symlink:")
        lines += [f"M {mode} inline {path}", f"data {len(data.encode())}", data]
    script = "\n".join(lines) + "\n"
    done = subprocess.run(
        ["git", "fast-import", "--quiet", "--date-format=now"],
        cwd=repo,
        input=script.encode(),
        capture_output=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr.decode(errors="replace")


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
    """Set app.txt; a fix session adds a line for its round, so that it changes the commit."""
    marker = session.prompt.partition("fix round ")[2][:1]
    note = f"fix {marker}\n" if marker else ""
    (session.cwd / "app.txt").write_text(f"version 2\n{note}", encoding="utf-8")


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
