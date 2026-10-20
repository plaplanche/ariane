"""`ariane update <n>` refuses a ticket folder it would not keep whole (C11, ADR 0033)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_c11_update import delivered, head, move_base, pushes, run_update  # noqa: F401 (fixture)

from ariane import metrics
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


def test_c11_update_refuses_a_base_that_changes_the_tickets_records(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],  # noqa: F811
) -> None:
    runtime = delivered(project, tracker, pushes)
    move_base(project, {"work/7/evidence.md": "from the base\n"})
    local = head(project)
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1, outcome.line
    assert "origin/main changes the ticket's records (work/7/evidence.md)" in outcome.line
    assert head(project) == local and pushes == [] and runtime.sessions == []
    assert not (worktree(project) / "work" / "7" / "evidence.md").exists()


@pytest.mark.parametrize(
    "error", [PermissionError, KeyboardInterrupt], ids=["unreadable", "ctrl-c"]
)
def test_c11_update_a_failed_read_of_the_records_writes_and_removes_nothing(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    error: type[BaseException],
) -> None:
    runtime = delivered(project, tracker, pushes)
    move_base(project, {"other.txt": "x\n"})
    folder = worktree(project) / "work" / "7"
    (folder / "z-evidence.txt").write_text("ignored, kept\n", encoding="utf-8")
    exclude = Path(sh(["git", "rev-parse", "--git-path", "info/exclude"], worktree(project)))
    exclude = exclude if exclude.is_absolute() else worktree(project) / exclude
    exclude.write_text("work/7/z-evidence.txt\n", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    local = head(project)
    real = Path.read_text

    def failing(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name == "review-0.md":
            raise error()
        return real(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", failing)
    outcome = run_update(project, tracker, runtime)
    monkeypatch.setattr(Path, "read_text", real)
    assert outcome.exit_code in (1, 130) and "Did not update ticket #7" in outcome.line
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before
    assert head(project) == local and pushes == [] and runtime.sessions == []


@pytest.mark.parametrize(
    "text", ["not json", "[]", '{"steps": []}', '{"started": 1, "rounds": "x"}']
)
def test_c11_update_unreadable_metrics_are_left_out_whole(text: str) -> None:
    measured = metrics.Metrics(7, "delivered", lambda _: None)
    started = measured.started
    measured.resume(text)
    assert (measured.started, measured.steps, measured.sessions) == (started, [], [])
    assert (measured.rounds, measured.updates) == (0, 0)
