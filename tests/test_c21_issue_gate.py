"""The issue gate (C21): only a labelled-by-a-writer, not-edited-since issue runs (ADR 0032)."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from test_config import VALID

from ariane import config, flow, git
from ariane.github import GitHubTracker
from ariane.tracker import IssueRefused

from conftest import FakeRuntime, Project, make_config

LABELLED = "2026-10-01T10:00:00Z"
BEFORE = "2026-10-01T09:00:00Z"
AFTER = "2026-10-01T11:00:00Z"
PERMISSIONS = {"alice": "admin", "mia": "maintain", "wendy": "write", "rita": "read"}


class Fake:
    """A fake GitHub: one issue, its events, the body edit and the users' permissions."""

    def __init__(self) -> None:
        self.labels = ["ariane"]
        self.events: list[dict[str, Any]] = [self.labeled("wendy", LABELLED)]
        self.edit: tuple[str, str] | None = None
        self.paths: list[str] = []

    @staticmethod
    def labeled(actor: str, when: str, name: str = "ariane") -> dict[str, Any]:
        return {
            "event": "labeled",
            "label": {"name": name},
            "actor": {"login": actor},
            "created_at": when,
        }

    def reply(self, method: str, path: str, body: Any) -> tuple[int, Any]:
        route = path.split("?")[0]
        self.paths.append(route)
        if route == "/repos/o/n/issues/5":
            return 200, {
                "number": 5,
                "title": "T",
                "body": "B",
                "html_url": "https://x/5",
                "labels": [{"name": n} for n in self.labels],
            }
        if route == "/repos/o/n/issues/5/events":
            return 200, self.events
        if route == "/graphql":
            issue: dict[str, Any] = {"lastEditedAt": None, "editor": None}
            if self.edit:
                issue = {"lastEditedAt": self.edit[1], "editor": {"login": self.edit[0]}}
            return 200, {"data": {"repository": {"issue": issue}}}
        prefix = "/repos/o/n/collaborators/"
        if route.startswith(prefix) and route.endswith("/permission"):
            user = route[len(prefix) : -len("/permission")]
            return 200, {"permission": PERMISSIONS.get(user, "none")}
        return 404, {"message": "Not Found"}


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Fake, str]]:
    for name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    state = Fake()

    class Handler(BaseHTTPRequestHandler):
        def _serve(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            status, payload = state.reply(self.command, self.path, json.loads(raw) if raw else None)
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = _serve

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield state, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def gate(url: str, label: str = "ariane") -> GitHubTracker:
    return GitHubTracker(repository="o/n", token="t", api_url=url, ready_label=label)


def test_c21_issue_gate_accepts_an_issue_labelled_by_a_writer_and_not_edited(
    fake: tuple[Fake, str],
) -> None:
    _, url = fake
    assert gate(url).read_issue(5).title == "T"


def test_c21_issue_gate_accepts_a_maintainer_or_an_admin_as_labeller(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    for user in ("mia", "alice"):
        state.events = [state.labeled(user, LABELLED)]
        assert gate(url).read_issue(5).number == 5


def test_c21_issue_gate_refuses_an_issue_without_the_label(fake: tuple[Fake, str]) -> None:
    state, url = fake
    state.labels = ["bug"]
    with pytest.raises(IssueRefused, match="does not carry the label `ariane`"):
        gate(url).read_issue(5)


def test_c21_issue_gate_refuses_a_label_added_by_a_reader(fake: tuple[Fake, str]) -> None:
    state, url = fake
    state.events = [state.labeled("rita", LABELLED)]
    with pytest.raises(IssueRefused, match=r"'rita'.*cannot write"):
        gate(url).read_issue(5)


def test_c21_issue_gate_uses_the_last_time_the_label_was_added(fake: tuple[Fake, str]) -> None:
    state, url = fake
    state.events = [state.labeled("wendy", BEFORE), state.labeled("rita", LABELLED)]
    with pytest.raises(IssueRefused, match="'rita'"):
        gate(url).read_issue(5)


def test_c21_issue_gate_refuses_a_body_edited_by_a_reader_after_the_label(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.edit = ("rita", AFTER)
    with pytest.raises(
        IssueRefused, match=r"body was edited by 'rita'.*add the label `ariane` again"
    ):
        gate(url).read_issue(5)


def test_c21_issue_gate_accepts_a_body_edited_by_a_writer_after_the_label(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.edit = ("wendy", AFTER)
    assert gate(url).read_issue(5).number == 5


def test_c21_issue_gate_accepts_a_body_edited_by_a_reader_before_the_label(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.edit = ("rita", BEFORE)
    assert gate(url).read_issue(5).number == 5


def test_c21_issue_gate_refuses_a_title_renamed_by_a_reader_after_the_label(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.events.append({"event": "renamed", "actor": {"login": "rita"}, "created_at": AFTER})
    with pytest.raises(IssueRefused, match="title was changed by 'rita'"):
        gate(url).read_issue(5)


def test_c21_issue_gate_accepts_a_title_renamed_by_a_writer_after_the_label(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.events.append({"event": "renamed", "actor": {"login": "wendy"}, "created_at": AFTER})
    assert gate(url).read_issue(5).number == 5


def test_c21_issue_gate_uses_the_configured_label(fake: tuple[Fake, str]) -> None:
    state, url = fake
    state.labels = ["ready"]
    state.events = [state.labeled("wendy", LABELLED, "ready")]
    assert gate(url, "ready").read_issue(5).number == 5
    with pytest.raises(IssueRefused):
        gate(url).read_issue(5)


def test_c21_issue_gate_ready_label_is_read_from_the_configuration() -> None:
    assert config.parse(VALID).tracker.ready_label == "ariane"
    data = {**VALID, "tracker": {**VALID["tracker"], "ready_label": "go"}}
    assert config.parse(data).tracker.ready_label == "go"


def test_c21_issue_gate_start_refuses_with_exit_2_and_creates_nothing(
    project: Project, fake: tuple[Fake, str]
) -> None:
    state, url = fake
    state.events = [state.labeled("rita", LABELLED)]
    outcome = flow.start(
        5,
        repo_root=project.root,
        config=make_config(),
        tracker=gate(url),
        runtime=FakeRuntime(),
        environ={**os.environ, "GH_TOKEN": "t"},
    )
    assert outcome.exit_code == 2
    assert "Did not start #5" in outcome.line
    assert not git.local_branch_exists(project.root, "ariane/5")
    assert not flow.worktree_path(project.root, 5).exists()
