"""C10, C5, C19: a small change gets the small reviewer settings and a narrower prompt
(ADR 0046)."""

from __future__ import annotations

import copy
import dataclasses
import json
from typing import Any

import pytest
from test_config import VALID, with_change
from test_docs_reference import errors
from test_verify import BRANCH, branch, pushes  # noqa: F401 (fixtures)

from ariane import config, git, opencode, review, review_session, verify
from ariane.claude_code import ClaudeCodeRuntime
from ariane.config import Config, SmallReview
from ariane.opencode import OpenCodeRuntime
from ariane.runtime import RoutedRuntime, Session, SessionResult, StopReason
from ariane.tracker import InMemoryTracker, Issue

from conftest import FakeRuntime, Project, make_config, sh
from test_flow import environ, journal, start, worktree

NOTE = (
    "This change is small (2 changed lines). Review the changed files, their tests and the code"
    " that calls them; do not survey the rest of the repository."
)


def small_config(max_lines: int = 10, **changes: Any) -> Config:
    """The test configuration with `[agents.reviewer.small]`; the fake implementer's change to
    app.txt is 2 changed lines (one deleted, one added)."""
    base = make_config()
    small = dataclasses.replace(
        SmallReview(max_lines, "small-reviewer", 0.25, None, 0.5), **changes
    )
    return dataclasses.replace(base, reviewer=dataclasses.replace(base.reviewer, small=small))


def reviewers(runtime: FakeRuntime) -> list[Session]:
    return [s for s in runtime.sessions if s.role == "reviewer"]


def metrics_sessions(project: Project) -> list[dict[str, Any]]:
    data = json.loads(project.show("ariane/7", "work/7/metrics.json"))
    return [s for s in data["sessions"] if s["role"] == "reviewer"]


def test_c10_small_review_a_small_diff_uses_the_small_settings_and_the_narrower_prompt(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    outcome = start(project, tracker, runtime, small_config())
    assert outcome.exit_code == 0, outcome.line
    [session] = reviewers(runtime)
    assert (session.model, session.max_budget_usd, session.timeout_s) == (
        "small-reviewer",
        0.25,
        30.0,
    )
    assert session.tools == ("Read", "Glob", "Grep")
    assert f"in the diff.\n\n{NOTE}\n\nRules:" in session.prompt
    assert "small change (2 changed lines, at most 10): small reviewer settings" in journal(project)
    [recorded] = metrics_sessions(project)
    assert (recorded["model"], recorded["changed_lines"]) == ("small-reviewer", 2)
    assert "Reviewer model: small-reviewer" in project.show("ariane/7", "work/7/review-0.md")


def test_c10_small_review_a_larger_diff_uses_the_reviewer_s_own_settings(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    assert start(project, tracker, runtime, small_config(max_lines=1)).exit_code == 0
    [session] = reviewers(runtime)
    assert (session.model, session.max_budget_usd, session.timeout_s) == (
        "test-reviewer",
        1.0,
        60.0,
    )
    assert "This change is small" not in session.prompt
    text = journal(project)
    assert "; 2 changed lines." in text and "small reviewer settings" not in text
    assert metrics_sessions(project)[0]["changed_lines"] == 2


def test_c10_small_review_without_the_table_sessions_and_prompt_are_unchanged(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    assert start(project, tracker, runtime).exit_code == 0
    [session] = reviewers(runtime)
    reviewer = make_config().reviewer
    assert (session.model, session.max_budget_usd, session.max_tokens, session.timeout_s) == (
        reviewer.model,
        reviewer.max_budget_usd,
        reviewer.max_tokens,
        reviewer.timeout_minutes * 60,
    )
    assert "This change is small" not in session.prompt
    # Today's text: the paragraph about the removed instruction files, then the rules.
    assert "their changes are in the diff.\n\nRules:\n- Be adversarial" in session.prompt
    issue = Issue(7, "T", "body", "u")
    assert review.prompt(issue, "d", [], [], ()) == review.prompt(
        issue, "d", [], [], (), small_lines=None
    )
    narrow = review.prompt(issue, "d", [], [], (), small_lines=2)
    assert narrow.replace(f"\n{NOTE}\n", "", 1) == review.prompt(issue, "d", [], [], ())


def small_table(**changes: Any) -> dict[str, Any]:
    table: dict[str, Any] = {"max_lines": 40, "model": "claude-haiku-5-5", "max_budget_usd": 0.3}
    table.update(changes)
    return {k: v for k, v in table.items() if v is not None}


def test_c10_small_review_table_is_parsed_and_valid_in_the_schema() -> None:
    data = with_change("agents.reviewer.small", small_table(max_tokens=5000, timeout_minutes=5))
    small = config.parse(copy.deepcopy(data)).reviewer.small
    assert small == SmallReview(40, "claude-haiku-5-5", 0.3, 5000, 5.0)
    assert errors(data, config.SCHEMA) == []
    assert config.parse(copy.deepcopy(VALID)).reviewer.small is None


@pytest.mark.parametrize(
    ("table", "message"),
    [
        (
            small_table(model="claude-sonnet-5-5"),
            r"agents\.reviewer\.small\.model: must differ from agents\.implementer\.model"
            r" \('claude-sonnet-5-5'\); the review is by a different model \(C10\)",
        ),
        (small_table(runtime="opencode"), r"agents\.reviewer\.small\.runtime: unknown key"),
        (small_table(tools=["Read"]), r"agents\.reviewer\.small\.tools: unknown key"),
        (small_table(max_lines=None), r"agents\.reviewer\.small\.max_lines: missing key"),
        (small_table(max_lines=0), r"agents\.reviewer\.small\.max_lines: expected a positive"),
        (small_table(max_lines=True), r"agents\.reviewer\.small\.max_lines: expected a positive"),
        (small_table(max_budget_usd=-1), r"agents\.reviewer\.small\.max_budget_usd: expected"),
        (small_table(max_tokens=1.5), r"agents\.reviewer\.small\.max_tokens: expected"),
        ("small", r"agents\.reviewer\.small: expected a table"),
    ],
)
def test_c10_small_review_invalid_table_is_refused_naming_the_key(table: Any, message: str) -> None:
    with pytest.raises(config.ConfigError, match=message):
        config.parse(with_change("agents.reviewer.small", table))


def test_c10_small_review_table_is_refused_on_the_implementer() -> None:
    with pytest.raises(config.ConfigError, match=r"agents\.implementer\.small: unknown key"):
        config.parse(with_change("agents.implementer.small", small_table()))
    assert errors(with_change("agents.implementer.small", small_table()), config.SCHEMA)


def test_c10_small_review_schema_refuses_unknown_key_and_missing_max_lines() -> None:
    assert errors(with_change("agents.reviewer.small", small_table(runtime="x")), config.SCHEMA)
    assert errors(with_change("agents.reviewer.small", small_table(max_lines=None)), config.SCHEMA)


def test_c10_small_review_lines_under_work_and_binary_files_do_not_count(
    project: Project,
) -> None:
    root = project.root
    base = git.head(root)
    (root / "app.txt").write_text("version 2\nmore\n", encoding="utf-8")  # 1 deleted, 2 added
    (root / "work" / "7").mkdir(parents=True)
    (root / "work" / "7" / "journal.md").write_text("a\nb\nc\nd\n", encoding="utf-8")
    (root / "image.bin").write_bytes(b"\x00\x01\x02\nline\n\x00" * 50)
    sh(["git", "add", "--all"], root)
    sh(["git", "commit", "--quiet", "-m", "change"], root)
    assert git.changes(root, base, git.head(root), "work").changed_lines == 3
    assert git.changes(root, base, base, "work").changed_lines == 0


class CappedRuntime(FakeRuntime):
    """A reviewer that stops at its cost cap."""

    def review(self, session: Session) -> SessionResult:
        return SessionResult.failed(StopReason.BUDGET, "stopped", cap="0.25 USD")


def test_c10_small_review_a_cap_stop_names_the_small_key(
    project: Project, tracker: InMemoryTracker
) -> None:
    outcome = start(project, tracker, CappedRuntime(), small_config())
    assert outcome.exit_code == 1
    assert "agents.reviewer.small.max_budget_usd" in (
        worktree(project) / "work/7/status.md"
    ).read_text(encoding="utf-8")


def test_c10_small_review_idle_limit_above_the_small_time_limit_is_dropped(
    project: Project, tracker: InMemoryTracker
) -> None:
    base = small_config()
    cfg = dataclasses.replace(base, reviewer=dataclasses.replace(base.reviewer, idle_minutes=0.9))
    runtime = FakeRuntime()
    assert start(project, tracker, runtime, cfg).exit_code == 0
    assert reviewers(runtime)[0].idle_timeout_s is None


def test_c10_small_review_verify_applies_the_same_rule(
    project: Project,
    branch: str,  # noqa: F811
    pushes: list[str],  # noqa: F811
) -> None:
    for max_lines, model in ((10, "small-reviewer"), (1, "test-reviewer")):
        runtime = FakeRuntime()
        outcome = verify.verify(
            branch,
            repo_root=project.root,
            config=small_config(max_lines),
            runtime=runtime,
            environ=environ(),
        )
        assert outcome.exit_code == 0, outcome.line
        [session] = reviewers(runtime)
        assert session.model == model
        assert (NOTE in session.prompt) == (model == "small-reviewer")
        shown = sh(["git", "show", f"{BRANCH}:work/verify/{BRANCH}/review.md"], project.root)
        assert f"Reviewer model: {model}" in shown
        metrics = sh(["git", "show", f"{BRANCH}:work/verify/{BRANCH}/metrics.json"], project.root)
        assert json.loads(metrics)["sessions"][0]["changed_lines"] == 2


@dataclasses.dataclass
class ProviderRuntime(FakeRuntime):
    """A fake runtime whose login depends on the model's provider, as opencode's does."""

    login_variables: tuple[str, ...] = ("ANTHROPIC_API_KEY",)

    def login_for(self, model: str) -> tuple[str, ...]:
        return opencode.login_variables(model)


KEYS = {"ANTHROPIC_API_KEY": "anthropic-key", "OPENAI_API_KEY": "openai-key"}


def cross_provider(max_lines: int = 10) -> Config:
    """A reviewer on one provider and a small reviewer on another."""
    cfg = small_config(max_lines, model="openai/small")
    return dataclasses.replace(
        cfg, reviewer=dataclasses.replace(cfg.reviewer, model="anthropic/large")
    )


def logins(session: Session) -> set[str]:
    return {name for name in KEYS if name in session.env}


def test_c10_small_review_small_model_gets_its_own_provider_login(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)
    for max_lines, expected in ((10, {"OPENAI_API_KEY"}), (1, {"ANTHROPIC_API_KEY"})):
        runtime = ProviderRuntime()
        number = 7 if max_lines == 10 else 8
        if number == 8:
            tracker.add_issue(8, "Another change", "Body.")
        assert start(project, tracker, runtime, cross_provider(max_lines), number).exit_code == 0
        [session] = reviewers(runtime)
        assert logins(session) == expected


def test_c10_small_review_verify_gives_the_small_model_its_own_provider_login(
    project: Project,
    branch: str,  # noqa: F811
    pushes: list[str],  # noqa: F811
) -> None:
    for max_lines, expected in ((10, {"OPENAI_API_KEY"}), (1, {"ANTHROPIC_API_KEY"})):
        runtime = ProviderRuntime()
        outcome = verify.verify(
            branch,
            repo_root=project.root,
            config=cross_provider(max_lines),
            runtime=runtime,
            environ={**environ(), **KEYS},
        )
        assert outcome.exit_code == 0, outcome.line
        [session] = reviewers(runtime)
        assert logins(session) == expected


def test_c10_small_review_opencode_logins_follow_each_model() -> None:
    cfg = cross_provider()
    runtime = RoutedRuntime(
        {"implementer": ClaudeCodeRuntime(), "reviewer": OpenCodeRuntime(model="anthropic/large")}
    )
    assert review_session.agent_logins(runtime, cfg.implementer, cfg.reviewer) == {
        "implementer": ("ANTHROPIC_", "CLAUDE_"),
        "reviewer": ("ANTHROPIC_API_KEY",),
        "reviewer.small": ("OPENAI_API_KEY",),
    }
    plain = small_config()
    assert review_session.agent_logins(runtime, plain.implementer, plain.reviewer)[
        "reviewer.small"
    ] == ("SMALL_REVIEWER_API_KEY",)
