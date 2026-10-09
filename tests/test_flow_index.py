"""Ariane commits only the paths it means to commit, never the whole index (C9, C11)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ariane import git
from ariane.config import CheckConfig
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import PY, FakeRuntime, Project, make_config, sh
from test_flow import start, worktree

STAGE_EVIL = """
import subprocess, sys
open("evil.py", "w").write("print('never replayed')\\n")
subprocess.run(["git", "-C", sys.argv[1], "add", "evil.py"], check=True)
"""


def test_c11_index_a_file_staged_by_a_check_is_not_in_the_delivered_commit(
    project: Project, tracker: InMemoryTracker
) -> None:
    ticket_tree = worktree(project)
    # The check runs in the replay; the file it writes must exist in the ticket tree to be staged.
    script = STAGE_EVIL.replace('open("evil.py", "w")', f'open(r"{ticket_tree}/evil.py", "w")')
    stage = CheckConfig("stages a file", (PY, "-c", script, str(ticket_tree)), True, 1.0)
    outcome = start(project, tracker, FakeRuntime(), make_config(checks=(stage,)))
    assert outcome.exit_code == 0, outcome.line
    listing = sh(["git", "ls-tree", "-r", "--name-only", "ariane/7"], project.remote)
    assert "evil.py" not in listing.splitlines()
    assert "app.txt" in listing.splitlines()


def test_c11_index_a_staged_change_to_another_tickets_records_is_not_committed(
    project: Project, tracker: InMemoryTracker
) -> None:
    def stage_records(session: Session) -> None:
        (session.cwd / "app.txt").write_text("version 2\n", encoding="utf-8")
        other = session.cwd / "work/3"
        other.mkdir(parents=True)
        (other / "journal.md").write_text("forged\n", encoding="utf-8")
        sh(["git", "add", "work/3/journal.md"], session.cwd)

    outcome = start(project, tracker, FakeRuntime(action=stage_records))
    assert outcome.exit_code == 0, outcome.line
    listing = sh(["git", "ls-tree", "-r", "--name-only", "ariane/7"], project.remote)
    assert not [p for p in listing.splitlines() if p.startswith("work/3/")]


def test_c11_index_pre_push_check_stops_a_head_that_differs_from_the_replayed_commit(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = git.commit

    def commit_with_extra(cwd: Path, pathspec: list[str], message: str, **kwargs):  # type: ignore[no-untyped-def]
        if "record the checks" in message:
            (cwd / "evil.py").write_text("print('x')\n", encoding="utf-8")
            sh(["git", "add", "evil.py"], cwd)
            sh(["git", "commit", "--quiet", "-m", "extra"], cwd)
        return real(cwd, pathspec, message, **kwargs)

    monkeypatch.setattr(git, "commit", commit_with_extra)
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == 1
    assert "evil.py" in outcome.line
    assert "ariane/7" not in project.remote_branches()
    assert tracker.opened == []
