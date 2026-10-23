"""The reviewer sessions of one review round (C10): the answer is asked again once if invalid."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from ariane import checks, git, review, review_history, ticket
from ariane.config import AgentConfig, CheckConfig, DoneItem
from ariane.metrics import Metrics
from ariane.risk import Tier
from ariane.runtime import (
    AgentRuntime,
    SessionResult,
    StopReason,
    category,
    describe,
    for_role,
    is_token_cap,
    login_for,
    session_for,
)
from ariane.stop import BUDGET, RUNTIME
from ariane.tracker import Issue


class ReviewFailed(Exception):
    """No valid answer: the ticket goes to a human."""

    def __init__(
        self, reason: str, next_action: str, detail: str = "", category: str = RUNTIME
    ) -> None:
        super().__init__(reason)
        self.category = category  # the stop category (ADR 0058)
        self.reason = reason
        self.next_action = next_action
        self.detail = detail


def instruction_dirs(tree: Path) -> list[Path]:
    """The folders whose instruction files, with their ancestors', a reviewer on `tree` can load:
    the system temporary folder (where its empty working directory is made) and the tree's
    parent (ADR 0031)."""
    return [Path(tempfile.gettempdir()), tree.parent]


def agent_logins(
    runtime: AgentRuntime, implementer: AgentConfig, reviewer: AgentConfig
) -> dict[str, tuple[str, ...]]:
    """The login variables of each kind of agent session: the implementer's, the reviewer's and,
    under `reviewer.small`, the small reviewer's, whose model may need another provider's key
    (ADR 0046). Each session receives only its own model's login (ADR 0024)."""
    small = reviewer.small.model if reviewer.small and reviewer.small.model else reviewer.model
    return {
        "implementer": login_for(runtime, "implementer", implementer.model),
        "reviewer": login_for(runtime, "reviewer", reviewer.model),
        "reviewer.small": login_for(runtime, "reviewer", small),
    }


def read_answer(
    result: SessionResult, earlier: Sequence[str] = ()
) -> tuple[review.Review | None, str]:
    """The validated answer of a reviewer session, or the reason it is not one; `earlier` are
    the identifiers of the earlier blocking findings it must answer (ADR 0059)."""
    data = result.structured_output
    if data is None:
        try:
            data = json.loads(result.summary)
        except json.JSONDecodeError:
            return None, "the answer is not a JSON object"
    errors = review.validate(data, earlier)
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
    changed_lines: int | None = None  # added plus deleted lines of the reviewed diff (ADR 0046)
    small_env: Mapping[str, str] | None = None  # the small reviewer's environment (its login)
    tier: Tier | None = None  # the round's risk tier, stated in the prompt (ADR 0056)
    residuals: Sequence[review.Residual] = ()  # accepted at the base commit (ADR 0057)
    sensitive: Sequence[str] = ()  # the changed paths matching `[review] sensitive_paths`
    earlier: Sequence[review_history.Earlier] = ()  # the earlier rounds' blocking findings

    @property
    def small(self) -> bool:
        """The change is at most `[agents.reviewer.small]`'s `max_lines` (ADR 0046), and not a
        `high` tier measured by `[checks_policy]`, which keeps the full review (ADR 0056)."""
        small = self.agent.small
        lines = self.changed_lines
        full = self.tier is not None and self.tier.measured and self.tier.high
        return small is not None and lines is not None and lines <= small.max_lines and not full

    @property
    def reviewer(self) -> AgentConfig:
        """The reviewer's settings for this change: the small ones replace the reviewer's own
        for a small change; runtime and tools stay the reviewer's (ADR 0046)."""
        small = self.agent.small
        if small is None or not self.small:
            return self.agent
        agent = self.agent
        timeout = small.timeout_minutes or agent.timeout_minutes
        idle = agent.idle_minutes
        return replace(
            agent,
            model=small.model or agent.model,
            max_budget_usd=small.max_budget_usd or agent.max_budget_usd,
            max_tokens=small.max_tokens or agent.max_tokens,
            timeout_minutes=timeout,
            # An idle limit at or above the time limit never fires first: none.
            idle_minutes=idle if idle is not None and idle < timeout else None,
            small=None,
        )

    def size_text(self) -> str:
        """The size of the change, for the journal."""
        small = self.agent.small
        if self.changed_lines is None:
            return "changed lines not counted"
        if small is not None and not self.small and self.changed_lines <= small.max_lines:
            return f"{self.changed_lines} changed lines, risk tier high: full review"
        if small is None or not self.small:
            return f"{self.changed_lines} changed lines"
        return (
            f"small change ({self.changed_lines} changed lines, at most {small.max_lines}):"
            " small reviewer settings"
        )

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
        agent = self.reviewer
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
                    small_lines=self.changed_lines if self.small else None,
                    tier=self.tier,
                    residuals=self.residuals,
                    sensitive=self.sensitive,
                    earlier=self.earlier,
                ),
                env=self.small_env if self.small and self.small_env is not None else self.env,
                json_schema=review.SCHEMA,
                add_dirs=(replay,) if claude else (),
            )
            self.folder.log(
                "ticket.review.started",
                f"Reviewer session {attempt} started",
                f"Runtime {describe(runtime)}, model {agent.model}, tools"
                f" {', '.join(agent.tools)}, {cap_text(agent)},"
                f" time limit {agent.timeout_minutes:g} min, in `{replay}` at `{checked}`;"
                f" {self.size_text()}.",
            )
            result = (
                self.metrics.run_session(runtime, session, self.round, self.changed_lines)
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
                name = "max_tokens" if is_token_cap(result.cap) else "max_budget_usd"
                key = f"agents.reviewer.{self._section(name)}{name}"
                kind = "token cap" if key.endswith("max_tokens") else "cost cap"
                raise ReviewFailed(
                    f"the reviewer session stopped at {result.cap}",
                    f"raise `{key}` ({kind}) in ariane.toml; the work is kept on branch"
                    f" ariane/{number}",
                    ticket.fenced(result.summary),
                    BUDGET,
                )
            if result.stop_reason is StopReason.QUOTA:
                raise ReviewFailed(
                    "reviewer quota reached",
                    result.next_step or "wait for the quota to reset",
                    ticket.fenced(result.summary),
                )
            if result.next_step:
                raise ReviewFailed(result.summary, result.next_step)
            if result.stop_reason is not StopReason.FINISHED:
                raise ReviewFailed(
                    f"the reviewer session stopped: {result.stop_text()}",
                    f"read work/{number}/journal.md; Ariane pushed nothing",
                    ticket.fenced(result.summary),
                    category(result.stop_reason),
                )
            answer, error = read_answer(result, [e.id for e in self.earlier])
            if answer is not None:
                return answer
            self.folder.log("ticket.review.invalid", f"Reviewer answer {attempt} invalid", error)
        raise ReviewFailed(
            f"the reviewer's answer was invalid twice ({error.splitlines()[0]})",
            f"read work/{self.issue.number}/journal.md; Ariane pushed nothing",
            error,
        )

    def _section(self, key: str) -> str:
        """`small.` when this round's value of `key` comes from `[agents.reviewer.small]`."""
        small = self.agent.small
        return "small." if self.small and getattr(small, key) is not None else ""


def cap_text(agent: AgentConfig) -> str:
    """The caps that apply to the reviewer's session, for the journal."""
    if agent.runtime == "opencode":
        return (
            "runtime cost cap none; Ariane stops at"
            f" {agent.max_budget_usd:g} USD of reported cost or {agent.max_tokens} tokens"
        )
    if agent.runtime == "pi":
        return (
            "runtime cost cap none (billed per token); Ariane stops at"
            f" {agent.max_budget_usd:g} USD of reported cost or {agent.max_tokens} tokens"
        )
    if agent.runtime == "codex":
        cap = f", Ariane stops at {agent.max_tokens} tokens" if agent.max_tokens else ""
        return f"runtime cost cap none (billed by the plan or the API key){cap}"
    return f"runtime cost cap {agent.max_budget_usd:g} USD"
