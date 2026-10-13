"""The reviewer sessions of one review round (C10): the answer is asked again once if invalid."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ariane import checks, review, ticket
from ariane.config import AgentConfig, CheckConfig, DoneItem
from ariane.runtime import AgentRuntime, Session, SessionResult, StopReason, describe, for_role
from ariane.tracker import Issue


class ReviewFailed(Exception):
    """No valid answer: the ticket goes to a human."""

    def __init__(self, reason: str, next_action: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.next_action = next_action
        self.detail = detail


def read_answer(result: SessionResult) -> tuple[review.Review | None, str]:
    """The validated answer of a reviewer session, or the reason it is not one."""
    data = result.structured_output
    if data is None:
        try:
            data = json.loads(result.summary)
        except json.JSONDecodeError:
            return None, "the answer is not a JSON object"
    errors = review.validate(data)
    if errors:
        return None, "\n".join(errors)
    return review.parse(data), ""


@dataclass(frozen=True)
class ReviewSession:
    """What the reviewer sessions of a ticket have in common."""

    runtime: AgentRuntime
    agent: AgentConfig
    folder: ticket.TicketFolder
    issue: Issue
    env: Mapping[str, str]
    all_checks: Sequence[CheckConfig]
    definition_of_done: Sequence[DoneItem]
    instructions: str = ""  # the base branch's CLAUDE.md, shown to the reviewer as data

    def run(
        self,
        replay: Path,
        checked: str,
        diff: str,
        results: list[checks.CheckResult],
        not_updated: Sequence[str],
        after_session: Callable[[], None],
    ) -> review.Review:
        """A fresh read-only reviewer session on `replay` (the reviewer tree, without instruction
        files); one retry if its answer is invalid. `after_session` verifies that the session
        changed nothing. Claude Code starts in an empty folder and reads `replay` (ADR 0031)."""
        empty = Path(tempfile.mkdtemp(prefix="ariane-reviewer-"))
        try:
            return self._run(replay, empty, checked, diff, results, not_updated, after_session)
        finally:
            shutil.rmtree(empty, ignore_errors=True)

    def _run(
        self,
        replay: Path,
        empty: Path,
        checked: str,
        diff: str,
        results: list[checks.CheckResult],
        not_updated: Sequence[str],
        after_session: Callable[[], None],
    ) -> review.Review:
        agent = self.agent
        claude = agent.runtime != "opencode"
        runtime = for_role(self.runtime, "reviewer")
        error = ""
        for attempt in (1, 2):
            session = Session(
                role="reviewer",
                model=agent.model,
                tools=agent.tools,
                max_budget_usd=agent.max_budget_usd,
                max_tokens=agent.max_tokens,
                timeout_s=agent.timeout_minutes * 60,
                cwd=empty if claude else replay,
                prompt=review.prompt(
                    self.issue,
                    diff,
                    results,
                    self.all_checks,
                    self.definition_of_done,
                    error=error,
                    not_updated=not_updated,
                    instructions=self.instructions,
                    tree=replay,
                ),
                env=self.env,
                json_schema=review.SCHEMA,
                add_dirs=(replay,) if claude else (),
            )
            self.folder.log(
                "ticket.review.started",
                f"Reviewer session {attempt} started",
                f"Runtime {describe(runtime)}, model {agent.model}, tools"
                f" {', '.join(agent.tools)}, {cap_text(agent)},"
                f" time limit {agent.timeout_minutes:g} min, in `{replay}` at `{checked}`.",
            )
            result = runtime.run(session)
            cost, tokens = result.usage()
            self.folder.log(
                "ticket.review.stopped",
                f"Reviewer session {attempt} stopped: {result.stop_reason.value}",
                f"Cost {cost} (as reported), tokens {tokens}.",
            )
            after_session()
            number = self.issue.number
            if result.stop_reason is not StopReason.FINISHED:
                raise ReviewFailed(
                    f"the reviewer session stopped: {result.stop_reason.value}",
                    f"read work/{number}/journal.md; Ariane pushed nothing",
                    ticket.fenced(result.summary),
                )
            answer, error = read_answer(result)
            if answer is not None:
                return answer
            self.folder.log("ticket.review.invalid", f"Reviewer answer {attempt} invalid", error)
        raise ReviewFailed(
            f"the reviewer's answer was invalid twice ({error.splitlines()[0]})",
            f"read work/{self.issue.number}/journal.md; Ariane pushed nothing",
            error,
        )


def cap_text(agent: AgentConfig) -> str:
    """The caps that apply to the reviewer's session, for the journal."""
    if agent.runtime == "opencode":
        return (
            "runtime cost cap none; Ariane stops at"
            f" {agent.max_budget_usd:g} USD of reported cost or {agent.max_tokens} tokens"
        )
    return f"runtime cost cap {agent.max_budget_usd:g} USD"
