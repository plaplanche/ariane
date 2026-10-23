"""`ariane start <n> --resume`: a ticket stopped by its implementer's budget, turn or time limit,
or by an agent runtime's quota, continues from the work its previous run saved, the limit that
stopped it raised once (C5, C23, ADR 0062)."""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ariane import checks, git, restart, ticket
from ariane.config import AgentConfig, Config
from ariane.metrics import METRICS, Metrics
from ariane.runtime import StopReason
from ariane.stop import BUDGET, RUNTIME, Stop

if TYPE_CHECKING:
    from ariane.flow import _TicketRun

LIMITS = (StopReason.BUDGET.value, StopReason.TURNS.value, StopReason.TIMEOUT.value)
QUOTA = StopReason.QUOTA.value
ENTRIES = 4  # the previous run's last journal entries given to the resumed session
ENTRY_CHARS = 2000
_ENTRY = re.compile(r"^## \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}Z ", re.MULTILINE)
_STARTED = re.compile(r"session(?: \d+)? started$")


def command(number: int) -> str:
    return f"`ariane start {number} --resume`"


def with_resume(action: str, number: int) -> str:
    """`action`, then the two ways on after a limit or quota stop: continue, or start over."""
    again = restart.command(number)
    action = restart.with_restart(action, number).removesuffix(f"; to start over, run {again}")
    return f"{action}; to continue from its saved work, run {command(number)} (or {again})"


@dataclass(frozen=True)
class Stopped:
    """How a run of the ticket stopped, from its `metrics.json`: its last agent session's stop
    reason and role, the run's stop category and outcome."""

    reason: str
    role: str
    category: str
    outcome: str
    rounds: int = 0  # the fix rounds the run had begun
    resumed: bool = False  # the run was itself resumed
    reset_at: str = ""  # when the runtime said its quota resets, UTC; "" when it did not

    @property
    def limit(self) -> bool:
        return self.reason in LIMITS

    def resumable(self) -> bool:
        """An implementer's limit (its stop category `budget`) in a run that was not resumed
        already, or any session's quota (`runtime`); a stop after the session (the guard, the
        checks) has another category and is not."""
        if self.outcome in ("running", "delivered"):
            return False
        if self.reason == QUOTA:
            return self.category == RUNTIME
        return (
            self.limit
            and self.role == "implementer"
            and self.category == BUDGET
            and not (self.resumed)
        )


def stopped(data: Mapping[str, Any]) -> Stopped | None:
    """The stop of a `metrics.json`'s data; None without a readable session."""
    try:
        last = data["sessions"][-1]
        before = data.get("restarted_from") or {}
        return Stopped(
            str(last["stop_reason"]),
            str(last["role"]),
            str(data.get("category") or ""),
            str(data.get("outcome") or ""),
            int(data.get("rounds") or 0),
            before.get("resumed") is True,
            str(last.get("reset_at") or ""),
        )
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        return None


def read(text: str) -> Stopped | None:
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return stopped(data) if isinstance(data, dict) else None


def offered(metrics: Metrics, category: str) -> bool:
    """Whether the stop line of a run stopping with `category` names `--resume`."""
    data = {"sessions": metrics.sessions, "category": category, "outcome": "stopped"}
    found = stopped(data | {"restarted_from": metrics.restarted_from})
    return found is not None and found.resumable()


def refusal(found: Stopped | None, number: int, now: datetime) -> Stop | None:
    """Why `--resume` refuses the previous run's stop, or None (ADR 0062)."""
    again = f"run {restart.command(number)}"
    if found is None:
        return Stop(f"the previous run of ticket #{number} recorded no agent session", again)
    if found.limit and found.resumed:
        return Stop(
            f"the previous run of ticket #{number} was resumed already and stopped on a limit"
            f" again ({found.reason})",
            f"{again} to start over, or finish it by hand on branch ariane/{number} and run"
            f" `ariane verify ariane/{number}`",
        )
    if not found.resumable():
        return Stop(
            f"the previous run of ticket #{number} did not stop on its implementer's budget,"
            f" turn or time limit or on a quota (last session: {found.role}, {found.reason};"
            f" stop category {found.category or 'none'})",
            again,
        )
    if found.reset_at and now < _moment(found.reset_at):
        return Stop(
            f"the quota of the {found.role}'s runtime resets at {found.reset_at}",
            f"run {command(number)} after {found.reset_at}",
        )
    return None


@dataclass(frozen=True)
class Resumed:
    """What a resumed run continues: the kept head, the diff's base, the previous session."""

    stopped: Stopped
    kept: str  # the kept branch
    head: str  # its head: the new branch starts there
    base: str  # where the previous run's branch left the base: the diffs start there
    changed: tuple[str, ...]  # the files the previous run changed, without `work/`
    entries: str  # the previous run's last journal entries
    agent: AgentConfig | None  # the resumed session's settings; None: the review only
    raised: str  # which limit was raised, from what to what

    def data(self) -> str:
        """What the resumed session is told of the interrupted attempt, as data."""
        files = "\n".join(f"- {p}" for p in self.changed) or "- none"
        round_ = f", fix round {self.stopped.rounds}" if self.stopped.rounds else ""
        return (
            f"Previous session: {self.stopped.role}{round_}, stopped: {self.stopped.reason}.\n\n"
            f"Files it changed (from the base, without work/):\n{files}\n\n"
            f"Last entries of its journal:\n\n{self.entries or '(none)'}"
        )

    def journal(self) -> str:
        session = (
            "No implementer session: the previous run's work is committed; Ariane replays the"
            " checks and reviews it."
            if self.agent is None
            else "The implementer session continues the interrupted attempt."
        )
        return (
            f"Resumed from `{self.kept}` at `{self.head}`, after a {self.stopped.reason} stop of"
            f" the {self.stopped.role} session. {session} {self.raised}\n\n"
            f"What the session is told (data from the previous run):\n\n"
            f"{ticket.fenced(self.data())}"
        )


def raised(agent: AgentConfig, reason: str) -> tuple[AgentConfig, str]:
    """`agent` with the limit that stopped its session raised by `resume_factor`, capped by its
    `*_cap` setting, and the journal's sentence for it."""
    factor = agent.resume_factor
    if reason == StopReason.BUDGET.value:
        usd = min(agent.max_budget_usd * factor, agent.max_budget_usd_cap or float("inf"))
        tokens = None if agent.max_tokens is None else int(agent.max_tokens * factor)
        text = f"Raised `max_budget_usd` from {agent.max_budget_usd:g} to {usd:g} USD"
        if tokens is not None:
            text += f" and `max_tokens` from {agent.max_tokens} to {tokens}"
        return dataclasses.replace(agent, max_budget_usd=usd, max_tokens=tokens), text + "."
    if reason == StopReason.TIMEOUT.value:
        cap = agent.timeout_minutes_cap or float("inf")
        minutes = min(agent.timeout_minutes * factor, cap)
        text = f"Raised `timeout_minutes` from {agent.timeout_minutes:g} to {minutes:g} min."
        return dataclasses.replace(agent, timeout_minutes=minutes), text
    if reason == StopReason.TURNS.value:
        return agent, "No limit raised: Ariane sets no turn limit of its own."
    return agent, "No limit raised: the session stopped on its runtime's quota."


def last_entries(journal: str) -> str:
    """The last `ENTRIES` entries of a journal, a session's prompt left out, each cut short."""
    starts = [m.start() for m in _ENTRY.finditer(journal)]
    entries = [
        journal[a:b].strip() for a, b in zip(starts, [*starts[1:], len(journal)], strict=True)
    ]
    shown = [e for e in entries if not _STARTED.search(e.partition("\n")[0])][-ENTRIES:]
    return "\n\n".join(e if len(e) <= ENTRY_CHARS else e[:ENTRY_CHARS] + "\n[cut]" for e in shown)


def prepare(
    repo_root: Path, config: Config, branch: str, worktree: Path, kept: str, resuming: bool
) -> tuple[str, dict[str, str], str, restart.Restarted | None, Resumed | None]:
    """`restart.prepare`; when `resuming`, the previous run's stop is read from its branch and
    refused (before anything is cleared) unless `--resume` applies, and the `Resumed` record is
    made from the kept branch."""
    if not resuming:
        return (*restart.prepare(repo_root, config.base_branch, branch, worktree, kept), None)
    number = int(worktree.name)
    if not git.local_branch_exists(repo_root, branch):
        raise Stop(
            f"ticket #{number} has no branch {branch} to resume", f"run `ariane start {number}`"
        )
    records = git.out(["rev-parse", f"refs/heads/{branch}"], repo_root)  # Ariane's commits
    folder = ticket.relative_folder(number)
    found = read(_show(repo_root, records, f"{folder}/{METRICS}"))
    if (refused := refusal(found, number, datetime.now(UTC))) is not None:
        raise refused
    assert found is not None
    journal = _show(repo_root, records, f"{folder}/{ticket.JOURNAL}")
    url, refs, instructions, restarted = restart.prepare(
        repo_root, config.base_branch, branch, worktree, kept
    )
    if restarted is None or not restarted.kept_head:
        raise Stop(
            f"ticket #{number} has no branch {branch} to resume", f"run `ariane start {number}`"
        )
    restarted = dataclasses.replace(restarted, resumed=True)
    head = restarted.kept_head
    base = git.merge_base(repo_root, f"{restart.REMOTE}/{config.base_branch}", head)
    changed = checks.changed_files(git.changes(repo_root, base, head, ticket.WORK_DIR).name_status)
    if found.reason == QUOTA and found.role == "reviewer":
        agent, text = None, "No limit raised: the reviewer stopped on its runtime's quota."
    else:
        agent, text = raised(config.implementer, found.reason)
    entries = last_entries(journal)
    resumed = Resumed(found, kept, head, base, tuple(changed), entries, agent, text)
    return url, refs, instructions, restarted, resumed


def enter(run: _TicketRun, resumed: Resumed) -> None:
    """Move the new branch to the kept head, and bring `work/` back to the base's (the previous
    run's records go, and anything an agent left there) in a commit of its own: the new run's
    records start empty, as for `--restart`. The tree's ADRs were read at the base first."""
    tree = run.worktree
    git.git(["reset", "--hard", "--quiet", resumed.head], tree)
    git.git(["restore", f"--source={resumed.base}", "--staged", "--worktree", "--", "work"], tree)
    message = f"#{run.number}: resume from {resumed.kept}"
    git.commit(tree, [ticket.WORK_DIR], message, env=run.untrusted_env)
    run.resumed = run.resume_next = resumed
    run.diff_base = resumed.base
    run.metrics.rounds = resumed.stopped.rounds


def _show(repo_root: Path, commit: str, path: str) -> str:
    done = git.git(["show", f"{commit}:{path}"], repo_root, check=False)
    return done.stdout if done.ok else ""


def _moment(text: str) -> datetime:
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
