"""C5: Claude Code as an agent runtime: command line, stop reasons, cost as reported."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ariane.claude_code import DENIED_TOOLS, ClaudeCodeRuntime, parse_result
from ariane.runtime import Session, StopReason

from conftest import PY

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def session(tmp_path: Path, timeout_s: float = 30) -> Session:
    return Session(
        role="implementer",
        model="claude-sonnet-5-5",
        tools=("Read", "Edit", "Bash"),
        max_budget_usd=2.5,
        timeout_s=timeout_s,
        cwd=tmp_path,
        prompt="do the ticket",
        env={**__import__("os").environ, "ARIANE_ROLE": "implementer"},
    )


def fake(mode: str, *extra: str) -> ClaudeCodeRuntime:
    return ClaudeCodeRuntime((PY, str(HERE / "fake_claude.py"), mode, *extra, "--"))


@pytest.mark.parametrize(
    ("fixture", "reason"),
    [
        ("claude_success.json", StopReason.FINISHED),
        ("claude_budget.json", StopReason.BUDGET),
        ("claude_turns.json", StopReason.TURNS),
    ],
)
def test_c5_stop_reason_and_cost_come_from_recorded_results(
    fixture: str, reason: StopReason
) -> None:
    raw = (FIXTURES / fixture).read_text(encoding="utf-8")
    data = json.loads(raw)
    result = parse_result(raw, "", 0)
    assert result.stop_reason is reason
    assert result.cost_usd == data["total_cost_usd"]
    assert result.input_tokens == data["usage"]["input_tokens"]
    assert result.output_tokens == data["usage"]["output_tokens"]


def test_c5_refused_tool_calls_are_reported() -> None:
    raw = (FIXTURES / "claude_denied.json").read_text(encoding="utf-8")
    result = parse_result(raw, "", 0)
    assert result.permission_denials == ("Bash: git push --dry-run origin main .",)


def test_c5_unknown_subtype_error_flag_and_garbage_are_errors() -> None:
    assert (
        parse_result('{"type": "result", "subtype": "error_during_execution"}', "", 1).stop_reason
        is StopReason.ERROR
    )
    flagged = '{"type": "result", "subtype": "success", "is_error": true, "result": "boom"}'
    assert parse_result(flagged, "", 0).stop_reason is StopReason.ERROR
    garbage = parse_result("not json", "Error: not logged in", 1)
    assert garbage.stop_reason is StopReason.ERROR
    assert "not logged in" in garbage.summary and garbage.cost_usd is None


def test_c5_command_line_has_the_allowlist_deny_list_budget_and_no_extra_tool_server(
    tmp_path: Path,
) -> None:
    argv = ClaudeCodeRuntime().command(session(tmp_path))
    tools = argv[argv.index("--tools") + 1 : argv.index("--disallowedTools")]
    assert tools == ["Read", "Edit", "Bash"]
    assert "Skill" not in argv
    denied = argv[argv.index("--disallowedTools") + 1 : argv.index("--permission-mode")]
    assert tuple(denied) == DENIED_TOOLS and "Bash(git push:*)" in denied
    assert argv[argv.index("--max-budget-usd") + 1] == "2.5"
    assert "--strict-mcp-config" in argv and "--no-session-persistence" in argv
    assert argv[argv.index("--model") + 1] == "claude-sonnet-5-5"


def test_c5_the_prompt_goes_on_standard_input_with_the_session_environment(
    tmp_path: Path,
) -> None:
    result = fake("echo").run(session(tmp_path))
    assert result.stop_reason is StopReason.FINISHED
    seen = json.loads(result.summary)
    assert seen["prompt"] == "do the ticket"
    assert seen["role"] == "implementer"
    assert "-p" in seen["argv"]


def test_c5_a_session_killed_at_its_time_limit_is_a_timeout(tmp_path: Path) -> None:
    result = fake("sleep").run(session(tmp_path, timeout_s=2))
    assert result.stop_reason is StopReason.TIMEOUT
    assert result.cost_usd is None


def test_c5_a_crashing_or_missing_runtime_is_an_error(tmp_path: Path) -> None:
    crashed = fake("crash").run(session(tmp_path))
    assert crashed.stop_reason is StopReason.ERROR and "not logged in" in crashed.summary
    missing = ClaudeCodeRuntime(("no-such-claude-for-ariane",)).run(session(tmp_path))
    assert missing.stop_reason is StopReason.ERROR
    assert "no-such-claude-for-ariane" in missing.summary


def test_c5_recorded_fixture_round_trips_through_the_runtime(tmp_path: Path) -> None:
    result = fake("fixture", str(FIXTURES / "claude_budget.json")).run(session(tmp_path))
    assert result.stop_reason is StopReason.BUDGET


def test_c6_no_user_plugins_setting_sources_are_project_and_local(tmp_path: Path) -> None:
    argv = ClaudeCodeRuntime().command(session(tmp_path))
    assert argv[argv.index("--setting-sources") + 1] == "project,local"
