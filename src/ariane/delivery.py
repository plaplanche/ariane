"""The delivery of a ticket whose blocking checks passed: push, pull request, statuses."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
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
    note: str  # appended to the outcome line, empty when everything was pushed


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

    def deliver(self, results: list[checks.CheckResult]) -> Delivered:
        number = self.issue.number
        self.folder.set_status("delivering", "checks green, pushing the branch", "wait")
        self.commit_record(f"#{number}: record the checks")
        first_pushed = git.head(self.worktree)
        git.push(self.worktree, self.url, first_pushed, self.branch)
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
        self.folder.set_status(
            "delivered", f"pull request {pull.url}", "review and merge the pull request"
        )
        self.commit_record(f"#{number}: record the delivery")
        note = ""
        pushed = git.head(self.worktree)
        try:
            git.push(self.worktree, self.url, pushed, self.branch)
        except git.GitError:
            note = " (the delivery record stays local: its push failed)"
            pushed = first_pushed
        self._publish_statuses(results, pushed)
        return Delivered(pull.url, note)

    def _publish_statuses(self, results: list[checks.CheckResult], sha: str) -> None:
        """C9: one commit status per check on the pull request's head commit. A refusal is a
        journaled warning; the journal stays local so that the head commit does not move."""
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
            with contextlib.suppress(*FAILURES):
                self.commit_record(f"#{self.issue.number}: record the refused statuses")

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
