"""Codex as an agent runtime, for the reviewer role: the official CLI only (ADR 0043)."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ariane import process
from ariane.runtime import (
    OUTPUT_TAIL_CHARS,
    Session,
    SessionResult,
    StopReason,
    as_int,
    json_object,
    timeout_summary,
    token_cap,
)

NOT_LOGGED_IN = "Codex is not logged in"
LOGIN_NEXT = "run codex login, or set agents.reviewer.api_key_env"
PLAN = "plan"
API = "api"

_FENCE = re.compile(r"```(?:json)?[ \t]*\n(.*?)\n[ \t]*```", re.DOTALL)
_USAGE_LIMIT = re.compile(r"usage[ _]limit", re.IGNORECASE)
_RESET = re.compile(r"try again (?:at|in|after) ([^.\n]+)", re.IGNORECASE)
# Variables that would bill per token behind a plan login's back.
_KEY_PREFIXES = ("OPENAI_", "CODEX_API_KEY")


class CodexRuntime:
    name = "codex"

    def __init__(
        self, executable: Sequence[str] = ("codex",), api_key_env: str | None = None
    ) -> None:
        self.executable = tuple(executable)
        self.api_key_env = api_key_env
        # The key's variable is the one login variable the reviewer's environment keeps.
        self.login_variables: tuple[str, ...] = (api_key_env,) if api_key_env else ()

    @property
    def billing(self) -> str:
        return API if self.api_key_env else PLAN

    def command(self, session: Session) -> list[str]:
        return [
            *self.executable,
            "exec",
            "--json",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--ephemeral",
            "-m",
            session.model,
            "-C",
            str(session.cwd.resolve()),
            "-",
        ]

    def environment(self, session: Session) -> dict[str, str]:
        """No OpenAI key, except the configured one, as `CODEX_API_KEY` for this process only."""
        return _environment(session.env, self.api_key_env)

    def describe(self) -> str:
        """The runtime and its version for the journal (`codex --version`)."""
        try:
            done = process.run([*self.executable, "--version"], cwd=Path.cwd(), timeout_s=30)
            version = done.stdout.strip().splitlines()[0] if done.ok and done.stdout else ""
        except (process.CommandNotFoundError, OSError):
            version = ""
        return f"codex {version or '(version unknown)'}"

    def logged_in(self, env: Mapping[str, str]) -> bool:
        """`codex login status` says the CLI holds a login (Ariane never reads the credentials)."""
        try:
            done = process.run(
                [*self.executable, "login", "status"], cwd=Path.cwd(), timeout_s=30, env=env
            )
        except (process.CommandNotFoundError, OSError):
            return True  # `run` reports the unstartable executable
        return done.ok and "not logged in" not in done.output.lower()

    def run(self, session: Session) -> SessionResult:
        env = self.environment(session)
        if self.api_key_env is None and not self.logged_in(env):
            return SessionResult.failed(StopReason.ERROR, NOT_LOGGED_IN).with_next(LOGIN_NEXT)
        events = Events(session.max_tokens, self.billing)
        try:
            completed = process.stream(
                self.command(session),
                cwd=session.cwd,
                on_line=events.add_line,
                timeout_s=session.timeout_s,
                env=env,
                input_text=_message(session),
            )
        except (process.CommandNotFoundError, OSError) as exc:
            return SessionResult.failed(StopReason.ERROR, str(exc))
        if events.quota is not None:
            return events.result(StopReason.QUOTA, events.quota, next_step=events.reset_step())
        if completed.stopped:
            return events.result(StopReason.BUDGET, events.stop_text, cap=events.cap)
        if completed.timed_out:
            return events.result(StopReason.TIMEOUT, timeout_summary(session.timeout_s))
        if events.error is not None:
            return events.result(StopReason.ERROR, events.error)
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout).strip()[-OUTPUT_TAIL_CHARS:]
            return events.result(StopReason.ERROR, f"codex exit {completed.returncode}: {tail}")
        if not events.completed:
            return events.result(StopReason.ERROR, "no completed turn in the events")
        return events.result(StopReason.FINISHED, events.text, structured=events.answer())


def _environment(base: Mapping[str, str], api_key_env: str | None) -> dict[str, str]:
    key = base.get(api_key_env) if api_key_env else None
    kept = api_key_env.upper() if api_key_env else None

    def own(name: str) -> bool:
        # Case-insensitive, as on Windows; a name ending in `_` is a prefix (ADR 0024).
        upper = name.upper()
        return kept is not None and (
            upper.startswith(kept) if kept.endswith("_") else upper == kept
        )

    env = {
        name: value
        for name, value in base.items()
        if not name.upper().startswith(_KEY_PREFIXES) and not own(name)
    }
    if key:
        env["CODEX_API_KEY"] = key
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
    """What `codex exec --json` says: the last agent message, usage of each completed turn."""

    def __init__(self, max_tokens: int | None, billing: str) -> None:
        self.max_tokens = max_tokens
        self.billing = billing
        self.input = self.cache_read = self.cache_write = self.output = 0
        self.turns = 0
        self.completed = False
        self.text = ""
        self.error: str | None = None
        self.quota: str | None = None
        self.reset: str | None = None
        self.cap: str | None = None
        self.stop_text = ""

    @property
    def total(self) -> int:
        return self.input + self.cache_read + self.cache_write + self.output

    def add_line(self, line: str) -> bool:
        """Count one event line; True when the token cap is reached and the session must stop."""
        event = json_object(line)
        if event is None:
            return False
        kind = event.get("type")
        if kind in ("item.completed", "item.updated"):
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                self.text = text if isinstance(text, str) else self.text
        elif kind in ("turn.failed", "error"):
            self._failure(event)
        elif kind == "turn.completed":
            return self._turn_completed(event.get("usage"))
        return False

    def _failure(self, event: dict[str, Any]) -> None:
        error = event.get("error")
        message = error.get("message") if isinstance(error, dict) else event.get("message")
        code = error.get("code") if isinstance(error, dict) else None
        text = message if isinstance(message, str) else "codex reported an error"
        self.completed = False
        if _USAGE_LIMIT.search(f"{code} {text}"):
            self.quota = f"Codex usage limit reached: {text}"
            found = _RESET.search(text)
            self.reset = found.group(1).strip() if found else None
        else:
            kind = error.get("type") if isinstance(error, dict) else None
            self.error = f"{kind}: {text}" if kind else text

    def _turn_completed(self, usage: Any) -> bool:
        usage = usage if isinstance(usage, dict) else {}
        cached = as_int(usage.get("cached_input_tokens")) or 0
        self.turns += 1
        self.completed = True
        self.error = None  # a notice before a completed turn was not fatal
        # Codex counts cached tokens inside `input_tokens`; Ariane records them apart.
        self.input += max((as_int(usage.get("input_tokens")) or 0) - cached, 0)
        self.cache_read += cached
        self.cache_write += as_int(usage.get("cache_write_input_tokens")) or 0
        self.output += as_int(usage.get("output_tokens")) or 0
        if self.max_tokens is not None and self.total >= self.max_tokens:
            self.cap = token_cap(self.max_tokens)
            self.stop_text = f"stopped by Ariane at {self.total} tokens"
        return self.cap is not None

    def reset_step(self) -> str:
        after = f" after {self.reset}" if self.reset else " later"
        return f"restart the ticket{after}"

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
        next_step: str | None = None,
    ) -> SessionResult:
        seen = self.turns > 0
        return SessionResult(
            stop_reason=reason,
            cost_usd=0.0 if self.billing == PLAN else None,
            input_tokens=self.input if seen else None,
            output_tokens=self.output if seen else None,
            cache_read_tokens=self.cache_read if seen else None,
            cache_write_tokens=self.cache_write if seen else None,
            summary=summary,
            cap=cap,
            structured_output=structured,
            billing=self.billing,
            next_step=next_step,
        )
