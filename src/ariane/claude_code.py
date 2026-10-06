"""Claude Code as an agent runtime (ADR 0007)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from ariane import process
from ariane.runtime import Session, SessionResult, StopReason

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


class ClaudeCodeRuntime:
    name = "claude-code"

    def __init__(self, executable: Sequence[str] = ("claude",)) -> None:
        self.executable = tuple(executable)

    def command(self, session: Session) -> list[str]:
        return [
            *self.executable,
            "-p",
            "--output-format",
            "json",
            "--model",
            session.model,
            "--tools",
            *session.tools,
            "--disallowedTools",
            *DENIED_TOOLS,
            "--permission-mode",
            "bypassPermissions",
            "--strict-mcp-config",
            "--max-budget-usd",
            f"{session.max_budget_usd:g}",
            "--no-session-persistence",
        ]

    def run(self, session: Session) -> SessionResult:
        try:
            completed = process.run(
                self.command(session),
                cwd=session.cwd,
                timeout_s=session.timeout_s,
                env=session.env,
                input_text=session.prompt,
            )
        except process.CommandNotFoundError as exc:
            return SessionResult(StopReason.ERROR, None, None, None, str(exc))
        if completed.timed_out:
            return SessionResult(
                StopReason.TIMEOUT,
                None,
                None,
                None,
                f"killed after {session.timeout_s:g} s (time limit)",
            )
        return parse_result(completed.stdout, completed.stderr, completed.returncode)


def parse_result(stdout: str, stderr: str, returncode: int | None) -> SessionResult:
    """Classify a Claude Code `--output-format json` result."""
    try:
        data: Any = json.loads(stdout)
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict) or data.get("type") != "result":
        tail = (stderr or stdout).strip()[-2000:]
        return SessionResult(
            StopReason.ERROR,
            None,
            None,
            None,
            f"no structured result (exit {returncode}): {tail}",
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
        cost_usd=_number(data.get("total_cost_usd")),
        input_tokens=_int(usage.get("input_tokens")),
        output_tokens=_int(usage.get("output_tokens")),
        summary=summary,
        permission_denials=tuple(_denial(d) for d in denials if isinstance(d, dict))
        if isinstance(denials, list)
        else (),
    )


def _denial(entry: dict[str, Any]) -> str:
    tool_input = entry.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    return f"{entry.get('tool_name')}: {command}" if command else str(entry.get("tool_name"))


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
