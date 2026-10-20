"""`ariane update <n>` refuses a ticket folder it would not keep whole (C11, ADR 0033)."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_c11_update import delivered, head, move_base, pushes, run_update  # noqa: F401 (fixture)

from ariane.tracker import InMemoryTracker

from conftest import Project, sh
from test_flow import worktree


@pytest.mark.parametrize("tracked", [True, False], ids=["committed", "ignored"])
def test_c11_update_refuses_a_folder_in_the_records_and_keeps_it(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],  # noqa: F811
    tracked: bool,
) -> None:
    runtime = delivered(project, tracker, pushes)
    move_base(project, {"other.txt": "x\n"})
    tree = worktree(project)
    nested = tree / "work" / "7" / "attachments"
    nested.mkdir()
    (nested / "evidence.md").write_text("kept\n", encoding="utf-8")
    if tracked:
        sh(["git", "add", "work/7/attachments"], tree)
        sh(["git", "commit", "--quiet", "-m", "evidence"], tree)
    else:
        exclude = Path(sh(["git", "rev-parse", "--git-path", "info/exclude"], tree))
        exclude = exclude if exclude.is_absolute() else tree / exclude
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text("work/7/attachments/\n", encoding="utf-8")
    local = head(project)
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1, outcome.line
    assert "work/7/ holds attachments, which are not plain record files" in outcome.line
    assert (nested / "evidence.md").read_text(encoding="utf-8") == "kept\n"
    assert head(project) == local and pushes == [] and runtime.sessions == []
