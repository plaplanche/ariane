"""GitHub tracker over the REST API, with the standard library only (ADR 0007)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from ariane import logs
from ariane.tracker import Issue, IssueRefused, PullRequest, PullRequestState, TrackerError

_TIMEOUT_S = 30
_PAGE = 100
_WRITERS = frozenset({"write", "maintain", "admin"})
# Adding a label stamps `updated_at` in the same second (seconds only): one second of slack.
_LABEL_SLACK = timedelta(seconds=1)
# GitHub lists a label event a few seconds late: waits before the 4 more reads (ADR 0032).
_EVENT_RETRY_DELAYS = (1, 2, 4, 8)


class _EventsLag(IssueRefused):
    """A refusal the events may only show because they lag behind the issue."""

    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects: urllib would forward the Authorization header to the new host."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def web_url(api_url: str) -> str:
    """The web address matching an API address (GitHub or GitHub Enterprise Server)."""
    parsed = urllib.parse.urlsplit(api_url.rstrip("/"))
    if parsed.netloc == "api.github.com":
        return "https://github.com"
    path = parsed.path.removesuffix("/api/v3")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


class GitHubTracker:
    def __init__(
        self,
        *,
        repository: str,
        token: str,
        api_url: str,
        ready_label: str,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._sleep = sleep
        self._ready_label = ready_label
        self._repository = repository
        self._token = token
        self._api_url = api_url.rstrip("/")
        self._web_url = web_url(api_url)
        self._user_owner: str | None = None

    def read_issue(self, number: int) -> Issue:
        data = self._request("GET", f"/repos/{self._repository}/issues/{number}")
        if "pull_request" in data:
            raise TrackerError(f"#{number} is a pull request, not an issue")
        self._check_trusted(number, data, self._ready_label)
        try:
            return Issue(
                number=int(data["number"]),
                title=str(data["title"]),
                body=str(data.get("body") or ""),
                url=str(data["html_url"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise TrackerError(f"GitHub API: unexpected issue #{number}: {exc!r}") from None

    def _check_trusted(self, number: int, data: dict[str, Any], label: str) -> None:
        """Refuse an issue not labelled by a writer, or changed since the label (C21, ADR 0032).

        REST only: GraphQL and, for most users, the permissions endpoint are unreachable from
        some sandboxes. Any change after the label (edit, rename, comment, other label) refuses.
        """
        names = [
            str(item.get("name")) for item in data.get("labels") or [] if isinstance(item, dict)
        ]
        if label not in names:
            raise IssueRefused(
                f"#{number} does not carry the label `{label}`; ask a maintainer to add it"
            )
        for attempt, delay in enumerate((*_EVENT_RETRY_DELAYS, None), start=1):
            try:
                self._judge(number, data, label, self._read_events(number))
                return
            except _EventsLag as lag:
                if delay is None:
                    raise IssueRefused(str(lag)) from None
                logs.emit(
                    "github.label_event_retry",
                    f"#{number}: read {attempt} of the events retried in {delay} s: {lag.reason}",
                )
                self._sleep(delay)

    def _read_events(self, number: int) -> list[dict[str, Any]]:
        return self._pages(f"/repos/{self._repository}/issues/{number}/events")

    def _pages(self, path: str) -> list[dict[str, Any]]:
        """Every object of the listing at `path`, page after page."""
        found: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self._request_any("GET", f"{path}?per_page={_PAGE}&page={page}")
            if not isinstance(batch, list):
                raise TrackerError(f"GitHub API GET {path}: unexpected response")
            found += [e for e in batch if isinstance(e, dict)]
            if len(batch) < _PAGE:
                return found
            page += 1

    def _judge(self, number: int, data: dict[str, Any], label: str, events: list[Any]) -> None:
        """Decide on one read of the events; `_EventsLag` when they may lag behind the issue."""
        fix = f"ask a maintainer to add the label `{label}` again"
        try:
            labelled = [
                e for e in events if e.get("event") == "labeled" and e["label"]["name"] == label
            ]
            if not labelled:
                raise _EventsLag(
                    f"#{number}: no event shows who added the label `{label}`; {fix}",
                    "no event lists the label",
                )
            last = max(labelled, key=lambda e: _moment(e["created_at"]))
            since = _moment(last["created_at"])
            updated = _moment(data["updated_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TrackerError(f"GitHub API: unexpected events for #{number}: {exc!r}") from None
        labeller = _login(last.get("actor"))
        if not self._can_write(labeller):
            raise IssueRefused(
                f"#{number}: the label `{label}` was added by {labeller!r},"
                f" who cannot write to {self._repository}; ask a maintainer to add it"
            )
        if updated > since + _LABEL_SLACK:
            raise _EventsLag(
                f"#{number} changed after the label `{label}` was added"
                f" (edit, rename, comment or other label); {fix}",
                "the issue changed after the last listed label event",
            )

    def _can_write(self, user: str) -> bool:
        """The owner of a user-owned repository, or a writer per the permissions endpoint."""
        if not user:
            return False
        if self._user_owner is None:
            repo = self._request("GET", f"/repos/{self._repository}")
            owner = repo.get("owner")
            self._user_owner = ""
            if isinstance(owner, dict) and owner.get("type") == "User":
                self._user_owner = str(owner.get("login") or "")
        if self._user_owner and user.casefold() == self._user_owner.casefold():
            return True
        quoted = urllib.parse.quote(user, safe="")
        try:
            data = self._request(
                "GET", f"/repos/{self._repository}/collaborators/{quoted}/permission"
            )
        except TrackerError as exc:
            if "HTTP 404" in str(exc):
                return False
            raise IssueRefused(f"cannot check whether {user!r} can write: {exc}") from None
        return data.get("permission") in _WRITERS or data.get("role_name") in _WRITERS

    def open_pull_request(
        self, *, head: str, base: str, title: str, body: str, draft: bool = False
    ) -> PullRequest:
        data = self._request(
            "POST",
            f"/repos/{self._repository}/pulls",
            {"head": head, "base": base, "title": title, "body": body}
            | ({"draft": True} if draft else {}),
        )
        try:
            return PullRequest(number=int(data["number"]), url=str(data["html_url"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise TrackerError(f"GitHub API: unexpected pull request: {exc!r}") from None

    def add_labels(self, number: int, labels: list[str]) -> None:
        # A pull request's labels are its issue's; GitHub creates a label it does not know.
        self._request_any(
            "POST", f"/repos/{self._repository}/issues/{number}/labels", {"labels": labels}
        )

    def comment(self, number: int, body: str) -> None:
        # A pull request's conversation comments are its issue's.
        self._request("POST", f"/repos/{self._repository}/issues/{number}/comments", {"body": body})

    def file_url(self, branch: str, path: str) -> str:
        return f"{self._web_url}/{self._repository}/blob/{branch}/{path}"

    def set_commit_status(
        self, sha: str, context: str, state: str, description: str, target_url: str
    ) -> None:
        self._request(
            "POST",
            f"/repos/{self._repository}/statuses/{sha}",
            {
                "state": state,
                "context": context,
                "description": description,
                "target_url": target_url,
            },
        )

    def pull_request_state(self, branch: str) -> PullRequestState | None:
        owner = urllib.parse.quote(self._repository.split("/")[0], safe="")
        head = urllib.parse.quote(f"{owner}:{branch}", safe=":")
        path = f"/repos/{self._repository}/pulls?state=all&sort=created&direction=desc&head={head}"
        found = self._request_any("GET", path)
        if not isinstance(found, list):
            raise TrackerError(f"GitHub API GET {path}: unexpected response")
        if not found:
            return None
        try:
            data = found[0]
            merged = data.get("merged_at")
            return PullRequestState(
                opened=str(data["created_at"]),
                ended=str(merged or data.get("closed_at") or ""),
                merged=bool(merged),
                number=int(data.get("number") or 0),
            )
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise TrackerError(f"GitHub API: unexpected pull request: {exc!r}") from None

    def changes_requested(self, number: int) -> bool:
        reviews = self._pages(f"/repos/{self._repository}/pulls/{number}/reviews")
        return any(
            r.get("state") == "CHANGES_REQUESTED"
            and isinstance(r.get("user"), dict)
            and r["user"].get("type") == "User"  # a bot account's type is "Bot"
            for r in reviews
        )

    def _request(self, method: str, path: str, payload: Any = None) -> dict[str, Any]:
        result = self._request_any(method, path, payload)
        if not isinstance(result, dict):
            raise TrackerError(f"GitHub API {method} {path}: unexpected response")
        return result

    def _request_any(self, method: str, path: str, payload: Any = None) -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(self._api_url + path, data=data, method=method)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", "ariane")
        request.add_header("Authorization", f"Bearer {self._token}")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with _OPENER.open(request, timeout=_TIMEOUT_S) as response:
                body = response.read().decode("utf-8", errors="replace")
                logs.emit("github.request", f"{method} {path}: HTTP {response.status}")
        except urllib.error.HTTPError as exc:
            logs.emit("github.request", f"{method} {path}: HTTP {exc.code}")
            detail = exc.read().decode("utf-8", errors="replace")
            raise TrackerError(
                f"GitHub API {method} {path}: HTTP {exc.code} {_message(detail)}"
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            logs.emit("github.request", f"{method} {path}: failed ({reason})")
            raise TrackerError(f"GitHub API {method} {path}: {reason}") from None
        try:
            result = json.loads(body)
        except json.JSONDecodeError:
            raise TrackerError(
                f"GitHub API {method} {path}: response is not JSON: {body[:200]!r}"
            ) from None
        return result


def _moment(text: str) -> datetime:
    return datetime.fromisoformat(text)


def _login(user: Any) -> str:
    return str(user["login"]) if isinstance(user, dict) and user.get("login") else ""


def _message(detail: str) -> str:
    """The `message` field of a GitHub error body, or the start of the raw body."""
    try:
        parsed = json.loads(detail)
    except json.JSONDecodeError:
        return detail[:200]
    if isinstance(parsed, dict):
        message = str(parsed.get("message", ""))
        errors = parsed.get("errors")
        if isinstance(errors, list) and errors:
            message += " " + "; ".join(
                str(e.get("message", e)) if isinstance(e, dict) else str(e) for e in errors
            )
        return message.strip()
    return detail[:200]
