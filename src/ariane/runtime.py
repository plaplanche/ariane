"""The agent runtime interface (C5): one fresh session per stage, whatever the agent CLI."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from ariane.attempts import Attempts
from ariane.config import AgentConfig
from ariane.stop import BUDGET, RUNTIME

OUTPUT_TAIL_CHARS = 2000
_TOKEN_CAP_PREFIX = "Ariane token cap"


def token_cap(tokens: int | None) -> str:
    return f"{_TOKEN_CAP_PREFIX} ({tokens} tokens)"


def cost_cap(usd: float) -> str:
    return f"runtime cost cap ({usd:g} USD)"


def is_token_cap(cap: str) -> bool:
    return cap.startswith(_TOKEN_CAP_PREFIX)


def timeout_summary(seconds: float) -> str:
    return f"killed after {seconds:g} s (time limit)"


def idle_summary(seconds: float, stdout: str) -> str:
    """The summary of a session killed at its idle limit, naming the last event it sent."""
    return f"no activity for {seconds / 60:g} min (idle limit); last event: {last_event(stdout)}"


def last_event(stdout: str) -> str:
    """The last line's event type, and its tool's name when it was a tool call."""
    line = stdout.rstrip("\n").rpartition("\n")[2]
    if not line.strip():
        return "none"
    event = json_object(line)
    if event is None:
        return "not a JSON event"
    kind = str(event.get("type", "unknown"))
    tool = _tool_name(event)
    return f"{kind} (tool {tool})" if tool else kind


def _tool_name(event: dict[str, Any]) -> str | None:
    """The tool of a Claude Code `tool_use` block, an opencode `tool_use` part or a Codex item."""
    message, part, item = event.get("message"), event.get("part"), event.get("item")
    if isinstance(message, dict) and isinstance(message.get("content"), list):
        names = [
            str(block.get("name"))
            for block in message["content"]
            if isinstance(block, dict) and block.get("type") == "tool_use"
        ]
        return names[-1] if names else None
    if isinstance(part, dict) and part.get("tool"):
        return str(part["tool"])
    if isinstance(item, dict) and item.get("type") not in (None, "agent_message", "reasoning"):
        return str(item.get("tool") or item["type"])
    return None


_SPAN = re.compile(r"(\d+)\s*(second|minute|hour|day|week)s?\b", re.IGNORECASE)
_CLOCK = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([ap]\.?m\.?)?", re.IGNORECASE)


def reset_moment(text: str, now: datetime | None = None) -> str | None:
    """The UTC time, as ISO text, of a runtime's "try again at/in <text>": an ISO time with its
    zone, a span ("2 hours 5 minutes") from `now`, or a clock time ("3:45 PM", the machine's
    local time) at its next occurrence; None when the text is none of these (ADR 0062)."""
    now = now or datetime.now(UTC)
    try:
        moment = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        moment = None
    if moment is not None and moment.tzinfo is not None:
        return _utc(moment)
    if spans := _SPAN.findall(text):
        return _utc(
            now + sum((timedelta(**{f"{u.lower()}s": int(n)}) for n, u in spans), timedelta())
        )
    if (found := _CLOCK.search(text)) is None:
        return None
    hour, minute, second = int(found[1]), int(found[2]), int(found[3] or 0)
    if found[4]:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if found[4][0].lower() == "p" else 0)
    if hour > 23 or minute > 59 or second > 59:
        return None
    local = now.astimezone()
    moment = local.replace(hour=hour, minute=minute, second=second, microsecond=0)
    return _utc(moment if moment > local else moment + timedelta(days=1))


def _utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def json_object(line: str) -> dict[str, Any] | None:
    """The JSON object a line holds, or None for anything else."""
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def as_number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class StopReason(StrEnum):
    FINISHED = "finished"
    BUDGET = "budget"
    TURNS = "turns"
    TIMEOUT = "timeout"
    QUOTA = "quota"  # a subscription's usage limit is reached (ADR 0043)
    ERROR = "error"


def category(reason: StopReason) -> str:
    """The stop category of a session that did not finish: a limit is `budget`, a quota or an
    error is `runtime` (ADR 0058)."""
    limits = (StopReason.BUDGET, StopReason.TURNS, StopReason.TIMEOUT)
    return BUDGET if reason in limits else RUNTIME


@dataclass(frozen=True)
class Session:
    role: str
    model: str
    tools: tuple[str, ...]
    max_budget_usd: float
    max_tokens: int | None  # Ariane's own cap on counted tokens; None for no cap
    timeout_s: float
    cwd: Path
    prompt: str
    env: Mapping[str, str]  # the complete environment of the agent process
    json_schema: Mapping[str, Any] | None = None  # shape of the structured answer, if any
    add_dirs: tuple[Path, ...] = ()  # read-only reviewer: the trees it may read, cwd is empty
    idle_timeout_s: float | None = None  # killed when no event arrives for this long (C5)


@dataclass(frozen=True)
class SessionResult:
    stop_reason: StopReason
    cost_usd: float | None  # as reported by the agent, never estimated
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None  # as reported, apart from input_tokens
    cache_write_tokens: int | None
    summary: str  # the agent's final message, or the error
    permission_denials: tuple[str, ...] = field(default_factory=tuple)
    cap: str | None = None  # which cap stopped a `budget` session
    structured_output: Any = None  # the answer parsed by the runtime, when a schema was given
    # pushes and pull requests the agent attempted (ADR 0036)
    attempts: Attempts = field(default_factory=Attempts)
    billing: str | None = None  # "plan" (covered by a subscription) or "api"; None when unknown
    next_step: str | None = None  # what to do, when the runtime knows (quota, login)
    reset_at: str | None = None  # a quota stop: when the runtime said it resets, UTC (ADR 0062)

    @classmethod
    def failed(cls, reason: StopReason, summary: str, cap: str | None = None) -> SessionResult:
        """A session that reported no usage."""
        return cls(reason, None, None, None, None, None, summary, cap=cap)

    def with_next(self, next_step: str) -> SessionResult:
        return replace(self, next_step=next_step)

    def stop_text(self) -> str:
        """The stop reason for a stop line; a timeout says which limit and what it was doing."""
        if self.stop_reason is StopReason.TIMEOUT:
            return f"{self.stop_reason.value} ({self.summary})"
        return self.stop_reason.value

    def stop_category(self) -> str:
        """The stop category of this session when it did not finish (`category`, ADR 0058)."""
        return category(self.stop_reason)

    def usage_text(self) -> str:
        """The cap line, then the cost and the tokens, as the journal words them."""
        cost, tokens = self.usage()
        cap = f"Cap reached: {self.cap}.\n\n" if self.cap else ""
        quota = f"{self.summary}\n\n" if self.stop_reason is StopReason.QUOTA else ""
        plan = " Billing: covered by the plan." if self.billing == "plan" else ""
        return f"{cap}{quota}Cost {cost} (as reported), tokens {tokens}.{plan}"

    def usage(self) -> tuple[str, str]:
        """The cost and the tokens as the journal words them."""
        cost = "not reported" if self.cost_usd is None else f"{self.cost_usd:.4f} USD"
        tokens = ", ".join(
            f"{'not reported' if n is None else n} {label}"
            for n, label in (
                (self.input_tokens, "in"),
                (self.cache_read_tokens, "cache read"),
                (self.cache_write_tokens, "cache write"),
                (self.output_tokens, "out"),
            )
        )
        return cost, tokens


class AgentRuntime(Protocol):
    name: str
    # Exact names and prefixes (ending in `_`) of the variables the runtime keeps for its login.
    login_variables: tuple[str, ...]

    def run(self, session: Session) -> SessionResult: ...


class RoutedRuntime:
    """One runtime per role (ADR 0029): a session goes to the runtime of its role.

    It has no login of its own: each session's environment is built from its role's runtime.
    """

    login_variables: tuple[str, ...] = ()

    def __init__(self, runtimes: Mapping[str, AgentRuntime]) -> None:
        self.runtimes = dict(runtimes)
        self.name = ", ".join(dict.fromkeys(r.name for r in self.runtimes.values()))

    def for_role(self, role: str) -> AgentRuntime:
        return self.runtimes[role]

    def run(self, session: Session) -> SessionResult:
        return self.runtimes[session.role].run(session)


def for_role(runtime: AgentRuntime, role: str) -> AgentRuntime:
    """The runtime that serves `role` (the runtime itself unless it routes by role)."""
    return runtime.for_role(role) if isinstance(runtime, RoutedRuntime) else runtime


def login_for(runtime: AgentRuntime, role: str, model: str) -> tuple[str, ...]:
    """The login variables of `role`'s sessions on `model`: a runtime whose login depends on the
    model (opencode: the model's provider) says so with `login_for`."""
    served = for_role(runtime, role)
    by_model = getattr(served, "login_for", None)
    return tuple(by_model(model)) if callable(by_model) else served.login_variables


def describe(runtime: AgentRuntime) -> str:
    """The runtime as the journal words it: its name, plus its own description if it has one."""
    describer = getattr(runtime, "describe", None)
    return str(describer()) if callable(describer) else runtime.name


def session_for(
    agent: AgentConfig,
    role: str,
    *,
    cwd: Path,
    prompt: str,
    env: Mapping[str, str],
    **extra: Any,
) -> Session:
    """The session of `role` as `agent` configures it."""
    return Session(
        role=role,
        model=agent.model,
        tools=agent.tools,
        max_budget_usd=agent.max_budget_usd,
        max_tokens=agent.max_tokens,
        timeout_s=agent.timeout_minutes * 60,
        idle_timeout_s=None if agent.idle_minutes is None else agent.idle_minutes * 60,
        cwd=cwd,
        prompt=prompt,
        env=env,
        **extra,
    )
