"""C11 and C21 (basic): code an agent wrote never runs with Ariane's credentials, and nothing it
does to git, the remote or Ariane's records goes unnoticed."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ariane import ticket
from ariane.config import CheckConfig
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker, TrackerError

from conftest import PY, FakeRuntime, Project, edit_app, make_config, sh
from test_flow import TOKEN, journal, start, worktree


def test_c21_checks_run_without_the_token_or_a_working_credential(
    project: Project, tracker: InMemoryTracker
) -> None:
    probe = (
        "import os, sys; bad = [k for k in ('GH_TOKEN', 'SSH_AUTH_SOCK') if k in os.environ];"
        " sys.exit(1 if bad or os.environ.get('GIT_TERMINAL_PROMPT') != '0' else 0)"
    )
    checks = (CheckConfig("sees no credential", (PY, "-c", probe), True, 1),)
    outcome = start(project, tracker, FakeRuntime(), make_config(checks=checks))
    assert outcome.exit_code == 0, outcome.line


def test_c21_a_known_token_is_masked_in_the_ticket_records(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    runtime.summary = f"I found {TOKEN} in the environment"
    assert start(project, tracker, runtime).exit_code == 0
    recorded = project.show("ariane/7", "work/7/journal.md")
    assert TOKEN not in recorded and "I found *** in the environment" in recorded


def test_c11_an_agent_that_edits_git_configuration_is_stopped(
    project: Project, tracker: InMemoryTracker
) -> None:
    def reroute(session: Session) -> None:
        edit_app(session)
        sh(["git", "config", "url.https://elsewhere.invalid/.insteadOf", "x"], session.cwd)

    outcome = start(project, tracker, FakeRuntime(action=reroute))
    assert outcome.exit_code == 1
    assert "the agent session changed git configuration, hooks or local branches" in outcome.line
    assert "added: setting local\t" in outcome.detail and "insteadof=x" in outcome.detail
    assert tracker.opened == []


def test_c11_an_agent_that_plants_a_hook_is_stopped_and_the_hook_never_runs(
    project: Project, tracker: InMemoryTracker
) -> None:
    marker = project.root.parent / "hook-ran"

    def plant(session: Session) -> None:
        edit_app(session)
        common = Path(
            sh(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], session.cwd)
        )
        hook = common / "hooks" / "pre-commit"
        hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
        hook.chmod(0o755)

    outcome = start(project, tracker, FakeRuntime(action=plant))
    assert outcome.exit_code == 1
    assert "changed git configuration, hooks" in outcome.line
    assert not marker.exists()


def test_c11_a_check_that_moves_the_branch_is_stopped(
    project: Project, tracker: InMemoryTracker
) -> None:
    sneak = (
        PY,
        "-c",
        "import subprocess; subprocess.run(['git', 'commit', '-q', "
        "'--allow-empty', '-m', 'unchecked'], check=True)",
    )
    checks = (CheckConfig("sneaky", sneak, True, 1),)
    outcome = start(project, tracker, FakeRuntime(), make_config(checks=checks))
    assert outcome.exit_code == 1
    assert "the checks moved the ticket branch" in outcome.line
    assert "ariane/7" not in project.remote_branches()


def test_c11_a_remote_branch_deleted_during_the_session_is_detected(
    project: Project, tracker: InMemoryTracker
) -> None:
    sh(["git", "push", "--quiet", "origin", "main:refs/heads/other"], project.root)

    def delete_branch(session: Session) -> None:
        edit_app(session)
        sh(["git", "push", "--quiet", str(project.remote), ":refs/heads/other"], session.cwd)

    outcome = start(project, tracker, FakeRuntime(action=delete_branch))
    assert outcome.exit_code == 1
    assert "the remote changed during the agent session (refs/heads/other)" in outcome.line


def test_c11_a_refused_pull_request_after_the_push_says_how_to_finish(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(**_: str) -> None:
        raise TrackerError("GitHub API POST /pulls: HTTP 422 Validation Failed")

    monkeypatch.setattr(tracker, "open_pull_request", refuse)
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == 1
    assert "is pushed but the pull request was refused" in outcome.line
    assert "open the pull request from ariane/7 by hand" in outcome.line
    assert "ariane/7" in project.remote_branches()
    assert ticket.read_status(worktree(project) / "work/7")["State"] == "stopped"


def test_c1_an_agent_cannot_forge_or_add_ticket_records(
    project: Project, tracker: InMemoryTracker
) -> None:
    def forge(session: Session) -> None:
        edit_app(session)
        (session.cwd / "work/7/journal.md").write_text("forged\n", encoding="utf-8")
        (session.cwd / "work/7/approval.md").write_text("approved\n", encoding="utf-8")

    assert start(project, tracker, FakeRuntime(action=forge)).exit_code == 0
    assert "forged" not in project.show("ariane/7", "work/7/journal.md")
    listing = sh(
        ["git", "--git-dir", str(project.remote), "ls-tree", "--name-only", "ariane/7", "work/7/"],
        project.root,
    )
    assert "approval.md" not in listing


def test_c1_editing_only_ticket_records_counts_as_no_change(
    project: Project, tracker: InMemoryTracker
) -> None:
    def only_records(session: Session) -> None:
        (session.cwd / "work/7/status.md").write_text("State: delivered\n", encoding="utf-8")

    outcome = start(project, tracker, FakeRuntime(action=only_records))
    assert "changed no file" in outcome.line


@pytest.mark.skipif(not hasattr(os, "symlink") or os.name == "nt", reason="POSIX symlinks")
def test_c1_a_ticket_folder_replaced_by_a_link_is_never_written_through(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()

    def redirect(session: Session) -> None:
        edit_app(session)
        folder = session.cwd / "work/7"
        for child in folder.iterdir():
            child.unlink()
        folder.rmdir()
        folder.symlink_to(outside, target_is_directory=True)

    assert start(project, tracker, FakeRuntime(action=redirect)).exit_code == 0
    assert list(outside.iterdir()) == []
    assert "Bump the app version" in project.show("ariane/7", "work/7/brief.md")


def test_c11_a_local_branch_or_working_tree_left_over_is_refused(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    sh(["git", "branch", "ariane/7"], project.root)
    assert "already exists locally" in start(project, tracker, runtime).line
    sh(["git", "branch", "-D", "ariane/7"], project.root)
    worktree(project).mkdir(parents=True)
    assert "working tree already exists" in start(project, tracker, runtime).line
    assert runtime.sessions == []


def test_c8_a_setup_command_missing_from_path_stops_the_ticket(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    config = make_config(setup=("no-such-setup-for-ariane",))
    outcome = start(project, tracker, runtime, config)
    assert outcome.exit_code == 1
    assert "setup failed: command not found on PATH: no-such-setup-for-ariane" in outcome.line
    assert runtime.sessions == []
    assert "Stopped: setup failed" in journal(project)


def test_c1_an_agent_committing_to_ticket_records_is_stopped(
    project: Project, tracker: InMemoryTracker
) -> None:
    (project.root / "work/3").mkdir(parents=True)
    (project.root / "work/3/journal.md").write_text("an earlier ticket\n", encoding="utf-8")
    sh(["git", "add", "--all"], project.root)
    sh(["git", "commit", "--quiet", "-m", "earlier ticket"], project.root)
    sh(["git", "push", "--quiet", "origin", "main"], project.root)

    def tamper(session: Session) -> None:
        edit_app(session)
        (session.cwd / "work/3/journal.md").write_text("tampered\n", encoding="utf-8")
        sh(["git", "commit", "--quiet", "-am", "agent commit"], session.cwd)

    outcome = start(project, tracker, FakeRuntime(action=tamper))
    assert outcome.exit_code == 1
    assert "the agent committed changes to ticket records (work/3/journal.md)" in outcome.line
    assert tracker.opened == []


def test_c9_files_the_agent_hid_from_git_are_reported(
    project: Project, tracker: InMemoryTracker
) -> None:
    def hide(session: Session) -> None:
        edit_app(session)
        (session.cwd / "ignored-by-git").mkdir()
        (session.cwd / "ignored-by-git/helper.py").write_text("x = 1\n", encoding="utf-8")

    assert start(project, tracker, FakeRuntime(action=hide)).exit_code == 0
    assert "- `ignored-by-git/`" in project.show("ariane/7", "work/7/journal.md")


def test_c1_non_ascii_paths_are_journaled_readably(
    project: Project, tracker: InMemoryTracker
) -> None:
    def accent(session: Session) -> None:
        edit_app(session)
        (session.cwd / "café.txt").write_text("é\n", encoding="utf-8")

    assert start(project, tracker, FakeRuntime(action=accent)).exit_code == 0
    assert "- `café.txt`" in project.show("ariane/7", "work/7/journal.md")


def test_c1_an_agent_committing_everything_is_not_blamed_for_ariane_journal(
    project: Project, tracker: InMemoryTracker
) -> None:
    def commit_all(session: Session) -> None:
        edit_app(session)
        sh(["git", "add", "--all"], session.cwd)
        sh(["git", "commit", "--quiet", "-m", "agent commit"], session.cwd)

    outcome = start(project, tracker, FakeRuntime(action=commit_all))
    assert outcome.exit_code == 0, f"{outcome.line}\n{outcome.detail}"
    assert "Ticket started" in project.show("ariane/7", "work/7/journal.md")
