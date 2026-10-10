"""C10, C26: the review before delivery, on real git with a fake runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ariane import checks, flow, review
from ariane.claude_code import ClaudeCodeRuntime
from ariane.config import CheckConfig, Config, DoneItem
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import PY, FakeRuntime, Project, go_answer, make_config
from test_flow import start, worktree

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "claude_stream_review.jsonl"
BLOCKING = {
    "severity": "blocking",
    "file": "app.txt",
    "line": 1,
    "title": "Wrong value",
    "detail": "Because.",
}


def answer(**changes: Any) -> dict[str, Any]:
    return {**go_answer(), **changes}


def pull_body(tracker: InMemoryTracker) -> str:
    return tracker.opened[-1]["body"]


def test_c10_review_go_delivers_with_the_verdict_in_the_pull_request_body(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 0, outcome.line
    body = pull_body(tracker)
    assert "Verdict: **go**" in body
    assert "ariane/7" in project.remote_branches()


def test_c10_review_go_with_a_blocking_finding_is_no_go_and_nothing_is_pushed(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime(answers=[answer(findings=[BLOCKING])])
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "the review is no-go (1 blocking findings)" in outcome.line
    assert "ariane/7" not in project.remote_branches()
    assert tracker.opened == []
    status = (worktree(project) / "work/7/status.md").read_text(encoding="utf-8")
    assert "Last action: needs a human" in status
    assert "**no-go** (the reviewer answered go)" in (
        worktree(project) / "work/7/review-0.md"
    ).read_text(encoding="utf-8")


def test_c10_review_an_invalid_answer_is_retried_once_in_a_new_session(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime(answers=[{"verdict": "maybe"}, go_answer()])
    assert start(project, tracker, runtime).exit_code == 0
    reviewers = [s for s in runtime.sessions if s.role == "reviewer"]
    assert len(reviewers) == 2
    assert "verdict: expected one of go, no-go" in reviewers[1].prompt


def test_c10_review_a_second_invalid_answer_stops_the_ticket(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime(answers=["not json"])
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "invalid twice" in outcome.line
    assert len([s for s in runtime.sessions if s.role == "reviewer"]) == 2
    assert "ariane/7" not in project.remote_branches()


def test_c10_review_runs_in_the_replay_tree_with_read_only_tools(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    assert start(project, tracker, runtime).exit_code == 0
    session = next(s for s in runtime.sessions if s.role == "reviewer")
    assert session.cwd == worktree(project).with_name("7-replay")
    assert session.tools == ("Read", "Glob", "Grep")
    assert session.model == "test-reviewer"
    assert session.json_schema == review.SCHEMA
    assert '<untrusted-ticket number="7">' in session.prompt
    assert "+version 2" in session.prompt
    assert not session.cwd.exists()


def test_c10_review_a_reviewer_that_edits_a_file_is_stopped(
    project: Project, tracker: InMemoryTracker
) -> None:
    def edit(session: Session) -> None:
        (session.cwd / "app.txt").write_text("tampered\n", encoding="utf-8")

    runtime = FakeRuntime(review_actions=[edit])
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "the reviewer changed files" in outcome.line
    assert "ariane/7" not in project.remote_branches()


def test_c10_review_a_reviewer_that_adds_a_file_is_stopped(
    project: Project, tracker: InMemoryTracker
) -> None:
    def add(session: Session) -> None:
        (session.cwd / "new.txt").write_text("x\n", encoding="utf-8")

    outcome = start(project, tracker, FakeRuntime(review_actions=[add]))
    assert outcome.exit_code == 1
    assert "the reviewer changed files" in outcome.line


def test_c10_review_the_review_file_is_in_the_pushed_branch(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert start(project, tracker, FakeRuntime()).exit_code == 0
    text = project.show("ariane/7", "work/7/review-0.md")
    assert "- Reviewed commit: `" in text
    assert "- Verdict: **go**" in text
    assert "## Proposed learnings (not decided)" in text


def test_c10_review_the_review_file_is_redacted(project: Project, tracker: InMemoryTracker) -> None:
    token = "secret-token-for-tests"
    leak = answer(learnings=[f"the token is {token}"])
    assert start(project, tracker, FakeRuntime(answers=[leak])).exit_code == 0
    assert token not in project.show("ariane/7", "work/7/review-0.md")


def test_c10_review_a_failing_blocking_check_stops_before_any_review(
    project: Project, tracker: InMemoryTracker
) -> None:
    config = make_config(checks=(CheckConfig("fail", (PY, "-c", "raise SystemExit(1)"), True, 1),))
    runtime = FakeRuntime()
    assert start(project, tracker, runtime, config).exit_code == 1
    assert [s.role for s in runtime.sessions] == ["implementer"]


def test_c10_review_claude_code_recorded_session_gives_no_go_with_two_blocking_findings(
    tmp_path: Path,
) -> None:
    runtime = ClaudeCodeRuntime(
        (PY, str(HERE / "fake_claude.py"), "stream", str(FIXTURE), "-", "end", "--")
    )
    schema = review.SCHEMA
    session = Session(
        "reviewer", "m", ("Read",), 1, None, 30, tmp_path, "go", dict(os.environ), schema
    )
    assert "--json-schema" in runtime.command(session)
    result = runtime.run(session)
    assert review.validate(result.structured_output) == []
    parsed = review.parse(result.structured_output)
    assert parsed.verdict == "no-go"
    assert [f.severity for f in parsed.findings] == ["blocking", "blocking"]
    assert [d.met for d in parsed.definition_of_done] == [False]
    assert all(json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines())


def test_c10_review_validator_names_each_fault() -> None:
    bad = {"verdict": "go", "findings": [{"severity": "x", "line": "1"}], "learnings": [1], "z": 0}
    assert review.validate(bad) == [
        "answer.definition_of_done: missing",
        "answer.z: unknown key",
        "findings[0].file: missing",
        "findings[0].title: missing",
        "findings[0].detail: missing",
        "findings[0].severity: expected one of blocking, minor",
        "findings[0].line: expected an integer",
        "learnings[0]: expected a string",
    ]
    assert review.validate([]) == ["answer: expected an object"]


def with_items(items: tuple[DoneItem, ...]) -> Config:
    base = make_config()
    return Config(**{**base.__dict__, "definition_of_done": items})


SENTENCE = DoneItem(text="Docs are updated.")
CHECK = DoneItem(check="app has version 2")


def test_c26_dod_review_an_item_answered_unmet_makes_the_review_no_go(
    project: Project, tracker: InMemoryTracker
) -> None:
    unmet = answer(definition_of_done=[{"item": SENTENCE.text, "met": False, "evidence": "none"}])
    config = with_items((CHECK, SENTENCE))
    outcome = start(project, tracker, FakeRuntime(answers=[unmet]), config)
    assert outcome.exit_code == 1
    text = (worktree(project) / "work/7/review-0.md").read_text(encoding="utf-8")
    assert "**not met**: Docs are updated." in text
    assert "met: check app has version 2 passes" in text


def test_c26_dod_review_an_item_missing_from_the_answer_makes_the_review_no_go(
    project: Project, tracker: InMemoryTracker
) -> None:
    config = with_items((SENTENCE,))
    outcome = start(project, tracker, FakeRuntime(answers=[answer(definition_of_done=[])]), config)
    assert outcome.exit_code == 1
    text = (worktree(project) / "work/7/review-0.md").read_text(encoding="utf-8")
    assert "The reviewer did not answer this item." in text


def test_c26_dod_review_the_pull_request_body_and_file_list_every_item(
    project: Project, tracker: InMemoryTracker
) -> None:
    config = with_items((CHECK, SENTENCE))
    met = answer(definition_of_done=[{"item": SENTENCE.text, "met": True, "evidence": "seen"}])
    assert start(project, tracker, FakeRuntime(answers=[met]), config).exit_code == 0
    body = pull_body(tracker)
    assert "| check app has version 2 passes | met |" in body
    assert "| Docs are updated. | met |" in body
    text = project.show("ariane/7", "work/7/review-0.md")
    assert "met: check app has version 2 passes" in text
    assert "met: Docs are updated." in text


def test_c26_dod_review_a_long_review_gives_a_summary_and_the_link() -> None:
    findings = tuple(review.Finding("minor", "f.py", i, "t" * 40, "d") for i in range(100))
    one = review.Review("go", findings, (), ())
    settled = review.settle(one, (), [])
    section = review.pull_request_section(settled, "http://x/review", "work/7/review-0.md")
    assert len(section) < review.PULL_REQUEST_LIMIT
    assert "100 findings (0 blocking)" in section and "http://x/review" in section


def test_c26_dod_review_a_failed_check_item_is_unmet() -> None:
    result = checks.CheckResult("t", ("x",), False, False, "exit 1", "", 0.1)
    settled = review.settle(review.Review("go", (), (), ()), (DoneItem(check="t"),), [result])
    assert not settled.go and not settled.items[0].met
    _ = flow
