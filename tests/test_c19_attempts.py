"""C19: the pushes and pull requests an agent attempted are counted per ticket (ADR 0036)."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest

from ariane.attempts import Attempts, count
from ariane.claude_code import TokenTally
from ariane.opencode import Events
from ariane.runtime import Session, SessionResult
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, sh
from test_flow import start


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git push origin x", Attempts(push=1)),
        ("gh pr create --title x", Attempts(pull_request=1)),
        ("git pushd", Attempts()),
        ('echo "git push"', Attempts()),
        ("cd sub && git -C x push --force", Attempts(push=1)),
        ("FOO=1 git push; gh pr create", Attempts(push=1, pull_request=1)),
        ("bash -c 'git push origin x'", Attempts(push=1)),
        ("git status\ngit push", Attempts(push=1)),
        ("echo 'unbalanced", Attempts()),
    ],
)
def test_c19_attempts_count_commands_not_quoted_text(command: str, expected: Attempts) -> None:
    assert count(command) == expected


def claude_event(command: str, call: str = "t1") -> str:
    block = {"type": "tool_use", "id": call, "name": "Bash", "input": {"command": command}}
    message = {"id": "m1", "content": [block], "usage": {"input_tokens": 1}}
    return json.dumps({"type": "assistant", "message": message})


def test_c19_attempts_claude_stream_counts_each_tool_call_once() -> None:
    tally = TokenTally(None)
    for line in (claude_event("git push origin x"), claude_event("git push origin x")):
        tally.add_line(line)  # a streamed message repeats its blocks
    tally.add_line(claude_event('echo "git push"', "t2"))
    tally.add_line(claude_event("gh pr create", "t3"))
    assert tally.attempts.attempts == Attempts(push=1, pull_request=1)


def test_c19_attempts_opencode_events_count_shell_calls() -> None:
    events = Events(None, None)
    for command, call in (("git push origin x", "c1"), ("git pushd", "c2"), ("gh pr create", "c3")):
        part = {"tool": "bash", "callID": call, "state": {"input": {"command": command}}}
        events.add_line(json.dumps({"type": "tool_use", "part": part}))
    assert events.attempts.attempts == Attempts(push=1, pull_request=1)


class Pushing(FakeRuntime):
    def run(self, session: Session) -> SessionResult:
        done = super().run(session)
        return dataclasses.replace(done, attempts=Attempts(push=2, pull_request=1))


def test_c19_attempts_reach_metrics_json(project: Project, tracker: InMemoryTracker) -> None:
    assert start(project, tracker, Pushing()).exit_code == 0
    data: dict[str, Any] = json.loads(project.show("ariane/7", "work/7/metrics.json"))
    # The implementer and the reviewer sessions each report the same counts.
    assert data["attempts"] == {"push": 4, "pull_request": 2, "guard_violations": 0}


def test_c19_attempts_guard_violation_is_counted(
    project: Project, tracker: InMemoryTracker
) -> None:
    def meddle(session: Session) -> None:
        sh(["git", "config", "core.sneaky", "1"], session.cwd)

    assert start(project, tracker, FakeRuntime(action=meddle)).exit_code == 1
    data = json.loads(sh(["git", "show", "ariane/7:work/7/metrics.json"], project.root))
    assert data["attempts"]["guard_violations"] == 1
