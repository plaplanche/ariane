"""C9, C10: a check declares the tests it cannot run locally; the records and prompts say so
(ADR 0042)."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from test_config import VALID, with_change
from test_docs_reference import errors

from ariane import checks, config, context, review
from ariane.config import CheckConfig
from ariane.tracker import Issue

GLOBS = ("tests/e2e/**", "web/*.spec.ts")
CHANGED = ["src/app.py", "tests/e2e/login.py", "web/a.spec.ts", "web/sub/b.spec.ts"]


def check(globs: tuple[str, ...] = GLOBS) -> CheckConfig:
    return CheckConfig("e2e", ("pytest",), True, 1, not_run_locally=globs)


def result(globs: tuple[str, ...] = GLOBS) -> checks.CheckResult:
    return checks.CheckResult("e2e", ("pytest",), True, True, "exit 0", "ok", 1.0, globs)


def test_c9_not_run_locally_is_parsed_and_valid_in_the_schema() -> None:
    data = with_change("checks.0.not_run_locally", list(GLOBS))
    assert config.parse(copy.deepcopy(data)).checks[0].not_run_locally == GLOBS
    assert errors(data, config.SCHEMA) == []
    assert config.parse(copy.deepcopy(VALID)).checks[0].not_run_locally == ()


@pytest.mark.parametrize("value", [[], "tests/**", [1], [""]])
def test_c9_not_run_locally_refuses_empty_or_non_strings(value: Any) -> None:
    data = with_change("checks.0.not_run_locally", value)
    with pytest.raises(config.ConfigError, match=r"checks\[0\]\.not_run_locally"):
        config.parse(data)


def test_c9_not_run_locally_empty_list_is_refused_by_the_schema() -> None:
    assert errors(with_change("checks.0.not_run_locally", []), config.SCHEMA)


def test_c9_not_run_locally_checks_md_lists_globs_and_matching_files() -> None:
    text = checks.report([result()], "abc", CHANGED)
    assert "Not run by this replay (CI only): `tests/e2e/**`, `web/*.spec.ts`" in text
    assert "`tests/e2e/login.py`, `web/a.spec.ts`" in text
    assert "web/sub/b.spec.ts" not in text
    assert "no changed file matches" in checks.report([result()], "abc", ["src/app.py"])
    assert "Not run by this replay" not in checks.report([result(())], "abc", CHANGED)


def test_c9_not_run_locally_reviewer_prompt_holds_the_block_only_on_a_match() -> None:
    issue = Issue(7, "T", "b", "u")
    hit = review.prompt(issue, "", [result()], [check()], (), changed=CHANGED)
    assert "hold tests that no replay ran" in hit
    assert "report a blocking finding for a test that cannot pass" in hit
    assert "tests/e2e/login.py" in hit and "src/app.py" not in hit.split("no replay ran")[1]
    miss = review.prompt(issue, "", [result()], [check()], (), changed=["src/app.py"])
    assert "no replay ran" not in miss


def test_c9_not_run_locally_implementer_prompt_marks_the_check() -> None:
    plain = CheckConfig("lint", ("ruff",), True, 1)
    prompt = context.implementer_prompt(Issue(7, "T", "b", "u"), "ariane/7", (plain, check()))
    assert "- lint: `ruff`\n" in prompt
    assert (
        "- e2e: `pytest` (does not run `tests/e2e/**`, `web/*.spec.ts` locally: only CI does;"
        " write those tests with extra care)"
    ) in prompt
