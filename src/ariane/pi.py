"""pi as an agent runtime, for the reviewer role: the official CLI only (ADR 0051)."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ariane import process
from ariane.config_schema import PI_PROVIDER_KEYS as PROVIDER_KEYS
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

# pi's isolation flags (ADR 0051): no session file, extension, skill, prompt template, theme,
# context file or startup network operation.
ISOLATION = (
    "--no-session",
    "--no-extensions",
    "--no-skills",
    "--no-prompt-templates",
    "--no-themes",
    "--no-context-files",
    "--offline",
)
LOGIN_NEXT = "run pi and /login, or set agents.reviewer.api_key_env"
AGENT_DIR = "PI_CODING_AGENT_DIR"

# Cloud credentials pi would also pick up (Amazon Bedrock, Google Vertex).
_CLOUD_PREFIXES = ("AWS_", "GOOGLE_APPLICATION_CREDENTIALS")

_FENCE = re.compile(r"```(?:json)?[ \t]*\n(.*?)\n[ \t]*```", re.DOTALL)
_NO_KEY = re.compile(r"No API key found for ([^\s.]+)")


def provider(model: str) -> str:
    return model.partition("/")[0].lower()


def agent_dir(env: Mapping[str, str], home: Path) -> Path:
    """pi's folder (`$PI_CODING_AGENT_DIR`, else `~/.pi/agent`), absolute: pi runs in the review
    tree, so a relative value is resolved once here, for the guard and the process (ADR 0031)."""
    return Path(env.get(AGENT_DIR) or home / ".pi" / "agent").absolute()


def no_credentials(name: str) -> str:
    return f"pi has no credentials for {name}"


class PiRuntime:
    name = "pi"

    def __init__(self, executable: Sequence[str] = ("pi",), api_key_env: str | None = None) -> None:
        self.executable = tuple(executable)
        self.api_key_env = api_key_env
        # pi's folder (settings, `auth.json`), and the configured key's variable, if any.
        self.login_variables: tuple[str, ...] = (AGENT_DIR, *([api_key_env] if api_key_env else []))

    def command(self, session: Session) -> list[str]:
        return [
            *self.executable,
            "-p",
            "--mode",
            "json",
            *ISOLATION,
            "--tools",
            ",".join(session.tools),
            "--model",
            session.model,
        ]

    def environment(self, session: Session) -> dict[str, str]:
        """No provider key, except the configured one under the provider's own variable."""
        env = _environment(session.env, self.api_key_env, provider(session.model))
        if env.get(AGENT_DIR):
            env[AGENT_DIR] = str(agent_dir(env, Path.home()))
        env["PI_TELEMETRY"] = "0"
        return env

    def describe(self) -> str:
        """The runtime and its version for the journal (`pi --version`)."""
        try:
            done = process.run([*self.executable, "--version"], cwd=Path.cwd(), timeout_s=30)
            version = done.stdout.strip().splitlines()[0] if done.ok and done.stdout else ""
        except (process.CommandNotFoundError, OSError):
            version = ""
        return f"pi {version or '(version unknown)'}"

    def run(self, session: Session) -> SessionResult:
        if self.api_key_env is not None and not session.env.get(self.api_key_env):
            message = f"agents.reviewer.api_key_env: variable {self.api_key_env} is not set"
            return SessionResult.failed(StopReason.ERROR, message)
        events = Events(session.max_tokens, session.max_budget_usd)
        try:
            # pi merges piped standard input into the prompt in print mode: no file is written.
            completed = process.stream(
                self.command(session),
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
        missing = _NO_KEY.search(f"{completed.stderr}\n{completed.stdout}")
        if missing is not None and not events.messages:
            summary = no_credentials(missing.group(1))
            return events.result(StopReason.ERROR, summary).with_next(LOGIN_NEXT)
        if events.error is not None:
            return events.result(StopReason.ERROR, events.error)
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout).strip()[-OUTPUT_TAIL_CHARS:]
            return events.result(StopReason.ERROR, f"pi exit {completed.returncode}: {tail}")
        if events.stop_reason != "stop":
            reason = events.stop_reason or "none"
            return events.result(StopReason.ERROR, f"no final assistant message (stop {reason})")
        return events.result(StopReason.FINISHED, events.text, structured=events.answer())


def _environment(base: Mapping[str, str], api_key_env: str | None, name: str) -> dict[str, str]:
    key = base.get(api_key_env) if api_key_env else None
    kept = api_key_env.upper() if api_key_env else None
    keys = set(PROVIDER_KEYS.values())

    def dropped(variable: str) -> bool:
        # Case-insensitive, as on Windows; a name ending in `_` is a prefix (ADR 0024).
        upper = variable.upper()
        own = kept is not None and (upper.startswith(kept) if kept.endswith("_") else upper == kept)
        return (
            own or upper in keys or upper.endswith("_API_KEY") or upper.startswith(_CLOUD_PREFIXES)
        )

    env = {variable: value for variable, value in base.items() if not dropped(variable)}
    if key and name in PROVIDER_KEYS:
        env[PROVIDER_KEYS[name]] = key
    return env


def _message(session: Session) -> str:
    if session.json_schema is None:
        return session.prompt
    schema = json.dumps(session.json_schema, indent=2)
    return (
        f"{session.prompt}\n\nYour last message must be one fenced ```json block holding the"
        f" answer, valid against this JSON Schema, and nothing after it:\n\n```json\n{schema}\n```"
    )


class Events:
    """What `pi --mode json` says: usage of each assistant `message_end`, the final answer."""

    def __init__(self, max_tokens: int | None, max_budget_usd: float | None = None) -> None:
        self.max_tokens = max_tokens
        self.max_budget_usd = max_budget_usd
        self.input = self.cache_read = self.cache_write = self.output = 0
        self.cost = 0.0
        self.cost_seen = False  # pi reported a cost, even 0
        self.messages = 0
        self.text = ""
        self.stop_reason: str | None = None
        self.error: str | None = None
        self.cap: str | None = None
        self.stop_text = ""

    @property
    def total(self) -> int:
        return self.input + self.cache_read + self.cache_write + self.output

    def add_line(self, line: str) -> bool:
        """Count one event line; True when a cap is reached and the session must stop."""
        event = json_object(line)
        if event is None:
            return False
        kind = event.get("type")
        if kind == "message_end":
            return self._message_end(event.get("message"))
        if kind == "agent_end":
            self._agent_end(event.get("messages"))
        elif kind == "auto_retry_start":
            self.error = None  # pi tries again: the next messages settle it
        elif kind == "auto_retry_end" and event.get("success") is False:
            final = event.get("finalError")
            self.error = f"pi gave up retrying: {final if isinstance(final, str) else 'error'}"
        return False

    def _message_end(self, message: Any) -> bool:
        if not _is_assistant(message):
            return False
        usage = message.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        cost = usage.get("cost")
        self.messages += 1
        self.input += as_int(usage.get("input")) or 0
        self.output += as_int(usage.get("output")) or 0
        self.cache_read += as_int(usage.get("cacheRead")) or 0
        self.cache_write += as_int(usage.get("cacheWrite")) or 0
        total = as_number(cost.get("total")) if isinstance(cost, dict) else None
        if total is not None:
            self.cost += total
            self.cost_seen = True
        self._settle(message)
        if self.max_tokens is not None and self.total >= self.max_tokens:
            self.cap = token_cap(self.max_tokens)
            self.stop_text = f"stopped by Ariane at {self.total} tokens"
        elif self.cost_seen and self.max_budget_usd is not None:
            if self.cost >= self.max_budget_usd:
                self.cap = cost_cap(self.max_budget_usd)
                self.stop_text = f"stopped by Ariane at {self.cost:.4f} USD"
        return self.cap is not None

    def _agent_end(self, messages: Any) -> None:
        """The last assistant message of the run is the answer (usage was counted already)."""
        replies = [m for m in messages if _is_assistant(m)] if isinstance(messages, list) else []
        if replies:
            self._settle(replies[-1])

    def _settle(self, message: dict[str, Any]) -> None:
        reason = message.get("stopReason")
        self.stop_reason = reason if isinstance(reason, str) else None
        self.text = _text(message)
        if self.stop_reason in ("error", "aborted"):
            detail = message.get("errorMessage")
            self.error = f"pi stop {self.stop_reason}: {detail if isinstance(detail, str) else ''}"
        else:
            self.error = None

    @property
    def reported_cost(self) -> float | None:
        """The summed cost pi reported (0 included), or None when no message reported one."""
        return self.cost if self.cost_seen else None

    def answer(self) -> Any:
        """The last message's fenced JSON block (else the whole text as JSON), if it parses."""
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
        seen = self.messages > 0
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
        )


def _is_assistant(message: Any) -> bool:
    return isinstance(message, dict) and message.get("role") == "assistant"


def _text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    blocks = content if isinstance(content, list) else []
    return "".join(
        b["text"]
        for b in blocks
        if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)
    )
