"""The measurements of one ticket, `work/<n>/metrics.json` (C19, ADR 0030).

Ariane rewrites the file after each step, so a crash leaves `outcome` at `running`.
"""

from __future__ import annotations

import contextlib
import json
import time
from collections.abc import Callable
from pathlib import Path
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
        self.unchanged_fix_rounds = 0
        self.attempts = Attempts()
        self.guard_violations = 0
        self.surviving = 0
        self.blocking_red = 0
        self.first_pass_verdict = NOT_REVIEWED
        self.outcome = "running"
        self.restarted_from: dict[str, str | float] | None = None  # the run this one started over
        self.updates = 0  # the `ariane update` runs that merged the base branch (ADR 0033)

    def resume(self, text: str) -> None:
        """Continue the measurements of the ticket's earlier runs from their `metrics.json`
        (`ariane update`, ADR 0033): its steps and sessions are extended, its counts added to;
        an unreadable file is left out and the measurements start empty."""
        try:
            data = json.loads(text)
            attempts = data.get("attempts", {})
            found = {
                "started": str(data["started"]),
                "steps": list(data.get("steps", [])),
                "sessions": list(data.get("sessions", [])),
                "rounds": int(data.get("rounds", 0)),
                "unchanged_fix_rounds": int(data.get("unchanged_fix_rounds", 0)),
                "attempts": Attempts(
                    int(attempts.get("push", 0)), int(attempts.get("pull_request", 0))
                ),
                "guard_violations": int(attempts.get("guard_violations", 0)),
                "surviving": int(data.get("surviving_processes", 0)),
                "blocking_red": int(data.get("blocking_red_at_delivery", 0)),
                "first_pass_verdict": str(data.get("first_pass_verdict", NOT_REVIEWED)),
                "restarted_from": data.get("restarted_from"),
                "updates": int(data.get("updates", 0)),
            }
        except (ValueError, KeyError, TypeError, AttributeError):
            return
        for name, value in found.items():
            setattr(self, name, value)

    def step(self, name: str) -> None:
        self.steps.append({"name": name, "at": ticket.now().replace(" ", "T")})
        self._write(self.render())

    def run_session(
        self,
        runtime: AgentRuntime,
        session: Session,
        round_: int = 0,
        changed_lines: int | None = None,
    ) -> SessionResult:
        """Run `session` and record its usage and duration; a reviewer session also records the
        changed lines of the diff it reviewed (ADR 0046)."""
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
            | ({"billing": result.billing} if result.billing else {})
            | ({"changed_lines": changed_lines} if changed_lines is not None else {})
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

    def unchanged_fix_round(self) -> None:
        """A fix round that left the head where it was (C10)."""
        self.unchanged_fix_rounds += 1

    def guard_violation(self) -> None:
        """The post-session check found a change it forbids (C11)."""
        self.guard_violations += 1

    def surviving_processes(self, count: int) -> None:
        """Processes that outlived a session or command and were killed (C10)."""
        self.surviving += count

    def delivered_red(self, count: int) -> None:
        """The number of blocking checks that were red when the ticket was delivered (C19)."""
        self.blocking_red = count

    def keep_stopped(self, path: Path) -> None:
        """Write the metrics, outcome `stopped`, to `path` outside the repository, without the
        usual writer (best effort: a failure to record must not hide the stop; ADR 0031)."""
        self.outcome = "stopped"
        with contextlib.suppress(OSError):
            path.parent.mkdir(parents=True, exist_ok=True)
            ticket.write_file(path, self.render())

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
            "blocking_red_at_delivery": self.blocking_red,
            "ticket": self.number,
            "mode": self.mode,
            "started": self.started,
            "steps": self.steps,
            "surviving_processes": self.surviving,
            "sessions": self.sessions,
            "rounds": self.rounds,
            "unchanged_fix_rounds": self.unchanged_fix_rounds,
            "first_pass_verdict": self.first_pass_verdict,
            "outcome": self.outcome,
            "updates": self.updates,
        }
        if self.restarted_from is not None:
            data["restarted_from"] = self.restarted_from
        return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
