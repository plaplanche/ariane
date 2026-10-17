"""The issue gate (C21): only a labelled-by-a-writer, not-edited-since issue runs (ADR 0032)."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from test_cli import VALID_TOML, ariane
from test_config import VALID

from ariane import config, flow, git
from ariane.github import GitHubTracker
from ariane.tracker import IssueRefused

from conftest import FakeRuntime, Project, make_config, sh

LABELLED = "2026-10-01T10:00:00Z"
BEFORE = "2026-10-01T09:00:00Z"
AFTER = "2026-10-01T11:00:00Z"
SAME_MOMENT = "2026-10-01T10:00:01Z"
TWO_SECONDS_LATER = "2026-10-01T10:00:02Z"
PERMISSIONS = {"alice": "admin", "mia": "maintain", "wendy": "write", "rita": "read"}


class Fake:
    """A fake GitHub: one issue, its events, the repository's owner and users' permissions."""

    def __init__(self) -> None:
        self.labels = ["ariane"]
        self.events: list[dict[str, Any]] = [self.labeled("wendy", LABELLED)]
        self.updated_at = LABELLED
        self.owner = {"login": "Olivia", "type": "User"}
        self.permission_status = 200
        self.paths: list[str] = []
        self.lag = 0
        self.late: list[dict[str, Any]] | None = None
        self.reads = 0

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
                "updated_at": self.updated_at,
            }
        if route == "/repos/o/n/issues/5/events":
            self.reads += 1
            if self.reads <= self.lag:
                return 200, self.events if self.late is not None else []
            return 200, self.events + (self.late or [])
        if route == "/repos/o/n":
            return 200, {"full_name": "o/n", "owner": self.owner}
        prefix = "/repos/o/n/collaborators/"
        if route.startswith(prefix) and route.endswith("/permission"):
            if self.permission_status != 200:
                return self.permission_status, {"message": "Forbidden"}
            user = route[len(prefix) : -len("/permission")]
            if user not in PERMISSIONS:
                return 404, {"message": "Not Found"}
            return 200, {"permission": PERMISSIONS[user]}
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


def gate(url: str, label: str = "ariane", sleeps: list[float] | None = None) -> GitHubTracker:
    record = sleeps if sleeps is not None else []
    return GitHubTracker(
        repository="o/n", token="t", api_url=url, ready_label=label, sleep=record.append
    )


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


def test_c21_issue_gate_refuses_an_issue_changed_after_the_label(fake: tuple[Fake, str]) -> None:
    state, url = fake
    state.updated_at = AFTER
    with pytest.raises(IssueRefused, match=r"#5 changed after the label `ariane`.*again"):
        gate(url).read_issue(5)


def test_c21_issue_gate_accepts_an_update_in_the_seconds_of_the_label(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.updated_at = SAME_MOMENT
    assert gate(url).read_issue(5).number == 5


def test_c21_issue_gate_refuses_an_update_two_seconds_after_the_label(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.updated_at = TWO_SECONDS_LATER
    with pytest.raises(IssueRefused, match="changed after the label"):
        gate(url).read_issue(5)


def test_c21_issue_gate_compares_the_owner_login_without_case_and_reads_the_repository_once(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.owner = {"login": "OLIVIA", "type": "User"}
    state.events = [state.labeled("olivia", LABELLED)]
    tracker = gate(url)
    tracker.read_issue(5)
    tracker.read_issue(5)
    assert state.paths.count("/repos/o/n") == 1


def test_c21_issue_gate_accepts_a_change_made_before_the_label(fake: tuple[Fake, str]) -> None:
    state, url = fake
    state.events = [
        {"event": "renamed", "actor": {"login": "rita"}, "created_at": BEFORE},
        state.labeled("wendy", LABELLED),
    ]
    assert gate(url).read_issue(5).number == 5


def test_c21_issue_gate_trusts_the_owner_of_a_user_repository_without_a_permission_call(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.events = [state.labeled("olivia", LABELLED)]
    state.permission_status = 403
    assert gate(url).read_issue(5).number == 5
    assert not [p for p in state.paths if "/collaborators/" in p]
    assert "/graphql" not in state.paths


def test_c21_issue_gate_does_not_trust_the_owner_login_of_an_organisation(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.owner = {"login": "olivia", "type": "Organization"}
    state.events = [state.labeled("olivia", LABELLED)]
    with pytest.raises(IssueRefused, match="'olivia'"):
        gate(url).read_issue(5)


def test_c21_issue_gate_refuses_when_the_permission_check_is_blocked(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.permission_status = 403
    with pytest.raises(IssueRefused, match=r"cannot check whether 'wendy' can write.*403"):
        gate(url).read_issue(5)


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


def _cli(project: Project, url: str, *args: str) -> subprocess.CompletedProcess[str]:
    toml = VALID_TOML.replace('repository = "owner/name"', f'repository = "o/n"\napi_url = "{url}"')
    (project.root / "ariane.toml").write_text(toml, encoding="utf-8")
    env = {**os.environ, "ARIANE_TEST_TOKEN": "t", "NO_PROXY": "127.0.0.1,localhost"}
    for name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        env.pop(name, None)
    return ariane(project.root, *args, env=env)


def test_c21_issue_gate_cli_start_passes_the_configured_label(
    project: Project, fake: tuple[Fake, str]
) -> None:
    state, url = fake
    state.labels = ["bug"]
    done = _cli(project, url, "start", "5")
    assert done.returncode == 2
    assert "does not carry the label `ariane`" in done.stderr + done.stdout
    assert not git.local_branch_exists(project.root, "ariane/5")


def test_c21_issue_gate_cli_verify_issue_refuses_and_reviews_nothing(
    project: Project, fake: tuple[Fake, str]
) -> None:
    state, url = fake
    state.events = [state.labeled("rita", LABELLED)]
    sh(["git", "branch", "work-branch"], project.root)
    done = _cli(project, url, "verify", "work-branch", "--issue", "5")
    assert done.returncode == 2
    assert "'rita'" in done.stderr + done.stdout
    assert git.worktree_of(project.root, "work-branch") is None
    assert not (project.root / "work" / "verify").exists()


def test_c21_issue_gate_a_user_without_permission_record_cannot_write(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.events = [state.labeled("ghost", LABELLED)]
    with pytest.raises(IssueRefused, match="'ghost'"):
        gate(url).read_issue(5)


def test_c21_issue_gate_retry_accepts_an_event_listed_from_the_third_read(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.lag = 2
    sleeps: list[float] = []
    assert gate(url, sleeps=sleeps).read_issue(5).number == 5
    assert sleeps == [1, 2]


def test_c21_issue_gate_retry_refuses_after_five_reads_when_the_event_never_comes(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.lag = 99
    sleeps: list[float] = []
    with pytest.raises(IssueRefused, match="no event shows who added the label `ariane`"):
        gate(url, sleeps=sleeps).read_issue(5)
    assert sleeps == [1, 2, 4, 8]
    assert state.paths.count("/repos/o/n/issues/5/events") == 5
    assert state.paths.count("/repos/o/n/issues/5") == 1


def test_c21_issue_gate_retry_does_not_wait_for_an_absent_label_or_a_reader(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    sleeps: list[float] = []
    state.labels = ["bug"]
    with pytest.raises(IssueRefused, match="does not carry"):
        gate(url, sleeps=sleeps).read_issue(5)
    state.labels = ["ariane"]
    state.events = [state.labeled("rita", LABELLED)]
    with pytest.raises(IssueRefused, match="cannot write"):
        gate(url, sleeps=sleeps).read_issue(5)
    assert sleeps == []
    assert state.paths.count("/repos/o/n/issues/5/events") == 1


def test_c21_issue_gate_retry_accepts_a_re_added_label_listed_on_the_second_read(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.events = [state.labeled("wendy", BEFORE)]
    state.late = [state.labeled("wendy", AFTER)]
    state.updated_at = AFTER
    state.lag = 1
    sleeps: list[float] = []
    assert gate(url, sleeps=sleeps).read_issue(5).number == 5
    assert sleeps == [1]


def test_c21_issue_gate_retry_refuses_a_change_after_the_label_after_five_reads(
    fake: tuple[Fake, str],
) -> None:
    state, url = fake
    state.events = [state.labeled("wendy", BEFORE)]
    state.updated_at = AFTER
    sleeps: list[float] = []
    with pytest.raises(IssueRefused, match="changed after the label"):
        gate(url, sleeps=sleeps).read_issue(5)
    assert sleeps == [1, 2, 4, 8]
    assert state.paths.count("/repos/o/n/issues/5/events") == 5


def test_c21_issue_gate_retry_logs_each_retried_read_with_its_reason(
    fake: tuple[Fake, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from ariane import logs

    records: list[tuple[str, str]] = []
    monkeypatch.setattr(logs, "emit", lambda type_id, message: records.append((type_id, message)))
    retried = "github.label_event_retry"
    state, url = fake
    state.lag = 99
    with pytest.raises(IssueRefused):
        gate(url, sleeps=[]).read_issue(5)
    retries = [m for t, m in records if t == retried]
    assert len(retries) == 4
    assert "read 1 of the events retried in 1 s: no event lists the label" in retries[0]
    records.clear()
    state.labels = ["bug"]
    with pytest.raises(IssueRefused):
        gate(url, sleeps=[]).read_issue(5)
    assert [t for t, _ in records if t == retried] == []
