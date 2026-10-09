"""The delivery of a ticket whose blocking checks passed: push, pull request, statuses."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from ariane import checks, git, process, ticket
from ariane.redact import redact
from ariane.tracker import Issue, Tracker, TrackerError

_STATUS_DESCRIPTION_MAX = 140
# Failures that stop a ticket cleanly, with a journaled reason, instead of a traceback.
FAILURES = (git.GitError, TrackerError, OSError, process.CommandNotFoundError)


class PullRequestRefused(Exception):
    """The branch is pushed but the tracker refused the pull request."""

    def __init__(self, reason: str, next_action: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.next_action = next_action


@dataclass(frozen=True)
class Delivered:
    pull_url: str


@dataclass(frozen=True)
class Delivery:
    """What the delivery needs from a ticket run."""

    issue: Issue
    tracker: Tracker
    folder: ticket.TicketFolder
    worktree: Path
    branch: str
    base_branch: str
    url: str
    commit_record: Callable[[str], None]
    secrets: list[str] = field(default_factory=list)
    token: str = field(default="", repr=False)
    environ: Mapping[str, str] | None = field(default=None, repr=False)
    checked: str = ""

    def deliver(self, results: list[checks.CheckResult]) -> Delivered:
        number = self.issue.number
        self.folder.log("Delivering", f"Pushing {self.branch} and opening the pull request.")
        self.folder.set_status(
            "pushed",
            f"{self.branch} pushed; opening the pull request",
            "see the pull request, or run ariane status <n>".replace("<n>", str(number)),
        )
        self.commit_record(f"#{number}: record the checks and the delivery")
        self._require_replayed()
        pushed = git.head(self.worktree)
        way = git.push(
            self.worktree, self.url, pushed, self.branch, token=self.token, environ=self.environ
        )
        self.folder.log("Pushed", f"Pushed `{self.branch}` {way}.")
        # Nothing is committed from here on: the pushed commit is the one CI runs on.
        try:
            pull = self.tracker.open_pull_request(
                head=self.branch,
                base=self.base_branch,
                title=redact(self.issue.title, self.secrets),
                body=redact(self._pull_request_body(results), self.secrets),
            )
        except TrackerError as exc:
            raise PullRequestRefused(
                f"branch {self.branch} is pushed but the pull request was refused: {exc}",
                f"open the pull request from {self.branch} by hand, or delete that branch"
                " and start again",
            ) from None
        self.folder.log("Delivered", f"Pull request #{pull.number}: {pull.url}")
        self._publish_statuses(results, pushed)
        return Delivered(pull.url)

    def _require_replayed(self) -> None:
        """The head differs from the replayed commit only by this ticket's records."""
        if not self.checked:
            return
        own = ticket.relative_folder(self.issue.number) + "/"
        listing = git.out(["diff", "--name-only", self.checked, "HEAD"], self.worktree)
        outside = [p for p in listing.splitlines() if p and not p.startswith(own)]
        if outside:
            raise PullRequestRefused(
                f"the head to push differs from the replayed commit outside {own}"
                f" ({', '.join(outside)})",
                "inspect the branch; Ariane pushed nothing",
            )

    def _publish_statuses(self, results: list[checks.CheckResult], sha: str) -> None:
        """C9: one commit status per check on the pull request's head commit. A refusal is a
        journaled warning; the journal stays local so that the pushed commit does not move."""
        report = self.tracker.file_url(
            self.branch, f"{ticket.relative_folder(self.issue.number)}/{ticket.CHECKS}"
        )
        warnings = []
        for r in results:
            description = redact(f"{r.detail}, {r.duration_s:.1f} s", self.secrets)
            description = description[:_STATUS_DESCRIPTION_MAX]
            try:
                self.tracker.set_commit_status(
                    sha,
                    f"ariane/{r.name}",
                    "success" if r.passed else "failure",
                    description,
                    report,
                )
            except TrackerError as exc:
                warnings.append(f"- `ariane/{r.name}`: {exc}")
        if warnings:
            self.folder.log("Warning: commit statuses refused", "\n".join(warnings))

    def _pull_request_body(self, results: list[checks.CheckResult]) -> str:
        number = self.issue.number
        report = f"{ticket.relative_folder(number)}/{ticket.CHECKS}"
        return (
            f"Closes #{number}\n\n"
            f"Implemented by an Ariane implementer session; checks replayed by Ariane.\n\n"
            f"{checks.summary_table(results)}\n\n{checks.summary_line(results)}\n\n"
            f"Full report: [{report}]({self.tracker.file_url(self.branch, report)}). "
            f"Journal: `{ticket.relative_folder(number)}/{ticket.JOURNAL}`.\n"
        )
