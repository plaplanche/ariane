"""The reviewer sessions of one review round (C10): the answer is asked again once if invalid."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ariane import checks, git, review, ticket
from ariane.config import AgentConfig, CheckConfig, DoneItem
from ariane.metrics import Metrics
from ariane.runtime import (
    AgentRuntime,
    SessionResult,
    StopReason,
    describe,
    for_role,
    is_token_cap,
    session_for,
)
from ariane.tracker import Issue


class ReviewFailed(Exception):
    """No valid answer: the ticket goes to a human."""

    def __init__(self, reason: str, next_action: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.next_action = next_action
        self.detail = detail


def instruction_dirs(tree: Path) -> list[Path]:
    """The folders whose instruction files, with their ancestors', a reviewer on `tree` can load:
    the system temporary folder (where its empty working directory is made) and the tree's
    parent (ADR 0031)."""
    return [Path(tempfile.gettempdir()), tree.parent]


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
    metrics: Metrics | None = None  # where the sessions' usage is recorded (C19)
    round: int = 0  # the review round, for the metrics

    def run(
        self,
        replay: Path,
        checked: str,
        diff: str,
        results: list[checks.CheckResult],
        not_updated: Sequence[str],
        changed: Sequence[str],
        after_session: Callable[[], None],
        name_status: str = "",
    ) -> review.Review:
        """A fresh read-only reviewer session on `replay` (the reviewer tree, without instruction
        files); one retry if its answer is invalid. `after_session` verifies that the session
        changed nothing. Claude Code starts in an empty folder and reads `replay` (ADR 0031)."""
        empty = Path(tempfile.mkdtemp(prefix="ariane-reviewer-"))
        try:
            self._record_instructions(replay)
            return self._run(
                replay,
                empty,
                checked,
                (diff, name_status),
                results,
                not_updated,
                changed,
                after_session,
            )
        finally:
            shutil.rmtree(empty, ignore_errors=True)

    def _record_instructions(self, replay: Path) -> None:
        """Journal the digests of the instruction files the reviewer's runtime can load from
        outside the reviewer tree; the guard compares them with the ticket's start (ADR 0031)."""
        files = git.instruction_snapshot(instruction_dirs(replay), self.agent.runtime, self.env)
        lines = [
            f"- `{key.removeprefix('instructions ')}`: {digest}"
            for key, digest in files.items()
            if digest != "absent"
        ]
        self.folder.log(
            "ticket.review.instructions",
            "Reviewer instruction files",
            f"{len(files)} places checked; present:\n" + ("\n".join(lines) or "- none"),
        )

    def _run(
        self,
        replay: Path,
        empty: Path,
        checked: str,
        diff: tuple[str, str],
        results: list[checks.CheckResult],
        not_updated: Sequence[str],
        changed: Sequence[str],
        after_session: Callable[[], None],
    ) -> review.Review:
        agent = self.agent
        claude = agent.runtime == "claude-code"
        runtime = for_role(self.runtime, "reviewer")
        error = ""
        for attempt in (1, 2):
            session = session_for(
                agent,
                "reviewer",
                cwd=empty if claude else replay,
                prompt=review.prompt(
                    self.issue,
                    diff[0],
                    results,
                    self.all_checks,
                    self.definition_of_done,
                    error=error,
                    not_updated=not_updated,
                    changed=changed,
                    instructions=self.instructions,
                    tree=replay,
                    name_status=diff[1],
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
            result = (
                self.metrics.run_session(runtime, session, self.round)
                if self.metrics
                else runtime.run(session)
            )
            timed_out = result.stop_reason is StopReason.TIMEOUT
            self.folder.log(
                "ticket.review.stopped",
                f"Reviewer session {attempt} stopped: {result.stop_reason.value}",
                (f"{result.summary}\n\n" if timed_out else "") + result.usage_text(),
            )
            after_session()
            number = self.issue.number
            if result.stop_reason is StopReason.BUDGET and result.cap:
                key = (
                    "agents.reviewer.max_tokens"
                    if is_token_cap(result.cap)
                    else "agents.reviewer.max_budget_usd"
                )
                kind = "token cap" if key.endswith("max_tokens") else "cost cap"
                raise ReviewFailed(
                    f"the reviewer session stopped at {result.cap}",
                    f"raise `{key}` ({kind}) in ariane.toml; the work is kept on branch"
                    f" ariane/{number}",
                    ticket.fenced(result.summary),
                )
            if result.stop_reason is StopReason.QUOTA:
                raise ReviewFailed(
                    "reviewer quota reached",
                    result.next_step or "restart the ticket later",
                    ticket.fenced(result.summary),
                )
            if result.next_step:
                raise ReviewFailed(result.summary, result.next_step)
            if result.stop_reason is not StopReason.FINISHED:
                raise ReviewFailed(
                    f"the reviewer session stopped: {result.stop_text()}",
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
    if agent.runtime == "codex":
        cap = f", Ariane stops at {agent.max_tokens} tokens" if agent.max_tokens else ""
        return f"runtime cost cap none (billed by the plan or the API key){cap}"
    return f"runtime cost cap {agent.max_budget_usd:g} USD"
