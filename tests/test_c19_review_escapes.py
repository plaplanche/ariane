"""C10, C19: `ariane report` counts review escapes per model pair and stopped tickets per
category (ADR 0058)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_fix_rounds import NO_GO

from ariane import report
from ariane.runtime import Session, StopReason
from ariane.tracker import InMemoryTracker, PullRequestState

from conftest import PY, FakeRuntime, Project, make_config, sh
from test_flow import start, worktree

OPENED = "2026-10-01T10:00:00Z"


def put(root: Path, number: int, **kw: Any) -> None:
    """A delivered ticket whose implementer is `implementer` and whose one review is `verdict`
    by `reviewer` on `runtime`."""
    review = {
        "role": "reviewer",
        "model": kw.pop("reviewer", "rev-a"),
        "runtime": kw.pop("runtime", "codex"),
        "verdict": kw.pop("verdict", "go"),
        "findings": kw.pop("findings", 0),
    }
    data = {
        "ticket": number,
        "mode": "delivered",
        "started": f"2026-10-01T09:00:{number % 60:02d}Z",
        "sessions": [{"role": "implementer", "model": kw.pop("implementer", "imp")}, review],
        "rounds": 0,
        "first_pass_verdict": review["verdict"],
        "outcome": "delivered",
    } | kw
    path = root / f"work/{number}/metrics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def pull(number: int, ended: str = "", merged: bool = False) -> PullRequestState:
    return PullRequestState(OPENED, ended, merged, number=number)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    return path


def lines(root: Path, tracker: InMemoryTracker | None) -> list[str]:
    return report.build(root, None, tracker).lines


def escapes_line(out: list[str], reviewer: str = "rev-a") -> str:
    found = [line for line in out if line.startswith("Review escapes, ") and reviewer in line]
    assert len(found) == 1, out
    return found[0]


def test_c19_review_escapes_each_wrong_go_counts_once_a_merge_does_not(root: Path) -> None:
    tracker = InMemoryTracker()
    put(root, 1, ci_failures=["tests"])  # red CI on the reviewed head
    tracker.pull_states["ariane/1"] = pull(101, "2026-10-02T00:00:00Z", merged=True)
    put(root, 2)  # a human asked for changes
    tracker.pull_states["ariane/2"] = pull(102, "2026-10-02T00:00:00Z", merged=True)
    tracker.changes_requested_on.add(102)
    put(root, 3)  # closed without merge
    tracker.pull_states["ariane/3"] = pull(103, "2026-10-02T00:00:00Z")
    put(root, 4, ci_failures=[])  # green CI, merged
    tracker.pull_states["ariane/4"] = pull(104, "2026-10-02T00:00:00Z", merged=True)
    put(root, 5, ci_failures=[])  # still open, nothing against it
    tracker.pull_states["ariane/5"] = pull(105)
    put(root, 6, verdict="no-go", findings=3, outcome="needs a human", category="review")
    tracker.pull_states["ariane/6"] = pull(106, "2026-10-02T00:00:00Z")  # not a go: not counted
    line = escapes_line(lines(root, tracker))
    assert "6 reviews over 6 tickets, 5 go, 0.5 findings per review, 3 escapes" in line
    assert "escape rate 3/5 (60%) over 5 tickets" in line


def test_c19_review_escapes_grouped_per_pair_and_runtime_no_rate_below_5(root: Path) -> None:
    tracker = InMemoryTracker()
    for n in range(1, 6):  # five tickets reviewed by rev-a on codex, one closed unmerged
        put(root, n)
        tracker.pull_states[f"ariane/{n}"] = pull(100 + n, "2026-10-02T00:00:00Z", n != 1)
    for n in range(6, 11):  # five reviewed by the implementer's own model, all merged
        put(root, n, reviewer="imp", runtime="claude-code")
        tracker.pull_states[f"ariane/{n}"] = pull(100 + n, "2026-10-02T00:00:00Z", True)
    for n in range(11, 15):  # four on another runtime: no rate
        put(root, n, runtime="pi")
        tracker.pull_states[f"ariane/{n}"] = pull(100 + n, "2026-10-02T00:00:00Z", True)
    out = lines(root, tracker)
    found = [line for line in out if line.startswith("Review escapes, ")]
    assert len(found) == 3, out
    assert any(
        "reviewer rev-a (codex)" in x and "escape rate 1/5 (20%) over 5 tickets" in x for x in found
    )
    assert any(
        "reviewer imp (claude-code)" in x and "escape rate 0/5 (0%) over 5 tickets" in x
        for x in found
    )
    assert any(
        "reviewer rev-a (pi)" in x and "escape rate not shown (4 tickets, fewer than 5)" in x
        for x in found
    )
    compared = [line for line in out if line.startswith("Escape rates compared: ")]
    assert compared == [
        "Escape rates compared: imp / imp (claude-code) 0% over 5 tickets;"
        " imp / rev-a (codex) 20% over 5 tickets."
    ]


def test_c19_review_escapes_without_ci_data_the_ci_part_is_skipped_and_said(root: Path) -> None:
    tracker = InMemoryTracker(pull_states={"ariane/1": pull(101, "2026-10-02T00:00:00Z", True)})
    put(root, 1)
    out = lines(root, tracker)
    assert "escape rate not shown (1 tickets, fewer than 5)" in escapes_line(out)
    assert any(line.startswith("Review escapes: CI not read") for line in out)
    put(root, 1, ci_failures=[])
    assert not any("CI not read" in line for line in lines(root, tracker))


def test_c19_review_escapes_without_tracker_nothing_is_counted_and_said(root: Path) -> None:
    put(root, 1, ci_failures=["tests"])
    out = lines(root, None)
    assert "0 escapes, escape rate not shown (0 tickets" in escapes_line(out)
    assert "Review escapes: tracker not available; escapes not counted." in out
    assert "Review escapes: tracker not available; escapes not counted." in lines(
        root, InMemoryTracker(unreachable=True)
    )


def test_c19_review_escapes_report_counts_categories_per_model(root: Path) -> None:
    put(root, 1)
    put(root, 2, outcome="stopped", category="guard")
    put(root, 3, outcome="stopped", category="guard", implementer="other")
    put(root, 4, outcome="needs a human", category="review", verdict="no-go")
    put(root, 5, outcome="stopped")  # recorded before categories existed
    out = lines(root, None)
    assert "Stopped by category: guard 2, review 1, not recorded 1 over 4 tickets." in out
    assert "Stopped by category, implementer imp: guard 1, review 1, not recorded 1." in out
    assert "Stopped by category, implementer other: guard 1." in out


def metrics(project: Project) -> dict[str, Any]:
    data = json.loads((worktree(project) / "work/7/metrics.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def switch_branch(session: Session) -> None:
    (session.cwd / "app.txt").write_text("version 2\n", encoding="utf-8")
    sh(["git", "checkout", "-q", "-b", "elsewhere"], session.cwd)


def red_check(session: Session) -> None:
    (session.cwd / "app.txt").write_text("v3\n", encoding="utf-8")


def test_c19_review_escapes_a_green_delivery_records_no_category_and_its_verdict(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert start(project, tracker, FakeRuntime()).exit_code == 0
    data = metrics(project)
    assert "category" not in data
    reviewer = data["sessions"][-1]
    assert (reviewer["verdict"], reviewer["findings"]) == ("go", 0)


@pytest.mark.parametrize(
    ("runtime", "config", "outcome", "category"),
    [
        (FakeRuntime(action=lambda s: None), None, "stopped", "spec"),
        (FakeRuntime(action=switch_branch), None, "stopped", "guard"),
        (FakeRuntime(stop_reason=StopReason.BUDGET), None, "stopped", "budget"),
        (FakeRuntime(stop_reason=StopReason.TIMEOUT), None, "stopped", "budget"),
        (FakeRuntime(stop_reason=StopReason.ERROR), None, "stopped", "runtime"),
        (FakeRuntime(answers=["not json"]), None, "needs a human", "runtime"),
        (
            FakeRuntime(action=red_check),
            None,
            "stopped",
            "checks",
        ),
        (FakeRuntime(answers=[NO_GO]), None, "needs a human", "review"),
        (
            FakeRuntime(),
            make_config(setup=(PY, "-c", "import sys; sys.exit(3)")),
            "stopped",
            "infra",
        ),
    ],
    ids=["spec", "guard", "budget", "timeout", "runtime", "invalid-review", "checks", "review",
         "infra"],
)  # fmt: skip
def test_c19_review_escapes_each_stop_path_of_start_records_its_category(
    project: Project,
    tracker: InMemoryTracker,
    runtime: FakeRuntime,
    config: Any,
    outcome: str,
    category: str,
) -> None:
    assert start(project, tracker, runtime, config).exit_code != 0
    data = metrics(project)
    assert (data["outcome"], data["category"]) == (outcome, category)
    if category == "review":
        assert {(s["verdict"], s["findings"]) for s in data["sessions"] if "verdict" in s} == {
            ("no-go", 1)
        }
