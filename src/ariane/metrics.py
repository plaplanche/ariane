"""The measurements of one ticket, `work/<n>/metrics.json` (C19, ADR 0030).

Ariane rewrites the file after each step, so a crash leaves `outcome` at `running`.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from ariane import ticket
from ariane.attempts import Attempts
from ariane.runtime import AgentRuntime, Session, SessionResult

METRICS = "metrics.json"
NOT_REVIEWED = "not reviewed"


class Metrics:
    """What a ticket cost and how it went; `write` receives the whole file after each change."""

    def __init__(self, number: int, mode: str, write: Callable[[str], None]) -> None:
        self._write = write
        self.number = number
        self.mode = mode
        self.started = ticket.now().replace(" ", "T")
        self.steps: list[dict[str, str]] = []
        self.sessions: list[dict[str, Any]] = []
        self.rounds = 0
        self.attempts = Attempts()
        self.guard_violations = 0
        self.first_pass_verdict = NOT_REVIEWED
        self.outcome = "running"

    def step(self, name: str) -> None:
        self.steps.append({"name": name, "at": ticket.now().replace(" ", "T")})
        self._write(self.render())

    def run_session(
        self, runtime: AgentRuntime, session: Session, round_: int = 0
    ) -> SessionResult:
        """Run `session` and record its usage and duration."""
        began = time.monotonic()
        result = runtime.run(session)
        self.sessions.append(
            {
                "role": session.role,
                "round": round_,
                "runtime": runtime.name,
                "model": session.model,
                "stop_reason": result.stop_reason.value,
                "cost_usd": result.cost_usd,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "cache_read_tokens": result.cache_read_tokens,
                "cache_write_tokens": result.cache_write_tokens,
                "duration_s": round(time.monotonic() - began, 3),
            }
        )
        self.attempts += result.attempts
        self.step(f"{session.role} session {len(self.sessions)} stopped")
        return result

    def reviewed(self, go: bool) -> None:
        """The first review's verdict is the first-pass verdict."""
        if self.first_pass_verdict == NOT_REVIEWED:
            self.first_pass_verdict = "go" if go else "no-go"

    def fix_round(self, round_: int) -> None:
        self.rounds = round_
        self.step(f"fix round {round_} began")

    def guard_violation(self) -> None:
        """The post-session check found a change it forbids (C11)."""
        self.guard_violations += 1

    def finish(self, outcome: str) -> None:
        self.outcome = outcome
        self.step(f"outcome: {outcome}")

    def render(self) -> str:
        data = {
            "attempts": {
                "push": self.attempts.push,
                "pull_request": self.attempts.pull_request,
                "guard_violations": self.guard_violations,
            },
            "ticket": self.number,
            "mode": self.mode,
            "started": self.started,
            "steps": self.steps,
            "sessions": self.sessions,
            "rounds": self.rounds,
            "first_pass_verdict": self.first_pass_verdict,
            "outcome": self.outcome,
        }
        return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
