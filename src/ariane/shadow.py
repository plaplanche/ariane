"""`ariane start --shadow`: the whole flow in a separate local clone, with nothing delivered
(C19, C23, ADR 0036).

The user's repository is only read. The clone has no remote: nothing is pushed, no pull request
is opened, no commit status or comment is posted.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path

from ariane import checks, git, review, ticket
from ariane.config import Config
from ariane.flow import (
    _FAILURES,
    EXIT_OK,
    REMOTE,
    Outcome,
    _describe,
    _interrupted_before_start,
    _TicketRun,
    branch_name,
)
from ariane.metrics import METRICS
from ariane.runtime import AgentRuntime
from ariane.stop import Stop
from ariane.tracker import Issue, Tracker, TrackerError

MAX_MINUTES = 1440
VERDICTS = ("accept", "reject")
BASE_REF_REMOTE = "shadow"  # only names the base branch's ref in the clone; it is not a remote


def clone_path(repo_root: Path, number: int) -> Path:
    return repo_root.parent / f"{repo_root.name}.ariane" / "shadow" / str(number)


def start(
    number: int,
    *,
    repo_root: Path,
    config: Config,
    tracker: Tracker,
    runtime: AgentRuntime,
    environ: Mapping[str, str],
) -> Outcome:
    try:
        issue = tracker.read_issue(number)
    except TrackerError as exc:
        return Outcome(exc.exit_code, f"Did not start #{number}: {exc}. Next: {exc.next_action}.")
    except KeyboardInterrupt:
        return _interrupted_before_start(number)
    clone = clone_path(repo_root, number)
    try:
        _prepare(repo_root, config, branch_name(number), clone)
        run = ShadowRun(issue, config, tracker, runtime, environ, clone)
    except KeyboardInterrupt:
        return _interrupted_before_start(number)
    except (Stop, *_FAILURES) as exc:
        reason, next_action = _describe(exc)
        return Outcome(1, f"Did not start shadow ticket #{number}: {reason}. Next: {next_action}.")
    return run.execute({})


def _prepare(repo_root: Path, config: Config, branch: str, clone: Path) -> None:
    """Clone the user's repository (read only) at its last known remote base branch, cut the
    clone from every remote, and check out the ticket's branch there."""
    if clone.exists():
        raise Stop(f"its shadow clone already exists at {clone}", "remove it to start over")
    base = f"refs/remotes/{REMOTE}/{config.base_branch}"
    found = git.git(
        ["rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"], repo_root, check=False
    )
    if not found.ok:
        raise Stop(
            f"{REMOTE}/{config.base_branch} is not known in the repository",
            f"run `git fetch {REMOTE}` in it, then start again",
        )
    sha = found.stdout.strip()
    clone.parent.mkdir(parents=True, exist_ok=True)
    git.git(
        ["clone", "--local", "--quiet", "--no-checkout", str(repo_root), str(clone)], clone.parent
    )
    git.git(["remote", "remove", REMOTE], clone)
    git.git(["update-ref", f"refs/remotes/{BASE_REF_REMOTE}/{config.base_branch}", sha], clone)
    git.git(["checkout", "--quiet", "-b", branch, sha], clone)


class ShadowRun(_TicketRun):
    """A ticket run whose delivery is a local record and whose remote does not exist."""

    remote = BASE_REF_REMOTE

    def __init__(
        self,
        issue: Issue,
        config: Config,
        tracker: Tracker,
        runtime: AgentRuntime,
        environ: Mapping[str, str],
        clone: Path,
    ) -> None:
        super().__init__(
            issue, config, tracker, runtime, environ, clone, branch_name(issue.number), ""
        )
        self.metrics.mode = "shadow"

    def _remote_changes(self, refs_before: dict[str, str]) -> list[str]:
        return []

    def _deliver(
        self,
        checked: str,
        settled: review.Settled | None,
        reviewed: int,
        results: list[checks.CheckResult],
        unchanged: int = 0,
        guard_push: Callable[[], None] | None = None,
    ) -> Outcome:
        draft = settled is not None and not settled.go
        outcome = "needs a human" if draft else "delivered"
        verdict = settled.verdict if settled is not None else "none"
        self.metrics.finish(outcome)
        self.folder.log(
            "ticket.shadow.done",
            "Shadow ticket done",
            f"Outcome {outcome}, review {verdict}. Nothing was pushed, no pull request opened.",
        )
        self.folder.set_status("shadow done", f"{outcome}, review {verdict}", "ariane judge")
        self._commit_record(f"#{self.number}: record the shadow outcome")
        return Outcome(
            EXIT_OK,
            f"Shadow ticket #{self.number} done ({outcome}, review {verdict}). Next: read"
            f" {self.worktree}/work/{self.number}/, then run ariane judge {self.number}"
            " accept|reject --minutes N.",
        )


def judge(
    repo_root: Path, number: int, verdict: str, minutes: int, note: str | None = None
) -> Outcome:
    """Record the human's verdict and time in the shadow ticket's `metrics.json` (ADR 0037).

    An earlier judgement moves to `judgements_before`, oldest first."""
    path = clone_path(repo_root, number) / "work" / str(number) / METRICS
    if not path.is_file():
        return Outcome(
            1,
            f"Did not judge #{number}: no shadow clone for it. Next: run ariane start --shadow"
            f" {number}.",
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("outcome") == "running":
        return Outcome(
            1,
            f"Did not judge #{number}: its shadow ticket is still running. Next: wait for it to"
            " end, then judge it.",
        )
    earlier = data.get("judgement")
    if earlier is not None:
        data["judgements_before"] = [*data.get("judgements_before", []), earlier]
    data["judgement"] = {
        "verdict": verdict,
        "minutes": minutes,
        "note": note,
        "at": ticket.now().replace(" ", "T"),
    }
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return Outcome(
        EXIT_OK,
        f"Judged shadow ticket #{number}: {verdict}, {minutes} minutes. Next: nothing.",
    )
