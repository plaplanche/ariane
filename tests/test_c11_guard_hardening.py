"""C11, C23 (ADR 0017, ADR 0028): verify guards git like start; diffs never run drivers; the
base instructions are read before any agent runs; the push is guarded once more."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_verify import BRANCH, branch  # noqa: F401

from ariane import git, ticket, verify
from ariane.config import CheckConfig
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import PY, FakeRuntime, Project, edit_app, make_config, sh
from test_flow import environ, start


@pytest.mark.usefixtures("branch")
def test_c11_guard_hardening_verify_refuses_when_a_check_changes_git_config(
    project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = Path(
        sh(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], project.root)
    )
    sneak = f"open({(config / 'config').as_posix()!r}, 'a').write('[alias]\\n\\tx = status\\n')"
    checks = (CheckConfig("edits git", (PY, "-c", sneak), True, 1),)
    seen: list[list[str]] = []
    real = git.git

    def spy(args: list[str], cwd: Path, **k: Any) -> Any:
        seen.append(args)
        return real(args, cwd, **k)

    monkeypatch.setattr(git, "git", spy)
    runtime = FakeRuntime()
    outcome = verify.verify(
        BRANCH,
        repo_root=project.root,
        config=make_config(checks=checks),
        runtime=runtime,
        environ=environ(),
    )
    assert outcome.exit_code == 1
    assert "the checks changed git configuration, hooks or local branches" in outcome.line
    assert not runtime.sessions
    # After the refusal: no status, ls-remote or commit. Only the cleanup of the reviewed
    # worktree (`worktree remove`, with the safe options) still runs.
    after = seen[[i for i, a in enumerate(seen) if a[:1] == ["config"]][-1] :]
    assert not any(a[:1] in (["status"], ["commit"], ["ls-remote"]) for a in after)


def test_c11_guard_hardening_diffs_ignore_external_and_textconv_drivers(
    project: Project, tmp_path: Path
) -> None:
    marker = tmp_path / "driver-ran"
    script = tmp_path / "driver.sh"
    script.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
    script.chmod(0o755)
    sh(["git", "config", "diff.external", str(script)], project.root)
    sh(["git", "config", "diff.t.textconv", str(script)], project.root)
    (project.root / ".gitattributes").write_text("*.txt diff=t\n", encoding="utf-8")
    first = git.head(project.root)
    (project.root / "app.txt").write_text("changed\n", encoding="utf-8")
    sh(["git", "add", "-A"], project.root)
    sh(["git", "commit", "-q", "-m", "change"], project.root)
    text = git.diff(project.root, first, "HEAD", "work")
    assert "+changed" in text
    assert not marker.exists()


def test_c11_guard_hardening_a_pushinsteadof_added_after_the_last_session_stops_the_delivery(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    pushed: list[str] = []
    monkeypatch.setattr(git, "push", lambda *a, **k: pushed.append("push"))
    real = git.commit

    def commit(cwd: Path, paths: list[str], message: str, **k: Any) -> Any:
        done = real(cwd, paths, message, **k)
        if "record the checks and the delivery" in message:
            sh(["git", "config", "url.https://elsewhere.invalid/.pushInsteadOf", "x"], cwd)
        return done

    monkeypatch.setattr(git, "commit", commit)
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == 1
    assert "reroutes URLs before the push" in outcome.line
    assert pushed == [] and tracker.opened == []


def test_c11_guard_hardening_delivery_runs_the_guard_right_before_the_push(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[str] = []
    real = git.url_rewrites

    def rewrites(cwd: Path) -> list[str]:
        order.append("guard")
        return real(cwd)

    monkeypatch.setattr(git, "url_rewrites", rewrites)

    def push(*args: Any, **kwargs: Any) -> str:
        order.append("push")
        return ""

    monkeypatch.setattr(git, "push", push)
    start(project, tracker, FakeRuntime())
    assert order[-2:] == ["guard", "push"]


def _publish_instructions(project: Project, text: str) -> None:
    (project.root / "CLAUDE.md").write_text(text, encoding="utf-8")
    sh(["git", "add", "CLAUDE.md"], project.root)
    sh(["git", "commit", "-q", "-m", "instructions"], project.root)
    sh(["git", "push", "-q", "origin", "HEAD:main"], project.root)


def test_c11_guard_hardening_reviewer_gets_the_instructions_of_the_fetched_base(
    project: Project, tracker: InMemoryTracker
) -> None:
    _publish_instructions(project, "Base rule: fetched.\n")

    def move_tracking_ref(session: Session) -> None:
        if session.role == "implementer":
            edit_app(session)
            (session.cwd / "CLAUDE.md").write_text("Base rule: forged.\n", encoding="utf-8")
            sh(["git", "add", "CLAUDE.md"], session.cwd)
            sh(["git", "commit", "-q", "-m", "forged"], session.cwd)
            sh(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], session.cwd)

    runtime = FakeRuntime(action=move_tracking_ref)
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "changed git configuration, hooks or local branches" in outcome.line
    assert "refs/remotes/origin/main" in outcome.detail
    assert not any(s.role == "reviewer" for s in runtime.sessions)


def test_c11_guard_hardening_instructions_are_read_before_any_agent_runs(
    project: Project, tracker: InMemoryTracker
) -> None:
    _publish_instructions(project, "Base rule: fetched.\n")
    runtime = FakeRuntime()
    assert start(project, tracker, runtime).exit_code == 0
    prompt = next(s for s in runtime.sessions if s.role == "reviewer").prompt
    assert "Base rule: fetched." in prompt


def test_c11_guard_hardening_verify_records_replace_a_symlinked_checks_file(
    project: Project, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("untouched\n", encoding="utf-8")
    sh(["git", "branch", BRANCH], project.root)
    other = project.root.parent / "hand-tree"
    sh(["git", "worktree", "add", "--quiet", str(other), BRANCH], project.root)
    (other / "app.txt").write_text("version 2\n", encoding="utf-8")
    folder = other / verify.relative_folder(BRANCH)
    folder.mkdir(parents=True)
    (folder / ticket.CHECKS).symlink_to(outside)
    sh(["git", "add", "-A"], other)
    sh(["git", "commit", "--quiet", "-m", "Bump by hand, with a link"], other)
    sh(["git", "worktree", "remove", "--force", str(other)], project.root)
    outcome = verify.verify(
        BRANCH,
        repo_root=project.root,
        config=make_config(),
        runtime=FakeRuntime(),
        environ=environ(),
    )
    assert outcome.exit_code == 0, outcome.line
    assert outside.read_text(encoding="utf-8") == "untouched\n"
    mode = sh(
        ["git", "ls-tree", BRANCH, f"{verify.relative_folder(BRANCH)}/{ticket.CHECKS}"],
        project.root,
    )
    assert mode.startswith("100644")
