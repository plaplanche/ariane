"""C5: the reviewer runs on opencode: events summed, caps, errors, permissions (ADR 0015)."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_fix_rounds import NO_GO

from ariane import cli, config, flow, process, review, runtime
from ariane.opencode import OpenCodeRuntime, inline_config, login_variables
from ariane.review_session import read_answer
from ariane.runtime import Session, SessionResult, StopReason
from ariane.tracker import InMemoryTracker

from conftest import PY, FakeRuntime, Project, go_answer, make_config

HERE = Path(__file__).resolve().parent
REVIEW = HERE / "fixtures" / "opencode_review.jsonl"
ERROR = HERE / "fixtures" / "opencode_error.jsonl"


def session(tmp_path: Path, max_tokens: int | None = None, budget: float = 3.0) -> Session:
    return Session(
        role="reviewer",
        model="openai/gpt-x",
        tools=("read", "glob", "grep"),
        max_budget_usd=budget,
        max_tokens=max_tokens,
        timeout_s=30,
        cwd=tmp_path,
        prompt="review this",
        env={**os.environ, "OPENAI_API_KEY": "k"},
        json_schema=review.SCHEMA,
    )


def run(
    tmp_path: Path, events: Path, code: int = 0, end: str = "end", **kwargs: Any
) -> tuple[SessionResult, dict[str, Any]]:
    dump = tmp_path / "dump.json"
    fake = HERE / "fake_opencode.py"
    adapter = OpenCodeRuntime((PY, str(fake), str(events), str(dump), str(code), end))
    result = adapter.run(session(tmp_path, **kwargs))
    return result, json.loads(dump.read_text(encoding="utf-8")) if dump.exists() else {}


def test_c5_opencode_review_fixture_sums_tokens_and_cost(tmp_path: Path) -> None:
    result, _ = run(tmp_path, REVIEW)
    assert result.stop_reason is StopReason.FINISHED
    assert (result.input_tokens, result.cache_read_tokens) == (1000, 3000)
    assert (result.output_tokens, result.cache_write_tokens) == (240, 0)
    assert result.cost_usd == pytest.approx(0.0075)


def test_c5_opencode_answer_is_the_last_text_part_and_validates_as_no_go(tmp_path: Path) -> None:
    result, _ = run(tmp_path, REVIEW)
    answer, error = read_answer(result)
    assert error == "" and answer is not None
    assert answer.verdict == "no-go"
    assert answer.findings[0].file == "calc.py"


def test_c5_opencode_a_cap_below_the_total_stops_the_session_as_budget(tmp_path: Path) -> None:
    result, _ = run(tmp_path, REVIEW, end="hang", max_tokens=4000)
    assert result.stop_reason is StopReason.BUDGET
    assert result.cap == "Ariane token cap (4000 tokens)"
    assert result.structured_output is None
    result, _ = run(tmp_path, REVIEW, max_tokens=4240)
    assert result.stop_reason is StopReason.BUDGET  # the cap is reached at 4,240


def test_c5_opencode_the_first_step_alone_stops_a_small_cap(tmp_path: Path) -> None:
    result, _ = run(tmp_path, REVIEW, end="hang", max_tokens=2000)
    assert result.stop_reason is StopReason.BUDGET
    assert result.input_tokens == 500 and result.output_tokens == 60


def test_c5_opencode_the_cost_cap_stops_the_session(tmp_path: Path) -> None:
    result, _ = run(tmp_path, REVIEW, end="hang", budget=0.003)
    assert result.stop_reason is StopReason.BUDGET
    assert result.cap == "runtime cost cap (0.003 USD)"


def test_c5_opencode_error_fixture_is_error(tmp_path: Path) -> None:
    result, _ = run(tmp_path, ERROR, code=1)
    assert result.stop_reason is StopReason.ERROR
    assert "upstream failure" in result.summary
    assert result.input_tokens is None and result.cost_usd is None


def test_c5_opencode_a_non_zero_exit_without_events_is_error(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    result, _ = run(tmp_path, empty, code=3)
    assert result.stop_reason is StopReason.ERROR
    assert "exit 3" in result.summary


def test_c5_opencode_zero_cost_with_tokens_is_cost_not_reported(tmp_path: Path) -> None:
    free = tmp_path / "free.jsonl"
    lines = [json.loads(line) for line in REVIEW.read_text(encoding="utf-8").splitlines()]
    for event in lines:
        if event["type"] == "step_finish":
            event["part"]["cost"] = 0
    free.write_text("\n".join(json.dumps(e) for e in lines), encoding="utf-8")
    result, _ = run(tmp_path, free)
    assert result.stop_reason is StopReason.FINISHED
    assert result.cost_usd is None and result.input_tokens == 1000
    assert result.usage()[0] == "not reported"


def test_c5_opencode_inline_configuration_denies_all_but_the_roles_tools() -> None:
    data = json.loads(inline_config("reviewer", ("read", "glob", "grep")))
    agent = data["agent"]["ariane-reviewer"]
    assert agent["permission"] == {"*": "deny", "read": "allow", "glob": "allow", "grep": "allow"}
    assert agent["steps"] == 20 and agent["mode"] == "primary"
    assert data["autoupdate"] is False and data["share"] == "disabled"


def test_c5_opencode_pure_and_the_claude_code_switch_are_always_set(tmp_path: Path) -> None:
    _, seen = run(tmp_path, REVIEW)
    argv = seen["argv"]
    assert argv[:6] == ["run", "--pure", "--format", "json", "--model", "openai/gpt-x"]
    assert argv[6:8] == ["--agent", "ariane-reviewer"]
    assert len(argv) == 8
    env = seen["env"]
    assert env["OPENCODE_DISABLE_CLAUDE_CODE"] == "1"
    assert env["OPENCODE_DISABLE_AUTOUPDATE"] == "1"
    assert json.loads(env["OPENCODE_CONFIG_CONTENT"])["agent"]["ariane-reviewer"]
    assert seen["cwd"] == str(tmp_path)


def test_c5_opencode_the_implementer_role_is_refused() -> None:
    data: dict[str, Any] = {
        "project": {"base_branch": "main"},
        "tracker": {"kind": "github", "repository": "o/n", "token_env": "GH_TOKEN"},
        "agents": {
            "implementer": {
                "runtime": "opencode",
                "model": "openai/gpt-x",
                "tools": ["read"],
                "max_budget_usd": 1,
                "timeout_minutes": 1,
            },
            "reviewer": {
                "runtime": "opencode",
                "model": "openai/gpt-y",
                "tools": ["read", "glob", "grep"],
                "max_budget_usd": 1,
                "timeout_minutes": 1,
                "max_tokens": 1000,
            },
        },
        "checks": [{"name": "t", "command": ["pytest"]}],
    }
    with pytest.raises(config.ConfigError, match=r"agents\.implementer\.runtime.*implementer role"):
        config.parse(data)
    data["agents"]["implementer"]["runtime"] = "claude-code"
    data["agents"]["implementer"]["model"] = "claude-sonnet-5-5"
    cfg = config.parse(data)
    assert cfg.reviewer.runtime == "opencode"
    data["agents"]["reviewer"]["tools"] = ["Bash"]
    with pytest.raises(config.ConfigError, match=r"agents\.reviewer\.tools"):
        config.parse(data)


def test_c5_opencode_stdin_the_command_has_no_message_argument(tmp_path: Path) -> None:
    command = OpenCodeRuntime().command(session(tmp_path))
    assert command[-2:] == ["--agent", "ariane-reviewer"]
    assert "review this" not in command


def test_c5_opencode_stdin_the_prompt_is_given_as_input_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def stream(argv: Any, **kwargs: Any) -> process.Completed:
        seen.update(kwargs)
        return process.Completed(tuple(argv), 0, "", "", False, 0.0)

    monkeypatch.setattr(process, "stream", stream)
    OpenCodeRuntime().run(session(tmp_path))
    assert seen["input_text"].startswith("review this")
    assert "JSON Schema" in seen["input_text"]


def test_c5_opencode_stdin_a_300000_character_prompt_runs_and_is_not_cut(tmp_path: Path) -> None:
    long = session(tmp_path)
    object.__setattr__(long, "prompt", "x" * 300_000)
    dump = tmp_path / "dump.json"
    fake = HERE / "fake_opencode.py"
    adapter = OpenCodeRuntime((PY, str(fake), str(REVIEW), str(dump), "0", "end"))
    result = adapter.run(long)
    assert result.stop_reason is StopReason.FINISHED
    recorded = json.loads(dump.read_text(encoding="utf-8"))
    assert recorded["stdin_size"] >= 300_000
    assert all(len(arg) < 1000 for arg in recorded["argv"])


def test_c5_opencode_cli_runtime_builds_opencode_with_the_model_for_a_reviewer(
    tmp_path: Path,
) -> None:
    cfg = make_config()
    reviewer = replace(cfg.reviewer, runtime=config.OPENCODE, model="openai/gpt-x")
    routed = cli._runtime(replace(cfg, reviewer=reviewer))
    built = routed.for_role("reviewer")
    assert isinstance(built, OpenCodeRuntime)
    assert built.login_variables == ("OPENAI_API_KEY",)
    assert routed.for_role("implementer").name == "claude-code"


def test_c5_opencode_an_unstartable_executable_ends_as_error(tmp_path: Path) -> None:
    broken = tmp_path / "opencode"
    broken.write_text("not a program", encoding="utf-8")
    broken.chmod(0o755)
    result = OpenCodeRuntime((str(broken),)).run(session(tmp_path))
    assert result.stop_reason is StopReason.ERROR


def test_c5_opencode_describe_gives_the_version_and_the_title_note(tmp_path: Path) -> None:
    fake = HERE / "fake_opencode.py"
    adapter = OpenCodeRuntime((PY, str(fake), "-", "-", "0", "end"))
    text = runtime.describe(adapter)
    assert text.startswith("opencode 1.18.35")
    assert "title call's usage is not reported" in text


def test_c5_opencode_login_variables_are_the_providers_keys() -> None:
    assert login_variables("openai/gpt-x") == ("OPENAI_API_KEY",)
    assert login_variables("google/gemini") == ("GOOGLE_GENERATIVE_AI_API_KEY", "GEMINI_API_KEY")
    assert OpenCodeRuntime(model="openai/m").login_variables == ("OPENAI_API_KEY",)


def test_c5_opencode_roles_are_routed_to_their_runtime(tmp_path: Path) -> None:
    reviewer = OpenCodeRuntime(model="openai/m")
    routed = runtime.RoutedRuntime({"implementer": runtime_stub(), "reviewer": reviewer})
    assert runtime.for_role(routed, "reviewer") is reviewer
    assert routed.name == "stub, opencode"


class StubRuntime:
    name = "stub"
    login_variables: tuple[str, ...] = ("STUB_",)

    def run(self, session: Session) -> SessionResult:
        raise AssertionError("not run")


def runtime_stub() -> StubRuntime:
    return StubRuntime()


def test_c21_role_env_the_reviewer_on_opencode_keeps_its_key_and_the_implementer_does_not(
    project: Project, tracker: InMemoryTracker
) -> None:
    implementer = FakeRuntime()
    reviewer = FakeRuntime(login_variables=("OPENAI_API_KEY",))
    routed = runtime.RoutedRuntime({"implementer": implementer, "reviewer": reviewer})
    environ = {**os.environ, "OPENAI_API_KEY": "sk-o", "ANTHROPIC_API_KEY": "sk-a"}
    outcome = flow.start(
        7,
        repo_root=project.root,
        config=make_config(),
        tracker=tracker,
        runtime=routed,
        environ={**environ, "GH_TOKEN": "t"},
    )
    assert outcome.exit_code == 0, outcome.line
    (built,) = implementer.sessions
    assert "OPENAI_API_KEY" not in built.env and "ANTHROPIC_API_KEY" in built.env
    (judged,) = reviewer.sessions
    assert "OPENAI_API_KEY" in judged.env
    assert "ANTHROPIC_API_KEY" not in judged.env


def test_c21_role_env_the_fix_session_does_not_hold_the_reviewers_key(
    project: Project, tracker: InMemoryTracker
) -> None:
    implementer = FakeRuntime()
    reviewer = FakeRuntime(login_variables=("OPENAI_API_KEY",), answers=[NO_GO, go_answer()])
    routed = runtime.RoutedRuntime({"implementer": implementer, "reviewer": reviewer})
    flow.start(
        7,
        repo_root=project.root,
        config=make_config(),
        tracker=tracker,
        runtime=routed,
        environ={**os.environ, "OPENAI_API_KEY": "sk-o", "GH_TOKEN": "t"},
    )
    assert len(implementer.sessions) == 2
    assert all("OPENAI_API_KEY" not in s.env for s in implementer.sessions)


def opencode_data() -> dict[str, Any]:
    return {
        "project": {"base_branch": "main"},
        "tracker": {"kind": "github", "repository": "o/n", "token_env": "GH_TOKEN"},
        "agents": {
            "implementer": {
                "runtime": "claude-code",
                "model": "claude-sonnet-5-5",
                "tools": ["Read", "Edit", "Write", "Bash"],
                "max_budget_usd": 1,
                "timeout_minutes": 1,
            },
            "reviewer": {
                "runtime": "opencode",
                "model": "openai/gpt-y",
                "tools": ["read", "glob", "grep"],
                "max_budget_usd": 1,
                "timeout_minutes": 1,
                "max_tokens": 1000,
            },
        },
        "checks": [{"name": "t", "command": ["pytest"]}],
    }


def test_c5_opencode_cap_an_agent_without_max_tokens_is_refused() -> None:
    data = opencode_data()
    config.parse(data)
    del data["agents"]["reviewer"]["max_tokens"]
    with pytest.raises(config.ConfigError, match=r"agents\.reviewer\.max_tokens"):
        config.parse(data)


def test_c5_opencode_cap_a_session_priced_at_zero_stops_at_max_tokens(tmp_path: Path) -> None:
    free = tmp_path / "free.jsonl"
    lines = [json.loads(line) for line in REVIEW.read_text(encoding="utf-8").splitlines()]
    for event in lines:
        if event["type"] == "step_finish":
            event["part"]["cost"] = 0
    free.write_text("\n".join(json.dumps(e) for e in lines), encoding="utf-8")
    result, _ = run(tmp_path, free, max_tokens=10)
    assert result.stop_reason is StopReason.BUDGET


def test_c5_opencode_cap_the_journal_names_the_caps_that_apply() -> None:
    from ariane.review_session import cap_text

    cfg = config.parse(opencode_data())
    text = cap_text(cfg.reviewer)
    assert "cost cap none" in text and "1 USD" in text and "1000 tokens" in text
    assert cap_text(cfg.implementer) == "runtime cost cap 1 USD"


def test_c21_opencode_project_config_is_disabled_in_every_session(tmp_path: Path) -> None:
    _, seen = run(tmp_path, REVIEW)
    assert seen["env"]["OPENCODE_DISABLE_PROJECT_CONFIG"] == "1"


@pytest.mark.parametrize("tool", ["Write", "Edit", "NotebookEdit", "Bash"])
def test_c10_reviewer_read_only_write_tools_are_refused(tool: str) -> None:
    data = opencode_data()
    data["agents"]["reviewer"] = {
        "runtime": "claude-code",
        "model": "claude-opus-5-5",
        "tools": ["Read", tool],
        "max_budget_usd": 1,
        "timeout_minutes": 1,
    }
    with pytest.raises(config.ConfigError, match=r"agents\.reviewer\.tools"):
        config.parse(data)
    data["agents"]["reviewer"]["tools"] = ["Read", "Grep"]
    config.parse(data)
    data["agents"]["implementer"]["tools"] = ["Read", tool]
    config.parse(data)


def test_c10_review_prompt_failed_checks_are_named() -> None:
    from ariane.checks import CheckResult
    from ariane.config import CheckConfig
    from ariane.tracker import Issue

    def result(name: str, passed: bool) -> CheckResult:
        return CheckResult(name, ("x",), True, passed, "exit 0", "", 0.0)

    cfgs = [CheckConfig("lint", ("x",), True, 1), CheckConfig("tests", ("x",), True, 1)]
    issue = Issue(7, "T", "B", "u")
    ok = review.prompt(issue, "", [result("lint", True), result("tests", True)], cfgs, ())
    assert "all blocking checks green" in ok
    bad = review.prompt(issue, "", [result("lint", True), result("tests", False)], cfgs, ())
    assert "all blocking checks green" not in bad and "FAILED: tests" in bad
