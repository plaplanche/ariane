"""C5: a session that sends no event for `idle_minutes` is killed as a timeout (ADR 0045)."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_c5_opencode import opencode_data
from test_process import _assert_stopped, _wait_for

from ariane import config, flow, process, runtime
from ariane.claude_code import ClaudeCodeRuntime
from ariane.opencode import OpenCodeRuntime
from ariane.runtime import Session, StopReason, last_event, session_for
from ariane.tracker import InMemoryTracker

from conftest import PY, FakeRuntime, Project, make_config
from test_flow import environ, journal, start, worktree

HERE = Path(__file__).resolve().parent

# The usage both idle sessions streamed before going silent, as the journal words it.
USAGE = "tokens 123 in, 6 cache read, 7 cache write, 45 out"

# Print one line, start a grandchild writing a heartbeat to argv[1], then stay silent.
SILENT = """
import subprocess, sys, time
child = (
    "import pathlib, sys, time\\n"
    "p = pathlib.Path(sys.argv[1])\\n"
    "while True:\\n"
    "    p.write_text(str(time.time()))\\n"
    "    time.sleep(0.1)\\n"
)
subprocess.Popen([sys.executable, "-c", child, sys.argv[1]])
print("started", flush=True)
time.sleep(60)
"""

TICKING = "import time\nfor i in range(6):\n    print(i, flush=True)\n    time.sleep(1)\n"

CLAUDE_TOOL_CALL = {
    "type": "assistant",
    "message": {
        "id": "msg_1",
        "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "x"}}],
        "usage": {
            "input_tokens": 123,
            "output_tokens": 45,
            "cache_read_input_tokens": 6,
            "cache_creation_input_tokens": 7,
        },
    },
}
OPENCODE_STEP = {
    "type": "step_finish",
    "part": {
        "reason": "tool-calls",
        "tokens": {"input": 123, "output": 45, "cache": {"read": 6, "write": 7}},
    },
}
OPENCODE_TOOL_CALL = {
    "type": "tool_use",
    "part": {"tool": "bash", "callID": "c1", "state": {"input": {"command": "x"}}},
}


def test_c5_idle_stream_kills_a_silent_command_and_its_whole_tree(tmp_path: Path) -> None:
    beat = tmp_path / "beat.txt"
    lines: list[str] = []

    def seen(line: str) -> bool:
        lines.append(line)
        return False

    done = process.stream(
        [PY, "-c", SILENT, str(beat)],
        cwd=tmp_path,
        on_line=seen,
        timeout_s=60,
        idle_timeout_s=1.5,
    )
    assert done.idle and not done.timed_out and not done.stopped
    assert done.returncode is None and not done.ok
    assert lines == ["started"]
    assert done.duration_s < 30
    _wait_for(beat)
    _assert_stopped(beat)


def test_c5_idle_stream_a_command_printing_every_second_is_not_killed(tmp_path: Path) -> None:
    done = process.stream(
        [PY, "-c", TICKING],
        cwd=tmp_path,
        on_line=lambda line: False,
        timeout_s=60,
        idle_timeout_s=4,
    )
    assert done.ok and not done.idle
    assert done.duration_s > 4
    assert done.stdout.split() == ["0", "1", "2", "3", "4", "5"]


def test_c5_idle_total_limit_still_applies_and_is_not_idle(tmp_path: Path) -> None:
    done = process.stream(
        [PY, "-c", TICKING], cwd=tmp_path, on_line=lambda line: False, timeout_s=1.5
    )
    assert done.timed_out and not done.idle


def test_c5_idle_last_event_names_the_event_type_and_the_tool() -> None:
    assert last_event(json.dumps(CLAUDE_TOOL_CALL) + "\n") == "assistant (tool Bash)"
    assert last_event('{"type":"x"}\n' + json.dumps(OPENCODE_TOOL_CALL)) == "tool_use (tool bash)"
    codex = {"type": "item.started", "item": {"type": "command_execution"}}
    assert last_event(json.dumps(codex)) == "item.started (tool command_execution)"
    assert last_event('{"type":"system","subtype":"init"}\n') == "system"
    assert last_event("") == "none"
    assert last_event("plain text") == "not a JSON event"


def claude_session(tmp_path: Path, idle_s: float) -> Session:
    return Session(
        role="implementer",
        model="m",
        tools=("Bash",),
        max_budget_usd=1,
        max_tokens=None,
        timeout_s=60,
        cwd=tmp_path,
        prompt="go",
        env=dict(os.environ),
        idle_timeout_s=idle_s,
    )


def write_events(path: Path, *events: dict[str, Any]) -> Path:
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return path


def fake_claude(events: Path) -> ClaudeCodeRuntime:
    return ClaudeCodeRuntime(
        (PY, str(HERE / "fake_claude.py"), "stream", str(events), "-", "hang", "--")
    )


def test_c5_idle_claude_code_session_is_a_timeout_naming_the_last_tool(tmp_path: Path) -> None:
    events = write_events(tmp_path / "events.jsonl", CLAUDE_TOOL_CALL)
    result = fake_claude(events).run(claude_session(tmp_path, 1.5))
    assert result.stop_reason is StopReason.TIMEOUT
    assert result.summary == (
        "no activity for 0.025 min (idle limit); last event: assistant (tool Bash)"
    )
    assert (result.input_tokens, result.output_tokens) == (123, 45)
    assert (result.cache_read_tokens, result.cache_write_tokens) == (6, 7)
    assert result.cost_usd is None


def test_c5_idle_claude_code_journal_and_stop_line_show_the_idle_summary(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    events = write_events(tmp_path / "events.jsonl", CLAUDE_TOOL_CALL)
    cfg = make_config()
    cfg = replace(cfg, implementer=replace(cfg.implementer, idle_minutes=0.025))
    outcome = flow.start(
        7,
        repo_root=project.root,
        config=cfg,
        tracker=tracker,
        runtime=fake_claude(events),
        environ=environ(),
    )
    summary = "no activity for 0.025 min (idle limit); last event: assistant (tool Bash)"
    assert outcome.exit_code == 1
    assert f"stopped: timeout ({summary})" in outcome.line
    text = journal(project)
    assert "Implementer session stopped: timeout" in text
    assert summary in text
    assert USAGE in text
    assert "its work is kept on the branch" in outcome.line


def test_c5_idle_opencode_reviewer_stops_with_timeout_and_the_summary_in_the_journal(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    events = write_events(tmp_path / "events.jsonl", OPENCODE_STEP, OPENCODE_TOOL_CALL)
    dump = tmp_path / "dump.json"
    reviewer = OpenCodeRuntime(
        (PY, str(HERE / "fake_opencode.py"), str(events), str(dump), "0", "hang"),
        model="openai/gpt-x",
    )
    cfg = make_config()
    agent = replace(
        cfg.reviewer,
        runtime=config.OPENCODE,
        model="openai/gpt-x",
        tools=("read", "glob", "grep"),
        max_tokens=1000,
        idle_minutes=0.025,
    )
    routed = runtime.RoutedRuntime({"implementer": FakeRuntime(), "reviewer": reviewer})
    outcome = flow.start(
        7,
        repo_root=project.root,
        config=replace(cfg, reviewer=agent),
        tracker=tracker,
        runtime=routed,
        environ={**environ(), "OPENAI_API_KEY": "k"},
    )
    summary = "no activity for 0.025 min (idle limit); last event: tool_use (tool bash)"
    assert outcome.exit_code == 1
    assert f"the reviewer session stopped: timeout ({summary})" in outcome.line
    text = journal(project)
    assert "Reviewer session 1 stopped: timeout" in text
    assert summary in text
    assert USAGE in text


def test_c5_idle_a_finished_session_is_unchanged(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert start(project, tracker, FakeRuntime()).exit_code == 0
    assert "idle limit" not in journal(project)
    assert (worktree(project) / "app.txt").exists()


@pytest.mark.parametrize("role", ["implementer", "reviewer"])
@pytest.mark.parametrize("value", [1, 2, 0, -1])
def test_c5_idle_minutes_at_or_above_the_time_limit_zero_or_negative_is_refused(
    role: str, value: float
) -> None:
    data = opencode_data()
    data["agents"][role]["idle_minutes"] = value
    with pytest.raises(config.ConfigError, match=rf"agents\.{role}\.idle_minutes"):
        config.parse(data)


def test_c5_idle_minutes_default_is_10_or_none_and_a_value_is_kept() -> None:
    data = opencode_data()
    parsed = config.parse(data)
    assert parsed.implementer.idle_minutes is None  # timeout_minutes = 1
    data["agents"]["implementer"]["timeout_minutes"] = 10
    assert config.parse(data).implementer.idle_minutes is None
    data["agents"]["implementer"]["timeout_minutes"] = 30
    assert config.parse(data).implementer.idle_minutes == 10
    data["agents"]["reviewer"]["timeout_minutes"] = 20
    data["agents"]["reviewer"]["idle_minutes"] = 5
    reviewer = config.parse(data).reviewer
    assert reviewer.idle_minutes == 5
    session = session_for(reviewer, "reviewer", cwd=Path("."), prompt="p", env={})
    assert session.idle_timeout_s == 300


def test_c5_idle_session_without_an_idle_limit_has_none() -> None:
    session = session_for(
        make_config().implementer, "implementer", cwd=Path("."), prompt="p", env={}
    )
    assert session.idle_timeout_s is None
