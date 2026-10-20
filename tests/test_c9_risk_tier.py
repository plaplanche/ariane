"""C9: each round has a risk tier, `low` or `high`, computed from its diff and `[checks_policy]`;
every check gets `ARIANE_RISK_TIER` and `ARIANE_FULL_SUITE` (ADR 0056)."""

from __future__ import annotations

import copy
import dataclasses
import sys
from typing import Any

import pytest
from test_c10_small_review import small_config
from test_config import VALID, with_change
from test_docs_reference import errors
from test_fix_rounds import NO_GO

from ariane import checks, config, risk
from ariane.config import CheckConfig, ChecksPolicy, Config
from ariane.review_session import ReviewSession
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, go_answer, make_config
from test_flow import journal, start, worktree

PY = sys.executable
# Prints the two variables, then passes.
SHOW = (
    PY,
    "-c",
    "import os; print('tier=' + os.environ['ARIANE_RISK_TIER'],"
    " 'full=' + os.environ['ARIANE_FULL_SUITE'])",
)
FAIL = (PY, "-c", "raise SystemExit(1)")


def show(name: str, full_when: str = "high") -> CheckConfig:
    return CheckConfig(name, SHOW, True, 1, full_when=full_when)


def with_policy(cfg: Config, policy: ChecksPolicy | None = None) -> Config:
    return dataclasses.replace(cfg, checks_policy=policy or ChecksPolicy())


def report(project: Project) -> str:
    return (worktree(project) / "work/7/checks.md").read_text(encoding="utf-8")


def test_c9_risk_tier_without_policy_is_high_and_every_check_gets_the_full_suite(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    cfg = make_config(checks=(show("a"), show("b", "always")))
    assert start(project, tracker, runtime, cfg).exit_code == 0
    text = report(project)
    assert text.startswith("# Checks\n\nRisk tier: high: no `[checks_policy]`.\n")
    assert text.count("tier=high full=1") == 2
    assert "Risk tier: high: no `[checks_policy]`." in tracker.opened[0]["body"]
    assert "Risk tier of this round: high: no `[checks_policy]`." in runtime.sessions[-1].prompt
    assert "Risk tier\n\nhigh: no `[checks_policy]`" in journal(project)


def test_c9_risk_tier_small_diff_in_one_module_is_low_and_full_when_always_keeps_the_suite(
    project: Project, tracker: InMemoryTracker
) -> None:
    """The fake implementer changes `app.txt` only: 2 changed lines, 1 module."""
    runtime = FakeRuntime()
    cfg = with_policy(make_config(checks=(show("related"), show("full", "always"))))
    assert start(project, tracker, runtime, cfg).exit_code == 0
    text = report(project)
    assert text.startswith("# Checks\n\nRisk tier: low: 2 changed lines, 1 module.\n")
    related, full = text.split("## related", 1)[1].split("## full", 1)
    assert "tier=low full=0" in related
    assert "tier=low full=1" in full
    assert "Risk tier: low: 2 changed lines, 1 module." in tracker.opened[0]["body"]
    assert "Risk tier of this round: low: 2 changed lines, 1 module." in runtime.sessions[-1].prompt


@pytest.mark.parametrize(
    ("policy", "changed", "lines", "reason"),
    [
        (ChecksPolicy(max_changed_lines=10), ["a.py"], 11, "11 changed lines (more than 10)"),
        (
            ChecksPolicy(max_modules=2),
            ["a/x.py", "b/y.py", "c/z.py"],
            3,
            "3 modules (more than 2): `a`, `b`, `c`",
        ),
        (
            ChecksPolicy(critical_paths=("src/auth/**",)),
            ["src/auth/login.py"],
            1,
            "touches `critical_paths` `src/auth/**`",
        ),
        (ChecksPolicy(), ["ariane.toml"], 1, "touches `ariane.toml`"),
        (ChecksPolicy(), ["uv.lock"], 1, "touches `check_all_paths` `uv.lock`"),
    ],
)
def test_c9_risk_tier_each_reason_makes_it_high_and_is_recorded(
    policy: ChecksPolicy, changed: list[str], lines: int, reason: str
) -> None:
    tier = checks.risk_tier(policy, changed, lines, ("uv.lock",))
    assert (tier.level, tier.reasons, tier.measured) == ("high", (reason,), True)
    assert tier.text() == f"high: {reason}"
    assert tier.variables("high") == {"ARIANE_RISK_TIER": "high", "ARIANE_FULL_SUITE": "1"}
    small = checks.risk_tier(ChecksPolicy(max_changed_lines=lines), ["a.py"], lines, ("uv.lock",))
    assert small.level == "low"  # at the threshold is still low


def test_c9_risk_tier_reasons_add_up_in_one_text() -> None:
    policy = ChecksPolicy(max_changed_lines=300, critical_paths=("src/auth/**",))
    tier = checks.risk_tier(policy, ["src/auth/a.py"], 412, failed_before=True)
    assert tier.text() == (
        "high: 412 changed lines (more than 300); touches `critical_paths` `src/auth/**`;"
        " a previous round failed a check"
    )


def test_c9_risk_tier_modules_count_children_of_the_roots_only() -> None:
    changed = ["src/ariane/a.py", "src/ariane/sub/b.py", "src/other/c.py", "tests/t.py", "x.md"]
    assert checks.modules(changed) == ["src", "tests", "x.md"]
    assert checks.modules(changed, ("src/*/",)) == [
        "src/ariane/a.py",
        "src/ariane/sub",
        "src/other/c.py",
    ]
    # The deepest matching root wins: `packages/web/` is the root, not `packages/`.
    assert checks.modules(["packages/web/src/a.ts"], ("packages/", "packages/*/")) == [
        "packages/web/src"
    ]


def test_c9_risk_tier_a_failed_previous_round_makes_the_next_one_high(
    project: Project, tracker: InMemoryTracker
) -> None:
    """Round 0 fails a non-blocking check and is reviewed no-go; round 1 is then high."""
    runtime = FakeRuntime(answers=[NO_GO, go_answer()])
    flaky = CheckConfig("flaky", FAIL, False, 1)
    cfg = with_policy(make_config(checks=(show("tests"), flaky)))
    assert start(project, tracker, runtime, cfg).exit_code == 0
    log = journal(project)
    assert "Risk tier\n\nlow: 2 changed lines, 1 module" in log
    assert "Risk tier\n\nhigh: a previous round failed a check" in log
    assert report(project).startswith(
        "# Checks\n\nRisk tier: high: a previous round failed a check.\n"
    )
    assert "tier=high full=1" in report(project)


def test_c9_risk_tier_high_keeps_the_full_review_and_unmeasured_keeps_the_sizing(
    project: Project, tracker: InMemoryTracker
) -> None:
    critical = ChecksPolicy(critical_paths=("app.txt",))
    runtime = FakeRuntime()
    assert start(project, tracker, runtime, with_policy(small_config(), critical)).exit_code == 0
    [session] = [s for s in runtime.sessions if s.role == "reviewer"]
    assert session.model == "test-reviewer"
    assert "2 changed lines, risk tier high: full review" in journal(project)


def test_c9_risk_tier_low_and_unmeasured_keep_the_small_review() -> None:
    def small(tier: risk.Tier) -> bool:
        reviewer = small_config().reviewer
        unused: Any = None  # the sizing reads only the reviewer, the lines and the tier
        session = ReviewSession(unused, reviewer, unused, unused, {}, (), (), tier=tier)
        return dataclasses.replace(session, changed_lines=2).small

    assert small(risk.UNMEASURED)
    assert small(checks.risk_tier(ChecksPolicy(), ["app.txt"], 2))
    assert not small(checks.risk_tier(ChecksPolicy(max_changed_lines=1), ["app.txt"], 2))


def test_c9_risk_tier_policy_parses_and_the_schema_accepts_it() -> None:
    table = {
        "max_changed_lines": 120,
        "max_modules": 2,
        "module_roots": ["src/*/"],
        "critical_paths": ["src/auth/**"],
    }
    data = with_change("checks_policy", table)
    data["checks"][0]["full_when"] = "always"
    assert errors(data, config.SCHEMA) == []
    parsed = config.parse(copy.deepcopy(data))
    assert parsed.checks_policy == ChecksPolicy(120, 2, ("src/*/",), ("src/auth/**",))
    assert parsed.checks[0].full_when == "always"
    assert config.parse(with_change("checks_policy", {})).checks_policy == ChecksPolicy(300, 3)
    assert config.parse(copy.deepcopy(VALID)).checks_policy is None
    assert config.parse(copy.deepcopy(VALID)).checks[0].full_when == "high"


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ({"max_lines": 10}, r"checks_policy\.max_lines: unknown key"),
        ({"max_changed_lines": 0}, r"checks_policy\.max_changed_lines: expected a positive"),
        ({"max_changed_lines": -5}, r"checks_policy\.max_changed_lines: expected a positive"),
        ({"max_changed_lines": 1.5}, r"checks_policy\.max_changed_lines: expected a positive"),
        ({"max_modules": True}, r"checks_policy\.max_modules: expected a positive"),
        ({"max_modules": 0}, r"checks_policy\.max_modules: expected a positive"),
        ({"critical_paths": ["src/**", 3]}, r"checks_policy\.critical_paths: expected a non-empty"),
        ({"critical_paths": []}, r"checks_policy\.critical_paths: expected a non-empty"),
        ({"module_roots": "src/*/"}, r"checks_policy\.module_roots: expected a non-empty"),
        ({"module_roots": [""]}, r"checks_policy\.module_roots: expected a non-empty"),
    ],
)
def test_c9_risk_tier_schema_refuses_a_bad_policy_naming_the_key(
    table: dict[str, Any], message: str
) -> None:
    data = with_change("checks_policy", table)
    with pytest.raises(config.ConfigError, match=message):
        config.parse(copy.deepcopy(data))
    assert any(e.startswith("checks_policy") for e in errors(data, config.SCHEMA))


def test_c9_risk_tier_schema_refuses_a_bad_full_when_and_a_policy_that_is_no_table() -> None:
    data = with_change("checks.0.full_when", "never")
    with pytest.raises(config.ConfigError, match=r'checks\[0\]\.full_when: expected "high"'):
        config.parse(copy.deepcopy(data))
    assert any(e.startswith("checks[0]") for e in errors(data, config.SCHEMA))
    with pytest.raises(config.ConfigError, match=r"checks_policy: expected a table"):
        config.parse(with_change("checks_policy", 3))
