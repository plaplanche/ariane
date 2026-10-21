"""`ariane next --start`: a confirmed proposal is reserved before any external write, consumed
by its start, held until its ticket registers, and every start is recorded, even one whose
record fails after the launch (C11, C23, ADR 0059)."""

from __future__ import annotations

import contextlib
import getpass
import json
import os
import sys
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
from test_c23_next import LABEL, at, queued

from ariane import flow, next_start, next_ticket, runs
from ariane.tracker import InMemoryTracker, QueuedIssue

from conftest import FakeRuntime, Project, make_config
from test_flow import environ

DEAD = 2**30  # a process id no process has


@dataclass
class Child:
    """A fake ticket started in the background."""

    pid: int
    code: int | None = 0

    def poll(self) -> int | None:
        return self.code


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(next_start, "REGISTER_SECONDS", 0.5)
    monkeypatch.setattr(next_start, "POLL_SECONDS", 0.01)


def registering(
    project: Project, monkeypatch: pytest.MonkeyPatch, launched: list[int]
) -> next_start.Launch:
    """A launch whose ticket registers as running, then ends, as `ariane start` does."""

    def launch(number: int, handed: Mapping[str, str]) -> Child:
        launched.append(number)
        handing(monkeypatch, handed)
        with runs.registered(runs.folder(project.root), number, flow.branch_name(number)):
            pass
        return Child(4000 + number)

    return launch


def handing(monkeypatch: pytest.MonkeyPatch, handed: Mapping[str, str]) -> None:
    """Set the variables of the handoff here, as `spawn` sets them in its ticket."""
    assert sorted(handed) == sorted([runs.HANDOFF_ENV, runs.CLAIM_ENV, runs.ISSUE_ENV])
    for name, value in handed.items():
        monkeypatch.setenv(name, value)


def entries(project: Project) -> list[str]:
    text = next_ticket.record_path(project.root).read_text(encoding="utf-8")
    return [e.split("\n", 1)[0].split(": ", 1)[1] for e in text.split("\n## ")[1:]]


def test_c23_next_start_refuses_a_proposal_that_changed_since_it_was_printed(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracker = InMemoryTracker()
    queued(tracker, 4, "", at(0), "ariane")
    queued(tracker, 5, "", at(1), "ariane")
    launched: list[int] = []
    launch = registering(project, monkeypatch, launched)
    _, outcome = next_start.start(project.root, make_config(), tracker, launch)
    assert outcome.exit_code == flow.EXIT_STOPPED
    assert "was none printed since the last start, now #4 (nothing runs)" in outcome.line
    assert next_start.show(project.root, make_config(), tracker).number == 4
    tracker.closed[4] = "completed"
    _, outcome = next_start.start(project.root, make_config(), tracker, launch)
    assert outcome.line == (
        "Did not start: the proposal changed since it was printed (was #4 (nothing runs), now"
        " #5 (nothing runs)). Next: read it above, then run ariane next --start to confirm it."
    )
    assert launched == []
    assert tracker.removed_labels == []
    _, outcome = next_start.start(project.root, make_config(), tracker, launch)  # just printed
    assert outcome.exit_code == flow.EXIT_OK
    assert launched == [5]


def test_c23_next_start_relabels_the_issue_and_starts_it(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracker = InMemoryTracker()
    queued(tracker, 7, "Set `app.txt` to version 2.", at(0), "ariane")
    queued(tracker, 8, "Needs #7", at(1), "ariane")
    cfg = make_config()
    outcomes: list[flow.Outcome] = []

    def launch(number: int, handed: Mapping[str, str]) -> Child:
        # The fake runtime: the ticket runs here, to its pull request, as `spawn` starts it.
        handing(monkeypatch, handed)
        outcomes.append(
            flow.start(
                number,
                repo_root=project.root,
                config=cfg,
                tracker=tracker,
                runtime=FakeRuntime(),
                environ=environ(),
            )
        )
        return Child(4242)

    assert next_start.show(project.root, cfg, tracker).number == 7
    proposal, outcome = next_start.start(project.root, cfg, tracker, launch)
    assert proposal.number == 7
    assert tracker.removed_labels == [(7, "ariane")]
    assert tracker.labels[7] == [LABEL, "ariane"]
    assert outcomes[0].exit_code == flow.EXIT_OK, outcomes[0].line
    journal = flow.worktree_path(project.root, 7) / "work/7/journal.md"
    assert journal.is_file()
    assert outcome.exit_code == flow.EXIT_OK
    assert outcome.line == (
        f"Started #7 in the background (process 4242); its journal will be {journal}, its output"
        f" {next_ticket.output_path(project.root, 7)}. Next: follow it with ariane status 7."
    )
    assert next_ticket.reservations(project.root) == []
    _, again = next_start.start(project.root, cfg, tracker, launch)
    assert again.exit_code == flow.EXIT_STOPPED  # the start consumed the confirmation
    assert "was none printed since the last start" in again.line
    assert len(outcomes) == 1


def test_c23_next_records_every_proposal_and_start_in_next_md(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(getpass, "getuser", lambda: "owner")
    tracker = InMemoryTracker()
    queued(tracker, 4, "Needs #2", at(0), "ariane")
    queued(tracker, 5, "", at(1), "ariane")
    next_start.show(project.root, make_config(), tracker)
    next_start.start(project.root, make_config(), tracker, registering(project, monkeypatch, []))
    text = next_ticket.record_path(project.root).read_text(encoding="utf-8")
    assert next_ticket.record_path(project.root) == project.root.parent / "proj.ariane/next.md"
    parts = text.split("\n## ")
    assert parts[0] == "# Proposals of ariane next\n"
    assert entries(project) == ["proposal", "start intent", "start"]
    for entry in parts[1:]:
        assert "- Running: none." in entry
        assert "- #4: waits on #2" in entry
        assert "- #5: can start" in entry
        assert "- Proposal: #5 (nothing runs)" in entry
    assert "- Confirmed by: owner (ariane next --start)" in parts[2]
    assert "- Started: #5, process 4005; registered as running" in parts[3]


def test_c23_next_start_concurrent_starts_launch_a_confirmed_proposal_once(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    met = threading.Barrier(2)

    class Racing(InMemoryTracker):
        def queue(self, label: str) -> list[QueuedIssue]:
            with contextlib.suppress(threading.BrokenBarrierError):
                met.wait(1)  # without the handoff lock, both starts read the same proposal
            return super().queue(label)

    tracker = Racing()
    queued(tracker, 7, "Edit `a.txt`.", at(0), "ariane")
    queued(tracker, 8, "Edit `a.txt` too.", at(1), "ariane")
    launched: list[int] = []
    launch = registering(project, monkeypatch, launched)
    met.abort()
    next_start.show(project.root, make_config(), tracker)
    met.reset()
    outcomes: list[flow.Outcome] = []

    def confirm() -> None:
        outcomes.append(next_start.start(project.root, make_config(), tracker, launch)[1])

    threads = [threading.Thread(target=confirm) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert launched == [7]
    assert tracker.removed_labels == [(7, "ariane")]
    assert sorted(o.exit_code for o in outcomes) == [flow.EXIT_OK, flow.EXIT_STOPPED]


def test_c23_next_start_a_registration_waits_for_the_handoff(project: Project) -> None:
    where = runs.folder(project.root)
    done = threading.Event()

    def by_hand() -> None:  # `ariane start 12` run by the owner during a handoff
        with runs.registered(where, 12, "ariane/12"):
            done.set()

    with next_start.handoff(project.root):
        thread = threading.Thread(target=by_hand)
        thread.start()
        assert not done.wait(0.3)
        assert runs.running(where) == {}
    thread.join(10)
    assert done.is_set()


def test_c23_next_start_a_pending_reservation_holds_the_proposals(project: Project) -> None:
    tracker = InMemoryTracker()
    queued(tracker, 9, "", at(0), "ariane")
    queued(tracker, 10, "", at(1), "ariane")
    folder = next_ticket.reservations_folder(project.root)
    folder.mkdir(parents=True)
    held = {"number": 9, "pid": os.getpid(), "at": runs.now(), "state": "launched"}
    (folder / "9.json").write_text(json.dumps(held), encoding="utf-8")
    proposal = next_start.show(project.root, make_config(), tracker)
    assert [c.number for c in proposal.candidates] == [10]
    assert proposal.number is None
    assert proposal.blockers == (f"#9 is starting (process {os.getpid()})",)


def test_c23_next_start_a_record_failure_after_the_launch_is_reported_and_reconciled(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracker = InMemoryTracker()
    queued(tracker, 7, "", at(0), "ariane")
    next_start.show(project.root, make_config(), tracker)
    recorded = next_ticket.record

    def failing(root: Path, title: str, *args: object) -> None:
        if title == "start":
            raise OSError("disk full")
        recorded(root, title, *args)  # type: ignore[arg-type]

    monkeypatch.setattr(next_start, "record", failing)
    _, outcome = next_start.start(
        project.root, make_config(), tracker, registering(project, monkeypatch, [])
    )
    assert outcome.exit_code == flow.EXIT_STOPPED
    assert outcome.line == (
        "Started #7 in the background (process 4007), but next.md could not record it (disk"
        " full). Next: follow it with ariane status 7; the next ariane next records the start."
    )
    assert [r.state for r in next_ticket.reservations(project.root)] == ["launched"]
    monkeypatch.setattr(next_start, "record", recorded)
    next_start.show(project.root, make_config(), tracker)
    assert entries(project) == ["proposal", "start intent", "start reconciled", "proposal"]
    text = next_ticket.record_path(project.root).read_text(encoding="utf-8")
    assert "(process 4007); it registered as running and ended" in text
    assert next_ticket.reservations(project.root) == []


def test_c23_next_start_a_crash_before_the_launch_is_reconciled(project: Project) -> None:
    folder = next_ticket.reservations_folder(project.root)
    folder.mkdir(parents=True)
    left = {"number": 9, "pid": DEAD, "at": "2026-10-21T10:00:00+00:00", "state": "intent"}
    (folder / "9.json").write_text(json.dumps(left), encoding="utf-8")
    next_start.show(project.root, make_config(), InMemoryTracker())
    text = next_ticket.record_path(project.root).read_text(encoding="utf-8")
    assert f"#9 maybe launched at {left['at']} (process {DEAD}); it did not register" in text
    assert next_ticket.reservations(project.root) == []


def test_c23_next_start_a_ticket_that_ends_before_registering_is_said(project: Project) -> None:
    tracker = InMemoryTracker()
    queued(tracker, 7, "", at(0), "ariane")
    next_start.show(project.root, make_config(), tracker)
    _, outcome = next_start.start(
        project.root, make_config(), tracker, lambda n, handed: Child(51, 1)
    )
    out = next_ticket.output_path(project.root, 7)
    assert outcome.line == (
        "Started #7 in the background (process 51), but it ended (exit code 1) before it"
        f" registered as running. Next: read its output {out}, then run ariane next."
    )
    assert next_ticket.reservations(project.root) == []


def test_c23_next_start_a_failed_relabel_starts_nothing_and_can_be_confirmed_again(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracker = InMemoryTracker()
    queued(tracker, 7, "", at(0), "ariane")
    next_start.show(project.root, make_config(), tracker)
    tracker.refuse_labels = True
    launched: list[int] = []
    launch = registering(project, monkeypatch, launched)
    _, outcome = next_start.start(project.root, make_config(), tracker, launch)
    assert outcome.line.startswith("Did not start #7: the relabel (`ariane`) failed")
    assert launched == []
    assert next_ticket.reservations(project.root) == []
    tracker.refuse_labels = False
    assert next_start.start(project.root, make_config(), tracker, launch)[1].exit_code == 0
    assert launched == [7]


def test_c23_next_spawn_runs_ariane_start_detached_with_its_output_kept(project: Project) -> None:
    child = next_start.spawn(project.root, 31, {}, environ())
    if sys.platform != "win32":
        assert os.getsid(child.pid) == child.pid  # its own session: detached from the terminal
    out = next_ticket.output_path(project.root, 31)
    assert out == project.root.parent / "proj.ariane/logs/31.out"
    deadline = time.monotonic() + 60
    while child.poll() is None and time.monotonic() < deadline:
        time.sleep(0.1)
    text = out.read_text(encoding="utf-8", errors="replace")
    assert "Refused configuration: ariane.toml: file not found" in text
