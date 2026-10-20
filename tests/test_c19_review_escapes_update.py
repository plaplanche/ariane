"""C19: each stop path of `ariane update` records its category in `metrics.json` (ADR 0058)."""

from __future__ import annotations

import json

import pytest
from test_c11_update import delivered, move_base, pushes, run_update  # noqa: F401 (fixture)
from test_fix_rounds import NO_GO

from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project
from test_flow import worktree


@pytest.mark.parametrize(
    ("files", "answers", "category"),
    [
        ({"app.txt": "version 3\n"}, [], "merge"),  # a conflict with the ticket's change
        ({"broken.txt": "the base broke it\n"}, [], "checks"),  # red after the merge
        ({"other.txt": "x\n"}, [NO_GO], "review"),  # the update's review is no-go
    ],
    ids=["merge", "checks", "review"],
)
def test_c19_review_escapes_each_stop_path_of_update_records_its_category(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],  # noqa: F811
    files: dict[str, str],
    answers: list[str],
    category: str,
) -> None:
    delivered(project, tracker, pushes)
    move_base(project, files)
    outcome = run_update(project, tracker, FakeRuntime(answers=answers))
    assert outcome.exit_code == 1, outcome.line
    data = json.loads((worktree(project) / "work/7/metrics.json").read_text(encoding="utf-8"))
    assert (data["outcome"], data["category"]) == ("needs a human", category)
