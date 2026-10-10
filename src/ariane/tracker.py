"""The tracker interface (C1): the only way Ariane talks to GitHub, GitLab or a test double."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class TrackerError(Exception):
    """The tracker refused or failed a request."""


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    body: str
    url: str


@dataclass(frozen=True)
class PullRequest:
    number: int
    url: str


class Tracker(Protocol):
    def read_issue(self, number: int) -> Issue:
        """Return the issue's title and body (never its comments); refuse pull requests."""
        ...

    def open_pull_request(
        self, *, head: str, base: str, title: str, body: str, draft: bool = False
    ) -> PullRequest:
        """Open a pull request from branch `head` into `base`; a `draft` is not ready to merge."""
        ...

    def file_url(self, branch: str, path: str) -> str:
        """Where a human with access to the repository reads `path` on `branch`."""
        ...

    def set_commit_status(
        self, sha: str, context: str, state: str, description: str, target_url: str
    ) -> None:
        """Publish a status (`state` is "success" or "failure") on commit `sha`."""
        ...


@dataclass
class InMemoryTracker:
    """A tracker held in memory, for tests."""

    issues: dict[int, Issue] = field(default_factory=dict)
    pull_request_numbers: set[int] = field(default_factory=set)
    opened: list[dict[str, Any]] = field(default_factory=list)
    statuses: list[dict[str, str]] = field(default_factory=list)
    refuse_statuses: bool = False

    def add_issue(self, number: int, title: str, body: str) -> Issue:
        issue = Issue(number, title, body, f"memory://issues/{number}")
        self.issues[number] = issue
        return issue

    def read_issue(self, number: int) -> Issue:
        if number in self.pull_request_numbers:
            raise TrackerError(f"#{number} is a pull request, not an issue")
        try:
            return self.issues[number]
        except KeyError:
            raise TrackerError(f"issue #{number} not found") from None

    def open_pull_request(
        self, *, head: str, base: str, title: str, body: str, draft: bool = False
    ) -> PullRequest:
        self.opened.append(
            {"head": head, "base": base, "title": title, "body": body, "draft": draft}
        )
        number = 1000 + len(self.opened)
        return PullRequest(number, f"memory://pulls/{number}")

    def file_url(self, branch: str, path: str) -> str:
        return f"memory://blob/{branch}/{path}"

    def set_commit_status(
        self, sha: str, context: str, state: str, description: str, target_url: str
    ) -> None:
        if self.refuse_statuses:
            raise TrackerError("statuses are refused")
        self.statuses.append(
            {
                "sha": sha,
                "context": context,
                "state": state,
                "description": description,
                "target_url": target_url,
            }
        )
