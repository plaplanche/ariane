"""C5: Ariane counts streamed usage, enforces its token cap and reads the final result."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from ariane import process
from ariane.claude_code import ClaudeCodeRuntime, TokenTally, parse_result
from ariane.runtime import Session, SessionResult, StopReason

from conftest import PY

HERE = Path(__file__).resolve().parent
STREAM = HERE / "fixtures" / "claude_stream_success.jsonl"


def session(tmp_path: Path, max_tokens: int | None) -> Session:
    return Session(
        role="implementer",
        model="m",
        tools=("Read",),
        max_budget_usd=1,
        max_tokens=max_tokens,
        timeout_s=30,
        cwd=tmp_path,
        prompt="go",
        env=dict(os.environ),
    )


def run_stream(
    tmp_path: Path, events: Path, max_tokens: int | None, pidfile: str = "-", end: str = "end"
) -> SessionResult:
    runtime = ClaudeCodeRuntime(
        (PY, str(HERE / "fake_claude.py"), "stream", str(events), pidfile, end, "--")
    )
    return runtime.run(session(tmp_path, max_tokens))


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_c5_budget_stream_fixture_is_finished_with_the_result_totals() -> None:
    raw = STREAM.read_text(encoding="utf-8")
    assert all(json.loads(line) for line in raw.splitlines())
    result = parse_result(raw, "", 0)
    assert result.stop_reason is StopReason.FINISHED
    assert result.cost_usd == 0.0133076
    assert (result.input_tokens, result.output_tokens) == (17, 191)
    assert (result.cache_read_tokens, result.cache_write_tokens) == (5656, 5885)


def test_c5_budget_stream_a_session_under_the_cap_finishes(tmp_path: Path) -> None:
    result = run_stream(tmp_path, STREAM, max_tokens=1_000_000)
    assert result.stop_reason is StopReason.FINISHED
    assert result.cost_usd == 0.0133076 and result.output_tokens == 191


def test_c5_budget_stream_events_repeating_a_message_id_count_once() -> None:
    tally = TokenTally(None)
    for line in STREAM.read_text(encoding="utf-8").splitlines():
        tally.add_line(line)
    # two messages, each streamed as two events with the same usage
    assert tally.total == (9 + 5656 + 3) + (8 + 229 + 5656 + 3)
    assert tally.parts == (17, 5656, 5885, 6)


def test_c5_budget_stream_the_cap_stops_the_session_and_the_process_tree(
    tmp_path: Path,
) -> None:
    pidfile = tmp_path / "child.pid"
    result = run_stream(tmp_path, STREAM, max_tokens=6000, pidfile=str(pidfile), end="hang")
    assert result.stop_reason is StopReason.BUDGET
    assert result.summary == "stopped by Ariane at 11564 tokens"
    assert result.cap is not None and "Ariane token cap (6000 tokens)" in result.cap
    pid = int(pidfile.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 5
    while alive(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not alive(pid)


def test_c5_budget_stream_a_stream_without_a_result_is_an_error(tmp_path: Path) -> None:
    lines = STREAM.read_text(encoding="utf-8").splitlines()[:-1]
    events = tmp_path / "events.jsonl"
    events.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = run_stream(tmp_path, events, max_tokens=None)
    assert result.stop_reason is StopReason.ERROR
    assert "no structured result" in result.summary


def test_c5_budget_stream_the_runtime_cost_cap_is_named() -> None:
    final = {"type": "result", "subtype": "error_max_budget_usd", "total_cost_usd": 1.0}
    assert parse_result(json.dumps(final), "", 0).stop_reason is StopReason.BUDGET


def test_c5_budget_stream_runtime_cost_stop_names_the_cost_cap(tmp_path: Path) -> None:
    final = {"type": "result", "subtype": "error_max_budget_usd", "total_cost_usd": 1.0}
    events = tmp_path / "events.jsonl"
    events.write_text(json.dumps(final) + "\n", encoding="utf-8")
    result = run_stream(tmp_path, events, max_tokens=None)
    assert result.stop_reason is StopReason.BUDGET
    assert result.cap == "runtime cost cap (1 USD)"


def test_c5_budget_stream_process_stream_reports_lines_and_stops_on_request(
    tmp_path: Path,
) -> None:
    seen: list[str] = []

    def on_line(line: str) -> bool:
        seen.append(line)
        return line == "two"

    code = "import time\nprint('one', flush=True)\nprint('two', flush=True)\ntime.sleep(60)"
    done = process.stream([PY, "-c", code], cwd=tmp_path, on_line=on_line, timeout_s=30)
    assert seen == ["one", "two"] and done.stopped and not done.timed_out


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "5"])
def test_c5_budget_stream_config_rejects_a_bad_token_cap(value: object) -> None:
    import copy

    from test_config import VALID

    from ariane import config

    data = copy.deepcopy(VALID)
    data["agents"]["implementer"]["max_tokens"] = value
    with pytest.raises(config.ConfigError, match=r"agents\.implementer\.max_tokens"):
        config.parse(data)
    data["agents"]["implementer"]["max_tokens"] = 1000
    assert config.parse(data).implementer.max_tokens == 1000
