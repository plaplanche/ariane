"""GitHub tracker over the REST API, with the standard library only (ADR 0007)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ariane.tracker import Issue, PullRequest, TrackerError

_TIMEOUT_S = 30


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
    def __init__(self, *, repository: str, token: str, api_url: str) -> None:
        self._repository = repository
        self._token = token
        self._api_url = api_url.rstrip("/")
        self._web_url = web_url(api_url)

    def read_issue(self, number: int) -> Issue:
        data = self._request("GET", f"/repos/{self._repository}/issues/{number}")
        if "pull_request" in data:
            raise TrackerError(f"#{number} is a pull request, not an issue")
        try:
            return Issue(
                number=int(data["number"]),
                title=str(data["title"]),
                body=str(data.get("body") or ""),
                url=str(data["html_url"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise TrackerError(f"GitHub API: unexpected issue #{number}: {exc!r}") from None

    def open_pull_request(self, *, head: str, base: str, title: str, body: str) -> PullRequest:
        data = self._request(
            "POST",
            f"/repos/{self._repository}/pulls",
            {"head": head, "base": base, "title": title, "body": body},
        )
        try:
            return PullRequest(number=int(data["number"]), url=str(data["html_url"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise TrackerError(f"GitHub API: unexpected pull request: {exc!r}") from None

    def file_url(self, branch: str, path: str) -> str:
        return f"{self._web_url}/{self._repository}/blob/{branch}/{path}"

    def _request(self, method: str, path: str, payload: Any = None) -> dict[str, Any]:
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
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise TrackerError(
                f"GitHub API {method} {path}: HTTP {exc.code} {_message(detail)}"
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise TrackerError(f"GitHub API {method} {path}: {reason}") from None
        try:
            result = json.loads(body)
        except json.JSONDecodeError:
            raise TrackerError(
                f"GitHub API {method} {path}: response is not JSON: {body[:200]!r}"
            ) from None
        if not isinstance(result, dict):
            raise TrackerError(f"GitHub API {method} {path}: unexpected response")
        return result


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
