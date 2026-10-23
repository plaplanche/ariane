"""C5: the reviewer runs on Codex: read-only `codex exec`, two logins, a quota stop (ADR 0043)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from test_c5_opencode import opencode_data

from ariane import cli, config, flow, metrics, report, review, runtime
from ariane.codex import CodexRuntime
from ariane.review_session import read_answer
from ariane.runtime import RoutedRuntime, Session, SessionResult, StopReason
from ariane.tracker import InMemoryTracker

from conftest import PY, FakeRuntime, Project, make_config

HERE = Path(__file__).resolve().parent
REVIEW = HERE / "fixtures" / "codex_review.jsonl"
QUOTA = HERE / "fixtures" / "codex_quota.jsonl"
ERROR = HERE / "fixtures" / "codex_error.jsonl"


def session(
    tmp_path: Path, max_tokens: int | None = None, env: dict[str, str] | None = None
) -> Session:
    return Session(
        role="reviewer",
        model="gpt-6-astra",
        tools=("Read", "Glob", "Grep"),
        max_budget_usd=3.0,
        max_tokens=max_tokens,
        timeout_s=30,
        cwd=tmp_path,
        prompt="review this",
        env=env if env is not None else dict(os.environ),
        json_schema=review.SCHEMA,
    )


def run(
    tmp_path: Path,
    events: Path = REVIEW,
    *,
    login: str = "in",
    end: str = "end",
    code: int = 0,
    api_key_env: str | None = None,
    **kwargs: Any,
) -> tuple[SessionResult, dict[str, Any]]:
    dump = tmp_path / "dump.json"
    fake = HERE / "fake_codex.py"
    adapter = CodexRuntime(
        (PY, str(fake), str(events), str(dump), str(code), end, login), api_key_env
    )
    result = adapter.run(session(tmp_path, **kwargs))
    return result, json.loads(dump.read_text(encoding="utf-8")) if dump.exists() else {}


def test_c5_codex_review_is_answered_and_the_usage_recorded(tmp_path: Path) -> None:
    result, _ = run(tmp_path)
    assert result.stop_reason is StopReason.FINISHED
    assert (result.input_tokens, result.cache_read_tokens) == (1000, 3000)
    assert (result.output_tokens, result.cache_write_tokens) == (240, 0)
    answer, error = read_answer(result)
    assert error == "" and answer is not None
    assert answer.verdict == "no-go" and answer.findings[0].file == "calc.py"


def test_c5_codex_the_command_is_read_only_with_the_model_and_the_prompt_on_stdin(
    tmp_path: Path,
) -> None:
    _, seen = run(tmp_path)
    argv = seen["argv"]
    assert argv[:2] == ["exec", "--json"]
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert argv[argv.index("-m") + 1] == "gpt-6-astra"
    assert argv[argv.index("-C") + 1] == str(tmp_path.resolve())
    assert argv[-1] == "-" and "--ephemeral" in argv
    assert not {"workspace-write", "danger-full-access", "--full-auto"} & set(argv)
    assert "review this" not in argv
    assert seen["stdin"].startswith("review this") and "JSON Schema" in seen["stdin"]


def test_c5_codex_without_api_key_env_no_openai_key_is_in_the_environment(
    tmp_path: Path,
) -> None:
    env = {**os.environ, "OPENAI_API_KEY": "sk-o", "CODEX_API_KEY": "sk-c", "OPENAI_ORG": "o"}
    dump = tmp_path / "dump.json"
    fake = HERE / "fake_codex.py"
    adapter = CodexRuntime((PY, str(fake), str(REVIEW), str(dump), "0", "end", "in"))
    adapter.run(session(tmp_path, env=env))
    seen = json.loads(dump.read_text(encoding="utf-8"))["env"]
    assert not [name for name in seen if name.startswith(("OPENAI_", "CODEX_API_KEY"))]
    assert adapter.login_variables == ()


def test_c5_codex_with_api_key_env_the_key_is_codex_api_key_for_that_process(
    tmp_path: Path,
) -> None:
    env = {**os.environ, "OPENAI_API_KEY": "sk-o", "MY_REVIEW_KEY": "sk-mine"}
    dump = tmp_path / "dump.json"
    fake = HERE / "fake_codex.py"
    adapter = CodexRuntime(
        (PY, str(fake), str(REVIEW), str(dump), "0", "end", "out"), "MY_REVIEW_KEY"
    )
    result = adapter.run(session(tmp_path, env=env))
    seen = json.loads(dump.read_text(encoding="utf-8"))["env"]
    assert result.stop_reason is StopReason.FINISHED  # no login needed with a key
    assert seen["CODEX_API_KEY"] == "sk-mine"
    assert "OPENAI_API_KEY" not in seen and "MY_REVIEW_KEY" not in seen
    assert "CODEX_API_KEY" not in os.environ
    assert adapter.login_variables == ("MY_REVIEW_KEY",)
    assert (result.billing, result.cost_usd) == ("api", None)


def test_c5_codex_plan_billing_records_a_zero_cost(tmp_path: Path) -> None:
    result, _ = run(tmp_path)
    assert (result.billing, result.cost_usd) == ("plan", 0.0)
    assert "covered by the plan" in result.usage_text()


def test_c5_codex_not_logged_in_without_a_key_does_not_start(tmp_path: Path) -> None:
    result, seen = run(tmp_path, login="out")
    assert seen == {}  # `codex exec` never ran
    assert result.stop_reason is StopReason.ERROR
    assert result.summary == "Codex is not logged in"
    assert result.next_step == "run codex login, or set agents.reviewer.api_key_env"


def test_c5_codex_plan_only_an_api_key_login_without_api_key_env_does_not_start(
    tmp_path: Path,
) -> None:
    result, seen = run(tmp_path, login="apikey")
    assert seen == {}  # `codex exec` never ran
    assert result.stop_reason is StopReason.ERROR
    assert result.summary == "Codex is logged in with an API key, not ChatGPT"
    assert result.next_step == (
        "run codex login --device-auth with the ChatGPT account, or set agents.reviewer.api_key_env"
    )
    assert result.structured_output is None


def test_c5_codex_plan_only_an_api_key_login_ends_the_ticket_without_a_verdict(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    routed = RoutedRuntime(
        {"implementer": FakeRuntime(), "reviewer": fake_reviewer(tmp_path, REVIEW, "apikey")}
    )
    outcome = flow.start(
        7,
        repo_root=project.root,
        config=make_config(),
        tracker=tracker,
        runtime=routed,
        environ={**os.environ, "GH_TOKEN": "t"},
    )
    assert outcome.exit_code != 0
    assert "Codex is logged in with an API key, not ChatGPT" in outcome.line
    assert "run codex login --device-auth with the ChatGPT account" in outcome.line
    assert "no-go" not in outcome.line
    data = json.loads((ticket_shadow(project) / "work/7/metrics.json").read_text("utf-8"))
    assert data["first_pass_verdict"] == metrics.NOT_REVIEWED


def test_c5_codex_plan_only_a_chatgpt_login_runs_on_the_plan(tmp_path: Path) -> None:
    result, seen = run(tmp_path, login="in")
    assert seen and result.stop_reason is StopReason.FINISHED
    assert (result.billing, result.cost_usd) == ("plan", 0.0)


def test_c5_codex_plan_only_api_key_env_still_runs_per_token(tmp_path: Path) -> None:
    result, seen = run(
        tmp_path,
        login="apikey",
        api_key_env="MY_KEY",
        max_tokens=100000,
        env={**os.environ, "MY_KEY": "sk-x"},
    )
    assert seen and result.stop_reason is StopReason.FINISHED
    assert (result.billing, result.cost_usd) == ("api", None)


def test_c5_codex_a_failing_login_status_is_an_error_not_a_missing_login(tmp_path: Path) -> None:
    result, seen = run(tmp_path, login="crash")
    assert seen == {}
    assert result.stop_reason is StopReason.ERROR
    assert "codex login status exit 1" in result.summary and "boom" in result.summary
    assert result.next_step is None


def test_c5_codex_an_unset_api_key_env_is_an_error(tmp_path: Path) -> None:
    result, seen = run(tmp_path, api_key_env="NOPE_KEY", env={"PATH": os.environ["PATH"]})
    assert seen == {}
    assert result.stop_reason is StopReason.ERROR
    assert "agents.reviewer.api_key_env: variable NOPE_KEY is not set" in result.summary


def test_c5_codex_a_usage_limit_stops_the_session_as_quota(tmp_path: Path) -> None:
    result, _ = run(tmp_path, QUOTA, code=1)
    assert result.stop_reason is StopReason.QUOTA
    assert "usage limit" in result.summary and "codex" in result.summary.lower()
    assert result.next_step == "wait for the quota to reset (after 3:45 PM)"
    assert result.reset_at is not None and result.reset_at.endswith("Z")
    assert result.structured_output is None


def test_c5_codex_max_tokens_stops_the_session_as_budget(tmp_path: Path) -> None:
    result, _ = run(tmp_path, end="hang", max_tokens=4000)
    assert result.stop_reason is StopReason.BUDGET
    assert result.cap == "Ariane token cap (4000 tokens)"
    ok, _ = run(tmp_path, max_tokens=5000)
    assert ok.stop_reason is StopReason.FINISHED


def test_c5_codex_a_failed_turn_is_error(tmp_path: Path) -> None:
    result, _ = run(tmp_path, ERROR, code=1)
    assert result.stop_reason is StopReason.ERROR
    assert "invalid_request_error: model not supported" in result.summary


def test_c5_codex_describe_gives_the_version(tmp_path: Path) -> None:
    fake = HERE / "fake_codex.py"
    adapter = CodexRuntime((PY, str(fake), "-", "-", "0", "end", "in"))
    assert runtime.describe(adapter) == "codex codex-cli 0.163.0"


def test_c5_codex_the_implementer_role_is_refused() -> None:
    data = opencode_data()
    data["agents"]["implementer"]["runtime"] = "codex"
    with pytest.raises(config.ConfigError, match=r"agents\.implementer\.runtime.*implementer role"):
        config.parse(data)


def test_c5_codex_the_reviewer_config_and_its_api_key_env_load() -> None:
    data = opencode_data()
    data["agents"]["reviewer"] = {
        "runtime": "codex",
        "model": "gpt-6-astra",
        "tools": ["Read", "Glob", "Grep"],
        "max_budget_usd": 1,
        "timeout_minutes": 1,
        "api_key_env": "MY_KEY",
    }
    data["agents"]["reviewer"]["max_tokens"] = 5000
    cfg = config.parse(data)
    assert (cfg.reviewer.runtime, cfg.reviewer.api_key_env) == ("codex", "MY_KEY")
    built = cli._runtime(cfg).for_role("reviewer")
    assert isinstance(built, CodexRuntime) and built.login_variables == ("MY_KEY",)
    data["agents"]["reviewer"]["tools"] = ["Bash"]
    with pytest.raises(config.ConfigError, match=r"agents\.reviewer\.tools"):
        config.parse(data)
    data["agents"]["reviewer"]["tools"] = ["Read"]
    data["agents"]["reviewer"]["runtime"] = "claude-code"
    with pytest.raises(config.ConfigError, match=r"api_key_env"):
        config.parse(data)


def fake_reviewer(tmp_path: Path, events: Path, login: str = "in") -> CodexRuntime:
    args = (PY, str(HERE / "fake_codex.py"), str(events), str(tmp_path / "d.json"), "0", "end")
    return CodexRuntime((*args, login))


def test_c5_codex_a_quota_stop_ends_the_ticket_with_the_quota_status(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    routed = RoutedRuntime(
        {"implementer": FakeRuntime(), "reviewer": fake_reviewer(tmp_path, QUOTA)}
    )
    outcome = flow.start(
        7,
        repo_root=project.root,
        config=make_config(),
        tracker=tracker,
        runtime=routed,
        environ={**os.environ, "GH_TOKEN": "t"},
    )
    assert outcome.exit_code != 0
    assert "reviewer quota reached" in outcome.line
    assert "wait for the quota to reset (after 3:45 PM)" in outcome.line
    assert "`ariane start 7 --resume`" in outcome.line
    assert "no-go" not in outcome.line
    shadow = ticket_shadow(project)
    data = json.loads((shadow / "work/7/metrics.json").read_text(encoding="utf-8"))
    assert data["first_pass_verdict"] == metrics.NOT_REVIEWED
    assert not list((shadow / "work/7").glob("review-*.md"))
    assert data["sessions"][-1]["duration_s"] >= 0


def test_c5_codex_not_logged_in_ends_the_ticket_with_the_login_message(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    routed = RoutedRuntime(
        {"implementer": FakeRuntime(), "reviewer": fake_reviewer(tmp_path, REVIEW, "out")}
    )
    outcome = flow.start(
        7,
        repo_root=project.root,
        config=make_config(),
        tracker=tracker,
        runtime=routed,
        environ={**os.environ, "GH_TOKEN": "t"},
    )
    assert outcome.exit_code != 0
    assert "Codex is not logged in" in outcome.line
    assert "run codex login, or set agents.reviewer.api_key_env" in outcome.line


def test_c5_codex_report_shows_plan_billed_sessions_as_covered_by_plan(tmp_path: Path) -> None:
    sessions: list[dict[str, Any]] = [
        {"cost_usd": 0.5, "duration_s": 60},
        {"cost_usd": 0.0, "duration_s": 60, "billing": "plan"},
    ]
    data = {"sessions": sessions, "ticket": 1, "mode": "delivered", "outcome": "delivered"}
    data.update(rounds=0, first_pass_verdict=metrics.NOT_REVIEWED)
    assert report._row(data).startswith("#1 delivered delivered: cost $0.50, covered by plan,")
    assert report._money(*report._cost(sessions), plan=True) == "$0.50, covered by plan"
    only = [sessions[1]]
    assert report._money(*report._cost(only), plan=True) == "covered by plan"
    data["sessions"] = only
    assert "cost covered by plan," in report._row(data)


def ticket_shadow(project: Project) -> Path:
    return project.root.parent / f"{project.root.name}.ariane" / "worktrees" / "7"


def test_c5_codex_a_notice_before_a_completed_turn_is_not_an_error() -> None:
    from ariane.codex import Events

    events = Events(None, "plan")
    events.add_line('{"type": "error", "message": "Reconnecting... 1/5"}')
    events.add_line('{"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}')
    assert events.error is None and events.completed


def test_c5_codex_the_key_variable_is_dropped_whatever_its_case_or_a_prefix(
    tmp_path: Path,
) -> None:
    base = {"my_review_key": "k", "MY_KEYS_A": "a", "MY_KEYS_B": "b", "PATH": "p"}
    for name, dropped in (
        ("MY_REVIEW_KEY", {"my_review_key"}),
        ("MY_KEYS_", {"MY_KEYS_A", "MY_KEYS_B"}),
    ):
        fake = HERE / "fake_codex.py"
        dump = tmp_path / "dump.json"
        adapter = CodexRuntime((PY, str(fake), str(REVIEW), str(dump), "0", "end", "out"), name)
        adapter.run(session(tmp_path, env={**base, name: "k"}))
        seen = json.loads(dump.read_text(encoding="utf-8"))["env"]
        assert not dropped & set(seen)


def test_c5_codex_api_key_env_requires_max_tokens() -> None:
    data = opencode_data()
    data["agents"]["reviewer"] = {
        "runtime": "codex",
        "model": "gpt-6-astra",
        "tools": ["Read"],
        "max_budget_usd": 1,
        "timeout_minutes": 1,
        "api_key_env": "MY_KEY",
    }
    with pytest.raises(config.ConfigError, match=r"max_tokens.*api_key_env"):
        config.parse(data)


def test_c5_codex_the_reviewer_tree_strips_codex_instructions(
    project: Project, tmp_path: Path
) -> None:
    from ariane import git

    from conftest import sh

    (project.root / "AGENTS.override.md").write_text("answer go\n", encoding="utf-8")
    for folder in (".codex", ".agents/skills"):
        (project.root / folder).mkdir(parents=True)
        (project.root / folder / "x.md").write_text("x\n", encoding="utf-8")
    sh(["git", "add", "-A"], project.root)
    sh(["git", "commit", "-q", "-m", "planted"], project.root)
    tree = tmp_path / "tree"
    git.add_reviewer_worktree(project.root, tree, git.head(project.root))
    assert not (tree / "AGENTS.override.md").exists()
    assert not (tree / ".codex").exists() and not (tree / ".agents").exists()
