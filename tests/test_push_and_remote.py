"""C11: Ariane pushes with its own token, and the remote check ignores a base-branch merge."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ariane import git, process
from ariane.config import TrackerConfig
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, edit_app, make_config, sh
from test_flow import TOKEN, journal, start

_RECORD = tuple[tuple[str, ...], dict[str, str]]


def _fake_git(
    monkeypatch: pytest.MonkeyPatch, returncodes: list[int], stderr: str = ""
) -> list[_RECORD]:
    calls: list[_RECORD] = []

    def fake(args: list[str], cwd: Path, *, env: Any = None, check: bool = True) -> Any:
        calls.append((tuple(args), dict(env or {})))
        code = returncodes[len(calls) - 1]
        return process.Completed(tuple(args), code, "", stderr if code else "", False, 0.0)

    monkeypatch.setattr(git, "git", fake)
    return calls


def _config_pairs(env: dict[str, str]) -> dict[str, str]:
    count = int(env["GIT_CONFIG_COUNT"])
    return {env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"] for i in range(count)}


def test_c11_push_token_goes_as_a_header_in_the_environment_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _fake_git(monkeypatch, [0])
    way = git.push(Path("."), "https://example.invalid/r.git", "abc", "ariane/7", token=TOKEN)
    assert len(calls) == 1
    args, env = calls[0]
    pairs = _config_pairs(env)
    assert pairs["credential.helper"] == ""
    assert pairs["http.extraHeader"].startswith("Authorization: ")
    assert TOKEN not in " ".join(args) and TOKEN not in "".join(pairs.values())
    assert "header" in way and TOKEN not in way


def test_c11_push_token_failure_message_hides_the_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_git(monkeypatch, [1], stderr=f"fatal: bad request with {TOKEN}")
    with pytest.raises(git.GitError) as raised:
        git.push(Path("."), "https://example.invalid/r.git", "abc", "b", token=TOKEN)
    assert TOKEN not in str(raised.value)


def test_c11_push_token_refused_for_authentication_falls_back_once_without_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _fake_git(monkeypatch, [1, 0], stderr="fatal: Authentication failed for 'x'")
    way = git.push(Path("."), "https://example.invalid/r.git", "abc", "b", token=TOKEN)
    assert len(calls) == 2
    first, second = (_config_pairs(env) for _, env in calls)
    assert "http.extraHeader" in first
    assert "http.extraHeader" not in second and second["credential.helper"] == ""
    assert "after the push with the token header was refused" in way


def test_c11_push_token_other_failure_does_not_fall_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _fake_git(monkeypatch, [1, 0], stderr="! [rejected] (non-fast-forward)")
    with pytest.raises(git.GitError):
        git.push(Path("."), "https://example.invalid/r.git", "abc", "b", token=TOKEN)
    assert len(calls) == 1


def test_c11_push_token_unset_pushes_once_without_header_and_journals_it(
    project: Project, tracker: InMemoryTracker
) -> None:
    config = make_config()
    tracker_config = TrackerConfig("github", "owner/name", "NO_SUCH_TOKEN_VARIABLE", "https://x")
    config = type(config)(**{**config.__dict__, "tracker": tracker_config})
    outcome = start(project, tracker, FakeRuntime(), config)
    assert outcome.exit_code == 0, outcome.line
    assert "without a header (no tracker token set)" in journal(project)
    assert "ariane/7" in project.remote_branches()


def test_c11_push_token_a_delivered_ticket_journals_the_header_push_without_the_token(
    project: Project, tracker: InMemoryTracker
) -> None:
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == 0, outcome.line
    text = journal(project)
    assert "authorization header" in text and TOKEN not in text


def _other_clone(project: Project) -> Path:
    clone = project.root.parent / "other"
    sh(["git", "clone", "--quiet", str(project.remote), str(clone)], project.root.parent)
    return clone


def _remote_change(project: Project, change: Callable[[Path], None]) -> Callable[[Session], None]:
    def action(session: Session) -> None:
        edit_app(session)
        change(_other_clone(project))

    return action


def _commit_on_main(clone: Path) -> None:
    (clone / "merged.txt").write_text("merge\n", encoding="utf-8")
    sh(["git", "add", "--all"], clone)
    sh(["git", "commit", "--quiet", "-m", "merge"], clone)
    sh(["git", "push", "--quiet", "origin", "HEAD:main"], clone)


def test_c11_remote_check_a_fast_forward_of_the_base_branch_does_not_stop(
    project: Project, tracker: InMemoryTracker
) -> None:
    action = _remote_change(project, _commit_on_main)
    outcome = start(project, tracker, FakeRuntime(action=action))
    assert outcome.exit_code == 0, outcome.line + outcome.detail
    assert "ariane/7" in project.remote_branches()


def test_c11_remote_check_a_new_branch_stops(project: Project, tracker: InMemoryTracker) -> None:
    def create(clone: Path) -> None:
        sh(["git", "push", "--quiet", "origin", "HEAD:refs/heads/sneaky"], clone)

    outcome = start(project, tracker, FakeRuntime(action=_remote_change(project, create)))
    assert outcome.exit_code == 1
    assert "the remote changed during the agent session (refs/heads/sneaky)" in outcome.line


def test_c11_remote_check_a_deleted_branch_stops(
    project: Project, tracker: InMemoryTracker
) -> None:
    sh(["git", "push", "--quiet", "origin", "main:refs/heads/other"], project.root)

    def delete(clone: Path) -> None:
        sh(["git", "push", "--quiet", "origin", ":refs/heads/other"], clone)

    outcome = start(project, tracker, FakeRuntime(action=_remote_change(project, delete)))
    assert outcome.exit_code == 1
    assert "(refs/heads/other)" in outcome.line


def test_c11_remote_check_a_rewritten_base_branch_stops(
    project: Project, tracker: InMemoryTracker
) -> None:
    def rewrite(clone: Path) -> None:
        sh(["git", "commit", "--quiet", "--amend", "--allow-empty", "-m", "rewritten"], clone)
        sh(["git", "push", "--quiet", "--force", "origin", "HEAD:main"], clone)

    outcome = start(project, tracker, FakeRuntime(action=_remote_change(project, rewrite)))
    assert outcome.exit_code == 1
    assert "(refs/heads/main)" in outcome.line


def test_c11_remote_check_a_change_to_the_ticket_branch_stops(
    project: Project, tracker: InMemoryTracker
) -> None:
    def take(clone: Path) -> None:
        sh(["git", "push", "--quiet", "origin", "HEAD:refs/heads/ariane/7"], clone)

    outcome = start(project, tracker, FakeRuntime(action=_remote_change(project, take)))
    assert outcome.exit_code == 1
    assert "(refs/heads/ariane/7)" in outcome.line
