"""GitHub tracker over the REST API, with the standard library only (ADR 0007)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from ariane import logs
from ariane.tracker import Issue, IssueRefused, PullRequest, TrackerError

_TIMEOUT_S = 30
_PAGE = 100
_WRITERS = frozenset({"write", "maintain", "admin"})


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
        self, *, repository: str, token: str, api_url: str, ready_label: str | None = None
    ) -> None:
        self._ready_label = ready_label
        self._repository = repository
        self._token = token
        self._api_url = api_url.rstrip("/")
        self._web_url = web_url(api_url)
        base = self._api_url
        self._graphql_root = base.removesuffix("/v3") if base.endswith("/api/v3") else base

    def read_issue(self, number: int) -> Issue:
        data = self._request("GET", f"/repos/{self._repository}/issues/{number}")
        if "pull_request" in data:
            raise TrackerError(f"#{number} is a pull request, not an issue")
        if self._ready_label is not None:
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
        """Refuse an issue not labelled by a writer, or edited by a non-writer since (C21)."""
        fix = f"ask a maintainer to add the label `{label}` again after the last edit"
        names = [
            str(item.get("name")) for item in data.get("labels") or [] if isinstance(item, dict)
        ]
        if label not in names:
            raise IssueRefused(
                f"#{number} does not carry the label `{label}`; ask a maintainer to add it"
            )
        path = f"/repos/{self._repository}/issues/{number}/events"
        events: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self._request_any("GET", f"{path}?per_page={_PAGE}&page={page}")
            if not isinstance(batch, list):
                raise TrackerError(f"GitHub API GET {path}: unexpected response")
            events += [e for e in batch if isinstance(e, dict)]
            if len(batch) < _PAGE:
                break
            page += 1
        try:
            labelled = [
                e for e in events if e.get("event") == "labeled" and e["label"]["name"] == label
            ]
            if not labelled:
                raise IssueRefused(
                    f"#{number}: no event shows who added the label `{label}`; {fix}"
                )
            last = max(labelled, key=lambda e: _moment(e["created_at"]))
            since = _moment(last["created_at"])
            if not self._can_write(_login(last.get("actor"))):
                raise IssueRefused(
                    f"#{number}: the label `{label}` was added by {_login(last.get('actor'))!r},"
                    f" who cannot write to {self._repository}; ask a maintainer to add it"
                )
            for event in events:
                if event.get("event") == "renamed" and _moment(event["created_at"]) >= since:
                    who = _login(event.get("actor"))
                    if not self._can_write(who):
                        raise IssueRefused(
                            f"#{number}: the title was changed by {who!r} after the label; {fix}"
                        )
            edited, editor = self._body_edit(number)
        except (KeyError, TypeError, ValueError) as exc:
            raise TrackerError(f"GitHub API: unexpected events for #{number}: {exc!r}") from None
        if edited is not None and edited >= since and not self._can_write(editor):
            raise IssueRefused(
                f"#{number}: the body was edited by {editor!r} after the label; {fix}"
            )

    def _body_edit(self, number: int) -> tuple[datetime | None, str]:
        """When the body was last edited and by whom (GraphQL `lastEditedAt`, `editor`)."""
        owner, name = self._repository.split("/")
        query = (
            "query($owner: String!, $name: String!, $number: Int!) {"
            " repository(owner: $owner, name: $name) {"
            " issue(number: $number) { lastEditedAt editor { login } } } }"
        )
        result = self._request_any(
            "POST",
            "/graphql",
            {"query": query, "variables": {"owner": owner, "name": name, "number": number}},
            base=self._graphql_root,
        )
        try:
            issue = result["data"]["repository"]["issue"]
            when = issue["lastEditedAt"]
            return (None, "") if when is None else (_moment(when), _login(issue["editor"]))
        except (KeyError, TypeError, ValueError):
            raise TrackerError(f"GitHub API: unexpected GraphQL answer for #{number}") from None

    def _can_write(self, user: str) -> bool:
        if not user:
            return False
        quoted = urllib.parse.quote(user, safe="")
        data = self._request("GET", f"/repos/{self._repository}/collaborators/{quoted}/permission")
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

    def _request(self, method: str, path: str, payload: Any = None) -> dict[str, Any]:
        result = self._request_any(method, path, payload)
        if not isinstance(result, dict):
            raise TrackerError(f"GitHub API {method} {path}: unexpected response")
        return result

    def _request_any(
        self, method: str, path: str, payload: Any = None, *, base: str | None = None
    ) -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request((base or self._api_url) + path, data=data, method=method)
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
