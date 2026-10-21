"""`ariane next --start`'s handoff binds the ticket it launches to what `ariane next` analysed:
the issue's revision (an edit before the relabel is refused, by `--start` and by the ticket),
and its reservation (a ticket whose reservation was dropped does not register) (C11, C23,
ADR 0060)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest
from test_c23_next import at, queued
from test_c23_next_start import Child, entries, handing

from ariane import flow, next_start, next_ticket, runs
from ariane.stop import Stop
from ariane.tracker import InMemoryTracker, TrackerError

from conftest import FakeRuntime, Project, make_config
from test_flow import environ

DEAD = 2**30  # a process id no process has


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(next_start, "REGISTER_SECONDS", 0.5)
    monkeypatch.setattr(next_start, "POLL_SECONDS", 0.01)


class Editing(InMemoryTracker):
    """A tracker on which someone edits issue 7 once `--start` analysed it, before its relabel."""

    edit: str | None = None

    def remove_label(self, number: int, label: str) -> None:
        if self.edit is not None:
            self.add_issue(number, f"Issue {number}", self.edit)
            self.edit = None
        super().remove_label(number, label)


@pytest.mark.parametrize("edit", ["Edit `app.txt`.", "Needs #3"])
def test_c23_next_start_an_edit_between_the_analysis_and_the_relabel_starts_nothing(
    project: Project, edit: str
) -> None:
    tracker = Editing()
    queued(tracker, 7, "Edit `b.txt`.", at(0), "ariane")
    next_start.show(project.root, make_config(), tracker)
    tracker.edit = edit
    launched: list[int] = []

    def launch(number: int, handed: Mapping[str, str]) -> Child:
        launched.append(number)
        return Child(4007)

    _, outcome = next_start.start(project.root, make_config(), tracker, launch)
    assert outcome.line == (
        "Did not start #7: its body changed since ariane next analysed it; its `ariane` label"
        " was removed. Next: read the issue, then run ariane next."
    )
    assert launched == []
    assert "ariane" not in tracker.labels[7]  # the fresh label blesses nothing unanalysed
    assert entries(project)[-1] == next_start.CHANGED
    assert next_ticket.reservations(project.root) == []
    _, again = next_start.start(project.root, make_config(), tracker, launch)
    assert "was none printed since the last start" in again.line  # analyse it again first
    assert launched == []


class Relabels(InMemoryTracker):
    """A tracker that counts the relabels of `--start`."""

    removed: int = 0

    def remove_label(self, number: int, label: str) -> None:
        self.removed += 1
        super().remove_label(number, label)


def test_c23_next_start_an_edit_before_the_relabel_touches_no_label(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An edit between `--start`'s analysis and its relabel is seen before the relabel: no fresh
    label exists for the edited revision, so a start run by hand meanwhile cannot pass the gate."""
    tracker = Relabels()
    queued(tracker, 7, "Edit `b.txt`.", at(0), "ariane")
    next_start.show(project.root, make_config(), tracker)
    real = next_start.propose  # type: ignore[attr-defined]  # imported there, patched there

    def then_edited(*args: Any, **kwargs: Any) -> Any:
        proposal = real(*args, **kwargs)
        tracker.add_issue(7, "Issue 7", "Edited after the analysis.")
        return proposal

    monkeypatch.setattr(next_start, "propose", then_edited)
    launched: list[int] = []

    def launch(number: int, handed: Mapping[str, str]) -> Child:
        launched.append(number)
        return Child(4007)

    _, outcome = next_start.start(project.root, make_config(), tracker, launch)
    assert outcome.line == (
        "Did not start #7: its body changed since ariane next analysed it. Next: read the issue,"
        " then run ariane next."
    )
    assert tracker.removed == 0 and launched == []
    assert entries(project)[-1] == next_start.CHANGED


def test_c23_next_start_the_launched_ticket_runs_only_the_analysed_issue(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracker = InMemoryTracker()
    tracker.add_issue(7, "Issue 7", "Edited after the analysis.")
    monkeypatch.setenv(runs.HANDOFF_ENV, "7")
    monkeypatch.setenv(runs.CLAIM_ENV, runs.now())
    monkeypatch.setenv(runs.ISSUE_ENV, runs.digest("The analysed body."))
    outcome = flow.start(
        7,
        repo_root=project.root,
        config=make_config(),
        tracker=tracker,
        runtime=FakeRuntime(),
        environ=environ(),
    )
    assert outcome.exit_code == 2
    assert outcome.line == (
        "Did not start #7: issue #7 changed since ariane next analysed it. Next: read the issue,"
        " label it again if it is right, then run ariane next."
    )
    assert runs.registered_since(runs.folder(project.root), 7, "") is False


def reserve(project: Project, at: str, pid: int = DEAD) -> None:
    folder = next_ticket.reservations_folder(project.root)
    folder.mkdir(parents=True, exist_ok=True)
    left = {"number": 9, "pid": pid, "at": at, "state": "intent"}
    (folder / "9.json").write_text(json.dumps(left), encoding="utf-8")


def test_c23_next_start_a_ticket_whose_starter_died_before_its_reservation_was_replaced(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The starter wrote its reservation, launched #9, then died before naming the child in it.
    claim = "2026-10-21T10:00:00.000000+00:00"
    reserve(project, claim)
    handing(monkeypatch, {runs.HANDOFF_ENV: "9", runs.CLAIM_ENV: claim, runs.ISSUE_ENV: ""})
    tracker = InMemoryTracker()
    queued(tracker, 10, "", at(0), "ariane")
    assert next_start.show(project.root, make_config(), tracker).number == 10  # grace is over
    assert next_ticket.reservations(project.root) == []
    where = runs.folder(project.root)
    with pytest.raises(Stop) as stopped, runs.registered(where, 9, "ariane/9"):
        pass  # the delayed child registers after the grace period: refused
    assert stopped.value.reason == (
        "the reservation of ariane next --start for #9 was dropped before it registered as running"
    )
    assert runs.running(where) == {}


def test_c23_next_start_a_launched_ticket_registers_only_under_its_own_reservation(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    claim = runs.now()
    reserve(project, claim, pid=0)
    where = runs.folder(project.root)
    handing(
        monkeypatch, {runs.HANDOFF_ENV: "9", runs.CLAIM_ENV: "an older claim", runs.ISSUE_ENV: ""}
    )
    with pytest.raises(Stop), runs.registered(where, 9, "ariane/9"):
        pass
    monkeypatch.setenv(runs.CLAIM_ENV, claim)
    with runs.registered(where, 9, "ariane/9"):
        assert list(runs.running(where)) == [9]


class FailsAfterRelabel(InMemoryTracker):
    """A tracker whose issue read fails once the ready label was given again."""

    relabelled: bool = False

    def add_labels(self, number: int, labels: list[str]) -> None:
        super().add_labels(number, labels)
        self.relabelled = True

    def peek_issue(self, number: int) -> Any:
        if self.relabelled:
            raise TrackerError("the tracker is unreachable")
        return super().peek_issue(number)


def test_c23_next_start_a_failed_read_after_the_relabel_leaves_no_fresh_label(
    project: Project,
) -> None:
    tracker = FailsAfterRelabel()
    queued(tracker, 7, "Edit `b.txt`.", at(0), "ariane")
    next_start.show(project.root, make_config(), tracker)
    launched: list[int] = []

    def launch(number: int, handed: Mapping[str, str]) -> Child:
        launched.append(number)
        return Child(4007)

    _, outcome = next_start.start(project.root, make_config(), tracker, launch)
    assert outcome.line.startswith("Did not start #7: the relabel (`ariane`) failed")
    assert launched == [] and "ariane" not in tracker.labels[7]  # nothing blessed, nothing run
