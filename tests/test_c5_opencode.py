"""C5: the reviewer runs on opencode: events summed, caps, errors, permissions (ADR 0015)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from ariane import config, review, runtime
from ariane.opencode import OpenCodeRuntime, inline_config, login_variables
from ariane.review_session import read_answer
from ariane.runtime import Session, SessionResult, StopReason

from conftest import PY

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
    assert argv[8].startswith("review this") and "JSON Schema" in argv[8]
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


def test_c5_opencode_a_too_long_prompt_ends_as_error_not_a_crash(tmp_path: Path) -> None:
    long = session(tmp_path)
    object.__setattr__(long, "prompt", "x" * 300_000)
    result = OpenCodeRuntime((PY, "-c", "pass")).run(long)
    assert result.stop_reason is StopReason.ERROR
    assert "command line" in result.summary


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
    assert "OPENAI_API_KEY" in routed.login_variables and "STUB_" in routed.login_variables


class StubRuntime:
    name = "stub"
    login_variables: tuple[str, ...] = ("STUB_",)

    def run(self, session: Session) -> SessionResult:
        raise AssertionError("not run")


def runtime_stub() -> StubRuntime:
    return StubRuntime()
