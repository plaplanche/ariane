"""C10, C19: fix rounds and reviewers see the earlier rounds; a draft says when they circled."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_fix_rounds import NO_GO, implementers, reviewers

from ariane import cli, context, git, review
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, go_answer
from test_flow import start, worktree


def finding(title: str, line: int = 1) -> dict[str, Any]:
    detail = f"Detail of {title}."
    return {
        "severity": "blocking",
        "file": "app.txt",
        "line": line,
        "title": title,
        "detail": detail,
    }


def no_go(title: str, line: int, *earlier: tuple[str, str, list[int]]) -> dict[str, Any]:
    key = {"replaced": "caused", "still open": "current"}
    entries = [{"finding": f, "answer": a} | ({key[a]: c} if c else {}) for f, a, c in earlier]
    return {**NO_GO, "findings": [finding(title, line)], "earlier": entries}


# Round 0 finds a split write; round 1's fix moved it (replaced); round 2's fix broke the other
# writes (replaced again) and round 1's finding is still open: one recurring finding, 2.1.
CIRCLING = [
    no_go("Check-then-write split", 1),
    no_go("Write moved, race left", 2, ("0.1", "replaced", [0])),
    no_go(
        "Intermediate state breaks writes",
        3,
        ("0.1", "replaced", [0]),
        ("1.1", "still open", [0]),
    ),
]


def envelope(prompt: str, kind: str) -> str:
    return prompt.partition(f'<untrusted-ticket kind="{kind}">')[2].partition(
        "</untrusted-ticket>"
    )[0]


def metrics(project: Project) -> dict[str, Any]:
    data = json.loads(project.show("ariane/7", "work/7/metrics.json"))
    assert isinstance(data, dict)
    return data


def test_c10_fix_history_round_two_fix_prompt_lists_rounds_zero_and_one(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime(answers=CIRCLING)
    start(project, tracker, runtime)
    first, round_one, round_two = implementers(runtime)
    assert context.RECHECK_RULE not in first.prompt
    assert context.RECHECK_RULE in round_one.prompt
    assert context.RECHECK_RULE in round_two.prompt
    data = envelope(round_two.prompt, "findings")
    assert "round 0 (`app.txt:1`): Check-then-write split" in data
    assert "Findings of round 1, the last review, in full:" in data
    assert (
        "- blocking (app.txt:2) Write moved, race left: Detail of Write moved, race left." in data
    )
    assert data.index("round 0") < data.index("round 1")
    assert "Intermediate state" not in data  # round 2's review comes after this fix
    assert context.RECHECK_RULE not in data
    assert "Blocking findings of the earlier rounds" not in envelope(round_one.prompt, "findings")


def test_c10_fix_history_round_one_reviewer_prompt_lists_round_zero_and_parses_earlier(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime(answers=CIRCLING)
    start(project, tracker, runtime)
    zero, one, two = reviewers(runtime)
    assert 'kind="earlier-findings"' not in zero.prompt
    assert envelope(one.prompt, "earlier-findings").strip() == (
        "- 0.1: round 0 (`app.txt:1`): Check-then-write split"
    )
    assert "- 1.1: round 1 (`app.txt:2`): Write moved, race left" in envelope(
        two.prompt, "earlier-findings"
    )
    parsed = review.parse(CIRCLING[2])
    assert [(e.finding, e.answer, e.caused, e.current) for e in parsed.earlier] == [
        ("0.1", "replaced", (0,), ()),
        ("1.1", "still open", (), (0,)),
    ]
    record = project.show("ariane/7", "work/7/review-1.md")
    assert "- 0.1: replaced, caused findings 0" in record


@pytest.mark.parametrize(
    ("earlier", "error"),
    [
        ([{"finding": "0.1", "answer": "maybe"}], "earlier[0].answer: expected one of"),
        ([], "earlier: no answer for finding 0.1"),
        ([{"finding": "0.2", "answer": "fixed"}], "unknown earlier finding '0.2'"),
        ([{"finding": "0.1", "answer": "replaced"}], "names the findings it caused"),
        ([{"finding": "0.1", "answer": "replaced", "caused": [3]}], "indexes of blocking"),
        ([{"finding": "0.1", "answer": "still open"}], "names the findings it is now"),
        ([{"finding": "0.1", "answer": "fixed", "current": [0]}], "only a still open finding"),
        (None, "earlier: missing"),
    ],
)
def test_c10_fix_history_unknown_answer_or_missing_entry_is_refused(
    earlier: list[dict[str, Any]] | None, error: str
) -> None:
    answer = {**go_answer(), "findings": [finding("New")]}
    if earlier is not None:
        answer["earlier"] = earlier
    found = review.validate(answer, ["0.1"])
    assert any(error in e for e in found), found


def test_c10_fix_history_round_zero_answer_without_earlier_is_accepted(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert review.validate(go_answer()) == []
    assert review.parse(go_answer()).earlier == ()
    assert review.validate({**go_answer(), "earlier": [{"finding": "0.1", "answer": "fixed"}]})
    assert start(project, tracker, FakeRuntime()).exit_code == 0
    assert '"earlier"' in json.dumps(review.SCHEMA["properties"])


def test_c10_fix_history_circled_rounds_are_said_in_the_draft_journal_and_metrics(
    project: Project, tracker: InMemoryTracker
) -> None:
    outcome = start(project, tracker, FakeRuntime(answers=CIRCLING))
    assert outcome.exit_code == 1
    body = tracker.opened[0]["body"]
    assert tracker.opened[0]["draft"] is True
    assert "circled on the same design question" in body
    assert body.index("circled on the same design question") < body.index("## Review")
    assert (
        "- round 0 (`app.txt:1`): Check-then-write split → round 1 (`app.txt:2`): Write moved,"
        " race left → round 2 (`app.txt:3`): Intermediate state breaks writes → still open in"
        " round 2"
    ) in body
    journal = (worktree(project) / "work/7/journal.md").read_text(encoding="utf-8")
    assert "Review circled on `app.txt`" in journal
    assert metrics(project)["recurring_findings"] == 1


def test_c10_fix_history_still_open_blocker_cannot_pass_as_go() -> None:
    contradictory = {**go_answer(), "earlier": [{"finding": "0.1", "answer": "still open"}]}
    assert any("names the findings it is now" in e for e in review.validate(contradictory, ["0.1"]))
    named = {
        **contradictory,
        "earlier": [{"finding": "0.1", "answer": "still open", "current": [0]}],
    }
    assert any("indexes of blocking findings" in e for e in review.validate(named, ["0.1"]))


def test_c10_fix_history_one_blocker_through_three_rounds_counts_once(
    project: Project, tracker: InMemoryTracker
) -> None:
    same = [
        no_go("Race on the lease", 1),
        no_go("Race on the lease", 1, ("0.1", "still open", [0])),
        no_go("Race on the lease", 1, ("0.1", "still open", [0]), ("1.1", "still open", [0])),
    ]
    assert start(project, tracker, FakeRuntime(answers=same)).exit_code == 1
    body = tracker.opened[0]["body"]
    step = "round {} (`app.txt:1`): Race on the lease"
    chain = " → ".join(step.format(n) for n in range(3)) + " → still open in round 2"
    assert f"- {chain}\n" in body
    assert body.count(" → still open in round 2") == 1
    assert metrics(project)["recurring_findings"] == 1


def test_c10_fix_history_rounds_that_fixed_everything_have_none(
    project: Project, tracker: InMemoryTracker
) -> None:
    fixed = [
        no_go("A", 1),
        no_go("B", 2, ("0.1", "fixed", [])),
        no_go("C", 3, ("0.1", "fixed", []), ("1.1", "fixed", [])),
    ]
    assert start(project, tracker, FakeRuntime(answers=fixed)).exit_code == 1
    assert "circled" not in tracker.opened[0]["body"]
    journal = (worktree(project) / "work/7/journal.md").read_text(encoding="utf-8")
    assert "Review circled" not in journal
    assert metrics(project)["recurring_findings"] == 0


def test_c10_fix_history_report_shows_recurring_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(git, "repo_root", lambda _p: tmp_path)
    data = {
        "ticket": 9,
        "mode": "delivered",
        "started": "2026-10-01T10:00:00Z",
        "sessions": [{"cost_usd": 1.0, "duration_s": 60}],
        "rounds": 2,
        "first_pass_verdict": "no-go",
        "outcome": "needs a human",
        "recurring_findings": 2,
    }
    path = tmp_path / "work/9/metrics.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert cli.main(["report"]) == 0
    row = capsys.readouterr().out.splitlines()[0]
    assert row.startswith("#9 delivered needs a human")
    assert ", first pass no-go, recurring_findings 2" in row
    path.write_text(json.dumps(data | {"recurring_findings": "two"}), encoding="utf-8")
    assert cli.main(["report"]) == 1
    assert "recurring_findings is not an integer" in capsys.readouterr().out
