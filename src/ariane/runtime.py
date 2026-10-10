"""The agent runtime interface (C5): one fresh session per stage, whatever the agent CLI."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol


class StopReason(StrEnum):
    FINISHED = "finished"
    BUDGET = "budget"
    TURNS = "turns"
    TIMEOUT = "timeout"
    ERROR = "error"


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
