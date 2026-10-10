"""The GitHub tracker against a local HTTP stub: requests, refusals, errors without the token."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from ariane.github import GitHubTracker, web_url
from ariane.tracker import TrackerError

TOKEN = "ghp_secret_for_tests"


class Stub:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.responses: dict[tuple[str, str], tuple[int, Any]] = {}


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Stub, str]]:
    for name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    state = Stub()

    class Handler(BaseHTTPRequestHandler):
        def _reply(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length).decode("utf-8") if length else ""
            state.requests.append(
                {
                    "method": self.command,
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": json.loads(body) if body else None,
                }
            )
            status, payload = state.responses.get((self.command, self.path), (404, {}))
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
            self.send_response(status)
            if status in (301, 302, 307, 308):
                self.send_header("Location", "http://127.0.0.1:9/elsewhere")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = _reply

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield state, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def tracker(url: str) -> GitHubTracker:
    return GitHubTracker(repository="owner/name", token=TOKEN, api_url=url + "/")


def test_c1_reads_title_and_body_with_the_token(stub: tuple[Stub, str]) -> None:
    state, url = stub
    state.responses[("GET", "/repos/owner/name/issues/5")] = (
        200,
        {"number": 5, "title": "Add --version", "body": None, "html_url": "https://x/5"},
    )
    issue = tracker(url).read_issue(5)
    assert (issue.number, issue.title, issue.body, issue.url) == (
        5,
        "Add --version",
        "",
        "https://x/5",
    )
    headers = state.requests[0]["headers"]
    assert headers["Authorization"] == f"Bearer {TOKEN}"
    assert headers["Accept"] == "application/vnd.github+json"


def test_c1_a_pull_request_number_is_refused(stub: tuple[Stub, str]) -> None:
    state, url = stub
    state.responses[("GET", "/repos/owner/name/issues/6")] = (
        200,
        {"number": 6, "title": "t", "body": "", "html_url": "h", "pull_request": {}},
    )
    with pytest.raises(TrackerError, match="#6 is a pull request"):
        tracker(url).read_issue(6)


def test_c11_opens_a_pull_request_from_the_ticket_branch(stub: tuple[Stub, str]) -> None:
    state, url = stub
    state.responses[("POST", "/repos/owner/name/pulls")] = (
        201,
        {"number": 12, "html_url": "https://github.com/owner/name/pull/12"},
    )
    pull = tracker(url).open_pull_request(head="ariane/5", base="main", title="T", body="Closes #5")
    assert (pull.number, pull.url) == (12, "https://github.com/owner/name/pull/12")
    assert state.requests[0]["body"] == {
        "head": "ariane/5",
        "base": "main",
        "title": "T",
        "body": "Closes #5",
    }
    assert tracker(url).file_url("ariane/5", "work/5/checks.md") == (
        f"{url}/owner/name/blob/ariane/5/work/5/checks.md"
    )


def test_c10_fix_round_a_draft_pull_request_is_requested_as_a_draft(
    stub: tuple[Stub, str],
) -> None:
    state, url = stub
    state.responses[("POST", "/repos/owner/name/pulls")] = (
        201,
        {"number": 13, "html_url": "https://github.com/owner/name/pull/13"},
    )
    tracker(url).open_pull_request(head="ariane/5", base="main", title="T", body="B", draft=True)
    assert state.requests[0]["body"]["draft"] is True


def test_c9_sets_a_commit_status_with_the_documented_request(stub: tuple[Stub, str]) -> None:
    state, url = stub
    state.responses[("POST", "/repos/owner/name/statuses/abc123")] = (201, {"id": 1})
    tracker(url).set_commit_status("abc123", "ariane/lint", "failure", "exit 1, 2.0 s", "https://r")
    request = state.requests[0]
    assert (request["method"], request["path"]) == ("POST", "/repos/owner/name/statuses/abc123")
    assert request["body"] == {
        "state": "failure",
        "context": "ariane/lint",
        "description": "exit 1, 2.0 s",
        "target_url": "https://r",
    }
    assert request["headers"]["Authorization"] == f"Bearer {TOKEN}"


def test_c9_a_refused_commit_status_is_a_tracker_error_without_the_token(
    stub: tuple[Stub, str],
) -> None:
    state, url = stub
    state.responses[("POST", "/repos/owner/name/statuses/abc123")] = (
        403,
        {"message": "Resource not accessible by personal access token"},
    )
    with pytest.raises(TrackerError, match="HTTP 403 Resource not accessible") as error:
        tracker(url).set_commit_status("abc123", "ariane/lint", "success", "exit 0", "https://r")
    assert TOKEN not in str(error.value)


@pytest.mark.parametrize(
    ("api", "web"),
    [
        ("https://api.github.com", "https://github.com"),
        ("https://api.github.com/", "https://github.com"),
        ("https://git.example.invalid/api/v3", "https://git.example.invalid"),
    ],
)
def test_c1_the_report_link_uses_the_web_address_of_the_api(api: str, web: str) -> None:
    assert web_url(api) == web


def test_c1_http_errors_are_explained_without_the_token(stub: tuple[Stub, str]) -> None:
    state, url = stub
    state.responses[("POST", "/repos/owner/name/pulls")] = (
        422,
        {"message": "Validation Failed", "errors": [{"message": "No commits between main and x"}]},
    )
    with pytest.raises(TrackerError) as error:
        tracker(url).open_pull_request(head="x", base="main", title="T", body="")
    assert "HTTP 422 Validation Failed No commits between main and x" in str(error.value)
    with pytest.raises(TrackerError, match="HTTP 404") as missing:
        tracker(url).read_issue(404)
    assert TOKEN not in str(error.value) + str(missing.value)


def test_c1_an_unreachable_api_is_a_tracker_error() -> None:
    with pytest.raises(TrackerError, match="GitHub API GET"):
        tracker("http://127.0.0.1:9").read_issue(1)


@pytest.mark.parametrize(
    "payload",
    [b"<html>not the API</html>", [1, 2], {"title": "no number", "html_url": "h"}],
)
def test_c1_an_unexpected_success_body_is_a_tracker_error(
    stub: tuple[Stub, str], payload: Any
) -> None:
    state, url = stub
    state.responses[("GET", "/repos/owner/name/issues/5")] = (200, payload)
    with pytest.raises(TrackerError, match="GitHub API"):
        tracker(url).read_issue(5)


def test_c21_a_redirect_is_refused_so_the_token_never_follows_it(stub: tuple[Stub, str]) -> None:
    state, url = stub
    state.responses[("GET", "/repos/owner/name/issues/5")] = (302, {})
    with pytest.raises(TrackerError, match="HTTP 302"):
        tracker(url).read_issue(5)
    assert len(state.requests) == 1
