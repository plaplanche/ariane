"""Claude Code as an agent runtime (ADR 0007)."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from typing import Any

from ariane import process
from ariane.attempts import AttemptTally
from ariane.runtime import (
    OUTPUT_TAIL_CHARS,
    Session,
    SessionResult,
    StopReason,
    as_int,
    as_number,
    cost_cap,
    json_object,
    timeout_summary,
    token_cap,
)

# First layer of the push guard; the worktree push URL and the post-session check are the others.
DENIED_TOOLS = (
    "Bash(git push:*)",
    "Bash(git checkout:*)",
    "Bash(git switch:*)",
    "Bash(git rebase:*)",
    "Bash(git reset:*)",
    "Bash(gh:*)",
)

_SUBTYPES = {
    "success": StopReason.FINISHED,
    "error_max_budget_usd": StopReason.BUDGET,
    "error_max_turns": StopReason.TURNS,
}


def schema_argument(schema: Mapping[str, Any]) -> dict[str, Any]:
    """The schema for `--json-schema`: Claude Code rejects a draft 2020-12 `$schema` (#73)."""
    return {k: v for k, v in schema.items() if k != "$schema"}


class ClaudeCodeRuntime:
    name = "claude-code"
    login_variables: tuple[str, ...] = ("ANTHROPIC_", "CLAUDE_")

    def __init__(self, executable: Sequence[str] = ("claude",)) -> None:
        self.executable = tuple(executable)

    def command(self, session: Session) -> list[str]:
        schema = (
            ["--json-schema", json.dumps(schema_argument(session.json_schema))]
            if session.json_schema
            else []
        )
        if session.role == "reviewer":
            # ADR 0031: nothing is loaded from the tree under review; it is only read.
            isolation = [
                "--restricted",
                *(a for d in session.add_dirs for a in ("--add-dir", str(d))),
            ]
        else:
            isolation = [
                "--permission-mode",
                "bypassPermissions",
                "--setting-sources",
                "project,local",
            ]
        return [
            *self.executable,
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--model",
            session.model,
            "--tools",
            *session.tools,
            "--disallowedTools",
            *DENIED_TOOLS,
            *isolation,
            "--strict-mcp-config",
            "--max-budget-usd",
            f"{session.max_budget_usd:g}",
            "--no-session-persistence",
            *schema,
        ]

    def run(self, session: Session) -> SessionResult:
        tally = TokenTally(session.max_tokens)
        result = self._run(session, tally)
        return dataclasses.replace(result, attempts=tally.attempts.attempts)

    def _run(self, session: Session, tally: TokenTally) -> SessionResult:
        try:
            completed = process.stream(
                self.command(session),
                cwd=session.cwd,
                on_line=tally.add_line,
                timeout_s=session.timeout_s,
                env={**session.env, "ARIANE_ROLE": session.role},
                input_text=session.prompt,
            )
        except process.CommandNotFoundError as exc:
            return SessionResult.failed(StopReason.ERROR, str(exc))
        if completed.stopped:
            return tally.stopped_result()
        if completed.timed_out:
            return SessionResult.failed(StopReason.TIMEOUT, timeout_summary(session.timeout_s))
        result = parse_result(completed.stdout, completed.stderr, completed.returncode)
        if result.stop_reason is StopReason.BUDGET:
            return dataclasses.replace(result, cap=cost_cap(session.max_budget_usd))
        return result


class TokenTally:
    """Running token total of a stream: the latest usage of each message id counts once."""

    def __init__(self, max_tokens: int | None) -> None:
        self.max_tokens = max_tokens
        self._usage: dict[str, tuple[int, int, int, int]] = {}
        self.attempts = AttemptTally()

    @property
    def parts(self) -> tuple[int, int, int, int]:
        """Input, cache read, cache write and output tokens."""
        return (
            sum(u[0] for u in self._usage.values()),
            sum(u[1] for u in self._usage.values()),
            sum(u[2] for u in self._usage.values()),
            sum(u[3] for u in self._usage.values()),
        )

    @property
    def total(self) -> int:
        return sum(self.parts)

    def add_line(self, line: str) -> bool:
        """Count one stream line; True when the cap is reached and the session must stop."""
        event = json_object(line)
        if event is None or event.get("type") != "assistant":
            return False
        message = event.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("id"), str):
            return False
        self._count_attempts(message)
        usage = message.get("usage")
        if not isinstance(usage, dict):
            return False
        self._usage[message["id"]] = (
            as_int(usage.get("input_tokens")) or 0,
            as_int(usage.get("cache_read_input_tokens")) or 0,
            as_int(usage.get("cache_creation_input_tokens")) or 0,
            as_int(usage.get("output_tokens")) or 0,
        )
        return self.max_tokens is not None and self.total >= self.max_tokens

    def _count_attempts(self, message: dict[str, Any]) -> None:
        """Shell commands of the message's `tool_use` blocks (a streamed message repeats them)."""
        content = message.get("content")
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_input = block.get("input")
            command = tool_input.get("command") if isinstance(tool_input, dict) else None
            if isinstance(command, str):
                self.attempts.add_command(command, str(block.get("id")))

    def stopped_result(self) -> SessionResult:
        read, cache_read, cache_write, out = self.parts
        return SessionResult(
            StopReason.BUDGET,
            None,
            read,
            out,
            cache_read,
            cache_write,
            f"stopped by Ariane at {self.total} tokens",
            cap=token_cap(self.max_tokens),
        )


def parse_result(stdout: str, stderr: str, returncode: int | None) -> SessionResult:
    """Classify a Claude Code result: one JSON object, or a stream whose last event is one."""
    data = _final_event(stdout)
    if data is None:
        tail = (stderr or stdout).strip()[-OUTPUT_TAIL_CHARS:]
        return SessionResult.failed(
            StopReason.ERROR, f"no structured result (exit {returncode}): {tail}"
        )
    reason = _SUBTYPES.get(str(data.get("subtype")), StopReason.ERROR)
    if reason is StopReason.FINISHED and data.get("is_error"):
        reason = StopReason.ERROR
    raw_usage = data.get("usage")
    usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
    errors = data.get("errors")
    summary = data.get("result")
    if not isinstance(summary, str) or not summary:
        subtype = str(data.get("subtype"))
        summary = "; ".join(map(str, errors)) if isinstance(errors, list) else subtype
    denials = data.get("permission_denials")
    return SessionResult(
        stop_reason=reason,
        cost_usd=as_number(data.get("total_cost_usd")),
        input_tokens=as_int(usage.get("input_tokens")),
        output_tokens=as_int(usage.get("output_tokens")),
        cache_read_tokens=as_int(usage.get("cache_read_input_tokens")),
        cache_write_tokens=as_int(usage.get("cache_creation_input_tokens")),
        summary=summary,
        structured_output=data.get("structured_output"),
        permission_denials=tuple(_denial(d) for d in denials if isinstance(d, dict))
        if isinstance(denials, list)
        else (),
    )


def _final_event(stdout: str) -> dict[str, Any] | None:
    candidates = [stdout, *reversed(stdout.splitlines())]
    for text in candidates:
        try:
            data: Any = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("type") == "result":
            return data
    return None


def _denial(entry: dict[str, Any]) -> str:
    tool_input = entry.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    return f"{entry.get('tool_name')}: {command}" if command else str(entry.get("tool_name"))
