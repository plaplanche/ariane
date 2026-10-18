"""opencode as an agent runtime, for the reviewer role (ADR 0015, ADR 0029)."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path
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
    idle_summary,
    json_object,
    timeout_summary,
    token_cap,
)

# opencode has no turn option on its command line: the agent's `steps` is the turn cap.
STEPS = 20

# Login variables of the providers whose key is not `<PROVIDER>_API_KEY`.
_PROVIDER_KEYS = {
    "google": ("GOOGLE_GENERATIVE_AI_API_KEY", "GEMINI_API_KEY"),
    "azure": ("AZURE_API_KEY", "AZURE_RESOURCE_NAME"),
    "amazon-bedrock": ("AWS_",),
}

_FENCE = re.compile(r"```(?:json)?[ \t]*\n(.*?)\n[ \t]*```", re.DOTALL)
TITLE_NOTE = "the title call's usage is not reported by opencode"


def login_variables(model: str) -> tuple[str, ...]:
    """The provider keys a `<provider>/<model>` needs in the agent's environment."""
    provider = model.partition("/")[0].lower()
    if provider in _PROVIDER_KEYS:
        return _PROVIDER_KEYS[provider]
    return (f"{re.sub('[^A-Z0-9]', '_', provider.upper())}_API_KEY",)


def agent_name(role: str) -> str:
    return f"ariane-{role}"


def inline_config(role: str, tools: Sequence[str]) -> str:
    """`OPENCODE_CONFIG_CONTENT`: every tool denied but the role's, no autoupdate, no sharing."""
    permission = {"*": "deny", **{tool.lower(): "allow" for tool in tools}}
    config = {
        "autoupdate": False,
        "share": "disabled",
        "agent": {
            agent_name(role): {
                "description": f"Ariane {role}",
                "mode": "primary",
                "steps": STEPS,
                "permission": permission,
            }
        },
    }
    return json.dumps(config, separators=(",", ":"))


class OpenCodeRuntime:
    name = "opencode"

    def __init__(self, executable: Sequence[str] = ("opencode",), model: str | None = None) -> None:
        self.executable = tuple(executable)
        self.login_variables: tuple[str, ...] = login_variables(model) if model else ()

    def command(self, session: Session) -> list[str]:
        return [
            *self.executable,
            "run",
            "--pure",
            "--format",
            "json",
            "--model",
            session.model,
            "--agent",
            agent_name(session.role),
            "--dir",
            str(session.cwd.resolve()),
        ]

    def environment(self, session: Session) -> dict[str, str]:
        return {
            **session.env,
            "PWD": str(session.cwd.resolve()),
            "OPENCODE_CONFIG_CONTENT": inline_config(session.role, session.tools),
            "OPENCODE_DISABLE_CLAUDE_CODE": "1",
            "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
            "OPENCODE_DISABLE_AUTOUPDATE": "1",
            "ARIANE_ROLE": session.role,
        }

    def describe(self) -> str:
        """The runtime and its version for the journal (`opencode --version`)."""
        try:
            done = process.run([*self.executable, "--version"], cwd=Path.cwd(), timeout_s=30)
            version = done.stdout.strip().splitlines()[0] if done.ok and done.stdout else ""
        except (process.CommandNotFoundError, OSError):
            version = ""
        return f"opencode {version or '(version unknown)'}; {TITLE_NOTE}"

    def run(self, session: Session) -> SessionResult:
        events = Events(session.max_tokens, session.max_budget_usd)
        command = self.command(session)
        try:
            completed = process.stream(
                command,
                cwd=session.cwd,
                on_line=events.add_line,
                timeout_s=session.timeout_s,
                idle_timeout_s=session.idle_timeout_s,
                env=self.environment(session),
                input_text=_message(session),
            )
        except (process.CommandNotFoundError, OSError) as exc:
            return SessionResult.failed(StopReason.ERROR, str(exc))
        if completed.stopped:
            return events.result(StopReason.BUDGET, events.stop_text, cap=events.cap)
        if completed.idle and session.idle_timeout_s is not None:
            summary = idle_summary(session.idle_timeout_s, completed.stdout)
            return events.result(StopReason.TIMEOUT, summary)
        if completed.timed_out:
            return events.result(StopReason.TIMEOUT, timeout_summary(session.timeout_s))
        if events.error is not None:
            return events.result(StopReason.ERROR, events.error)
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout).strip()[-OUTPUT_TAIL_CHARS:]
            return events.result(StopReason.ERROR, f"opencode exit {completed.returncode}: {tail}")
        if not events.stopped_normally:
            return events.result(StopReason.ERROR, "no final step (reason stop) in the events")
        return events.result(StopReason.FINISHED, events.text, structured=events.answer())


def _message(session: Session) -> str:
    if session.json_schema is None:
        return session.prompt
    schema = json.dumps(session.json_schema, indent=2)
    return (
        f"{session.prompt}\n\nYour last message must be one fenced ```json block holding the"
        f" answer, valid against this JSON Schema, and nothing after it:\n\n```json\n{schema}\n```"
    )


class Events:
    """What the `--format json` events say: usage summed from `step_finish`, text, errors."""

    def __init__(self, max_tokens: int | None, max_budget_usd: float | None) -> None:
        self.max_tokens = max_tokens
        self.max_budget_usd = max_budget_usd
        self.input = self.cache_read = self.cache_write = self.output = 0
        self.cost = 0.0
        self.steps = 0
        self.text = ""
        self.error: str | None = None
        self.stopped_normally = False
        self.cap: str | None = None
        self.stop_text = ""
        self.attempts = AttemptTally()

    @property
    def total(self) -> int:
        return self.input + self.cache_read + self.cache_write + self.output

    def add_line(self, line: str) -> bool:
        """Count one event line; True when a cap is reached and the session must stop."""
        event = json_object(line)
        if event is None:
            return False
        kind, part = event.get("type"), event.get("part")
        if kind == "text" and isinstance(part, dict) and isinstance(part.get("text"), str):
            self.text = part["text"]
        elif kind == "tool_use" and isinstance(part, dict):
            self._tool_use(part)
        elif kind == "error":
            self.error = _error_text(event.get("error"))
        elif kind == "step_finish" and isinstance(part, dict):
            return self._step_finish(part)
        return False

    def _tool_use(self, part: dict[str, Any]) -> None:
        """A shell tool call: its command counts once, whatever the events repeat."""
        state = part.get("state")
        tool_input = state.get("input") if isinstance(state, dict) else None
        command = tool_input.get("command") if isinstance(tool_input, dict) else None
        call = str(part.get("callID") or part.get("id") or command)
        is_shell = str(part.get("tool")).lower() == "bash"
        if is_shell and isinstance(command, str):
            self.attempts.add_command(command, call)

    def _step_finish(self, part: dict[str, Any]) -> bool:
        tokens = part.get("tokens")
        tokens = tokens if isinstance(tokens, dict) else {}
        cache = tokens.get("cache")
        cache = cache if isinstance(cache, dict) else {}
        self.steps += 1
        self.input += as_int(tokens.get("input")) or 0
        self.output += as_int(tokens.get("output")) or 0
        self.cache_read += as_int(cache.get("read")) or 0
        self.cache_write += as_int(cache.get("write")) or 0
        self.cost += as_number(part.get("cost")) or 0.0
        self.stopped_normally = part.get("reason") == "stop"
        if self.max_tokens is not None and self.total >= self.max_tokens:
            self.cap = token_cap(self.max_tokens)
            self.stop_text = f"stopped by Ariane at {self.total} tokens"
        elif self.reported_cost is not None and self.max_budget_usd is not None:
            if self.reported_cost >= self.max_budget_usd:
                self.cap = cost_cap(self.max_budget_usd)
                self.stop_text = f"stopped by Ariane at {self.reported_cost:.4f} USD"
        return self.cap is not None

    @property
    def reported_cost(self) -> float | None:
        """A cost of 0 with tokens reported counts as "cost not reported"."""
        return self.cost if self.cost > 0 else None

    def answer(self) -> Any:
        """The last text part's fenced JSON block (else the whole text as JSON), if it parses."""
        blocks = _FENCE.findall(self.text)
        try:
            return json.loads(blocks[-1] if blocks else self.text)
        except json.JSONDecodeError:
            return None

    def result(
        self,
        reason: StopReason,
        summary: str,
        *,
        cap: str | None = None,
        structured: Any = None,
    ) -> SessionResult:
        seen = self.steps > 0
        return SessionResult(
            stop_reason=reason,
            cost_usd=self.reported_cost,
            input_tokens=self.input if seen else None,
            output_tokens=self.output if seen else None,
            cache_read_tokens=self.cache_read if seen else None,
            cache_write_tokens=self.cache_write if seen else None,
            summary=summary,
            cap=cap,
            structured_output=structured,
            attempts=self.attempts.attempts,
        )


def _error_text(error: Any) -> str:
    if not isinstance(error, dict):
        return "opencode reported an error"
    data = error.get("data")
    message = data.get("message") if isinstance(data, dict) else None
    status = data.get("statusCode") if isinstance(data, dict) else None
    name = str(error.get("name", "error"))
    detail = f"{message} (HTTP {status})" if message and status else str(message or "")
    return f"{name}: {detail}" if detail else name
