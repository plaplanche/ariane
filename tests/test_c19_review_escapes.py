"""C10, C19: `ariane report` counts review escapes per model pair and stopped tickets per
category (ADR 0058)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_fix_rounds import NO_GO

from ariane import flow, report
from ariane.runtime import Session, StopReason
from ariane.stop import Stop
from ariane.tracker import InMemoryTracker, IssueRefused, PullRequestState

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
        "at": kw.pop("at", None),  # None: a record from before the verdict's time
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
    path = root / kw.pop("path", f"work/{number}") / "metrics.json"
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
    tracker.changes_requested_on[102] = "2026-10-02T00:00:00Z"
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


def test_c19_review_escapes_only_what_follows_the_go_counts(root: Path) -> None:
    tracker = InMemoryTracker()
    go = "2026-10-05T12:00:00Z"
    put(root, 1, at=go)  # changes requested before the go, fixed, then the go: no escape
    tracker.pull_states["ariane/1"] = pull(101, "2026-10-06T00:00:00Z", merged=True)
    tracker.changes_requested_on[101] = "2026-10-04T08:00:00Z"
    put(root, 2, at=go)  # changes requested after the go: an escape
    tracker.pull_states["ariane/2"] = pull(102, "2026-10-06T00:00:00Z", merged=True)
    tracker.changes_requested_on[102] = "2026-10-05T13:00:00Z"
    put(root, 3, at=go)  # closed without merge before the go: not this go's escape
    tracker.pull_states["ariane/3"] = pull(103, "2026-10-05T11:00:00Z")
    assert "2 escapes" not in escapes_line(lines(root, tracker))
    assert ", 1 escapes, " in escapes_line(lines(root, tracker))


def test_c19_review_escapes_a_ticket_counts_once_toward_the_threshold(root: Path) -> None:
    tracker = InMemoryTracker()
    for k in range(5):  # five takeover records of ticket 7, on five branches, all escaped
        put(root, 7, path=f"work/verify/ariane/7-{k}", outcome="delivered")
        tracker.pull_states[f"ariane/7-{k}"] = pull(170 + k, "2026-10-02T00:00:00Z")
    line = escapes_line(lines(root, tracker))
    assert "1 escapes, escape rate not shown (1 tickets, fewer than 5)" in line


def test_c19_review_escapes_report_reads_the_stops_kept_outside_the_repository(
    root: Path,
) -> None:
    kept = root.parent / f"{root.name}.ariane"
    put(kept, 7, path="stopped/7", outcome="stopped", category="infra")
    put(kept, 8, path="stopped/8/refused/2026-10-01T090000Z-1", outcome="stopped", category="spec")
    put(kept, 9, path="verify/ariane-9", outcome="stopped", category="checks")
    out = lines(root, None)
    assert "Stopped by category: spec 1, checks 1, infra 1 over 3 tickets." in out


def test_c19_review_escapes_a_refusal_in_a_runs_second_is_its_own_record(root: Path) -> None:
    """A start refused on the lock while another run of the ticket starts, in the same second:
    the same `started`, yet neither record replaces the other."""
    kept = root.parent / f"{root.name}.ariane"
    put(root, 7)  # the run, merged
    put(kept, 7, path="worktrees/7/work/7")  # the same run, in its worktree
    put(kept, 7, path="stopped/7/refused/2026-10-01T090007Z-a", outcome="stopped", category="infra")
    out = lines(root, None)
    assert "Stopped by category: infra 1 over 1 tickets." in out
    assert "Reported 2 tickets. Next: nothing." in out


def refused(project: Project) -> list[dict[str, Any]]:
    kept = project.root.parent / f"{project.root.name}.ariane" / "stopped/7/refused"
    found = [json.loads(p.read_text(encoding="utf-8")) for p in kept.glob("*/metrics.json")]
    return [d for d in found if isinstance(d, dict)]


def test_c19_review_escapes_a_start_refused_before_its_run_records_its_category(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = tracker.read_issue

    def gated(number: int) -> Any:
        raise IssueRefused("issue #7 is not labelled `ariane`")

    monkeypatch.setattr(tracker, "read_issue", gated)
    assert start(project, tracker, FakeRuntime()).exit_code == 2

    def interrupted(number: int) -> Any:
        raise KeyboardInterrupt

    monkeypatch.setattr(tracker, "read_issue", interrupted)
    assert start(project, tracker, FakeRuntime()).exit_code == 130
    monkeypatch.setattr(tracker, "read_issue", real)

    def held(*args: Any) -> Any:
        raise Stop("ticket #7 is running in another Ariane process", "wait")

    monkeypatch.setattr(flow, "locked", held)
    assert start(project, tracker, FakeRuntime()).exit_code == 1
    found = refused(project)
    assert sorted((d["outcome"], d["category"]) for d in found) == [
        ("stopped", "infra"),  # Ctrl-C during the issue's read
        ("stopped", "infra"),  # the lock
        ("stopped", "spec"),  # the issue gate
    ]
    assert not (worktree(project) / "work/7/metrics.json").exists()  # no run's file touched


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
