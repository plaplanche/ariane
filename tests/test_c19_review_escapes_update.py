"""C19: each stop path of `ariane update` records its category in `metrics.json` (ADR 0058)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_c11_update import delivered, move_base, pushes, run_update  # noqa: F401 (fixture)
from test_fix_rounds import NO_GO

from ariane import metrics, update
from ariane.stop import Stop
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
    gos = [s for s in data["sessions"] if s["role"] == "reviewer" and s.get("verdict") == "go"]
    assert gos[0]["pushed"] is True  # the delivery's go stays pushed, whatever the update did


def test_c19_review_escapes_an_update_failing_before_its_run_records_infra_apart(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delivered(project, tracker, pushes)
    move_base(project, {"other.txt": "x\n"})
    record = worktree(project) / "work/7/metrics.json"
    before = record.read_text(encoding="utf-8")

    def held(*args: Any) -> Any:
        raise Stop("ticket #7 is running in another Ariane process", "wait")

    monkeypatch.setattr(update, "locked", held)
    assert run_update(project, tracker, FakeRuntime()).exit_code == 1
    kept = project.root.parent / f"{project.root.name}.ariane" / "stopped/7/refused"
    found = [json.loads(p.read_text(encoding="utf-8")) for p in kept.glob("*/metrics.json")]
    assert [(d["outcome"], d["category"]) for d in found] == [("stopped", "infra")]
    assert record.read_text(encoding="utf-8") == before  # the delivery's record untouched


def test_c19_review_escapes_a_verification_refused_before_its_commit_is_not_pushed(
    tmp_path: Path,
) -> None:
    measured = metrics.Metrics(7, "verify", lambda _: None)
    measured.sessions.append({"role": "reviewer", "model": "rev", "runtime": "codex"})
    measured.reviewed(True)
    measured.finish("delivered")
    assert measured.sessions[-1]["pushed"] is True  # its branch is the one pushed and merged
    measured.keep_stopped(tmp_path / "metrics.json", "guard")
    kept = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert "pushed" not in kept["sessions"][-1] and kept["category"] == "guard"
