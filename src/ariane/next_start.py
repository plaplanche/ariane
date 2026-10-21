"""`ariane next` and `ariane next --start` under the handoff lock: a confirmed proposal is
reserved before any external write, consumed by its start, and held until the ticket it
launches registers as running (C11, C23, ADR 0059)."""

from __future__ import annotations

import contextlib
import dataclasses
import getpass
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from ariane import flow, logs, runs, ticket
from ariane.config import Config
from ariane.next_ticket import (
    START,
    Proposal,
    Reservation,
    last_printed,
    output_path,
    propose,
    record,
    reservations,
    reservations_folder,
)
from ariane.tracker import QueuedIssue, Tracker, TrackerError

REGISTER_SECONDS = 60.0  # how long `--start` waits for its ticket to register as running
POLL_SECONDS = 0.2
CHANGED = "start refused, the issue changed"  # not a printed proposal: `--start` needs a new one


class Launched(Protocol):
    """A ticket started in the background: its process, and its exit code once it ended."""

    pid: int

    def poll(self) -> int | None: ...


# Starts `ariane start <n>` in the background, with the variables of its handoff set.
Launch = Callable[[int, Mapping[str, str]], Launched]


def handoff(root: Path) -> contextlib.AbstractContextManager[None]:
    """The handoff lock: one `ariane next` at a time, and no registration of a run while it
    holds it (`runs.registered`), except the ticket it launches."""
    return runs.locked(reservations_folder(root))


def show(root: Path, config: Config, tracker: Tracker, slot_folder: Path | None = None) -> Proposal:
    """`ariane next`: propose, and record the proposal."""
    with handoff(root):
        reconcile(root)
        proposal = propose(root, config, tracker, slot_folder)
        record(root, "proposal", proposal)
    logs.emit("next.proposed", f"proposal: {proposal.summary()}")
    return proposal


def reconcile(root: Path) -> None:
    """Remove the reservations that no longer hold (their ticket registered, or their process
    is gone), recording in `next.md` the start of those whose `start` entry is missing: a
    `--start` that crashed or could not write it."""
    where = runs.folder(root)
    running = runs.running(where)
    for left in [r for r in reservations(root) if not r.pending(root)]:
        if left.state != "recorded":
            seen = "it runs" if left.number in running else "it did not register as running"
            if left.number not in running and runs.registered_since(where, left.number, left.at):
                seen = "it registered as running and ended"
            what = "launched" if left.state == "launched" else "maybe launched"
            proposal = Proposal(tuple(sorted(running)), (), (), None, "")
            record(
                root,
                "start reconciled",
                proposal,
                [f"Started: #{left.number} {what} at {left.at} (process {left.pid}); {seen}"],
            )
            logs.emit("next.reconciled", f"#{left.number}: {what}, {seen}")
        left.path(root).unlink(missing_ok=True)


def start(
    root: Path,
    config: Config,
    tracker: Tracker,
    launch: Launch,
    slot_folder: Path | None = None,
) -> tuple[Proposal, flow.Outcome]:
    """`ariane next --start`: under the handoff lock, propose again; if the proposal is the
    one last printed, reserve it and record the intent (the proposal is consumed), put the
    issue's ready label back (remove, then add, as a maintainer would), `launch` it, and
    wait for it to register before recording the start."""
    with handoff(root):
        printed = last_printed(root)
        reconcile(root)
        proposal = propose(root, config, tracker, slot_folder)
        if printed is None or printed != proposal.summary():
            was = printed or "none printed since the last start"
            record(root, "start refused", proposal, [f"Printed before: {was}"])
            return proposal, flow.Outcome(
                flow.EXIT_STOPPED,
                f"Did not start: the proposal changed since it was printed (was {was}, now"
                f" {proposal.summary()}). Next: read it above, then run {START} to confirm it.",
            )
        if proposal.number is None:
            record(root, "start refused", proposal)
            return proposal, flow.Outcome(flow.EXIT_STOPPED, proposal.last_line())
        return proposal, _launch(root, config, tracker, launch, proposal, proposal.number)


def _launch(
    root: Path,
    config: Config,
    tracker: Tracker,
    launch: Launch,
    proposal: Proposal,
    number: int,
) -> flow.Outcome:
    confirmed = f"Confirmed by: {_user()} ({START})"
    intent = Reservation(number, os.getpid(), runs.now(), "intent")
    _write(root, intent)  # an error here has written nothing outside: the caller did nothing
    try:
        record(root, "start intent", proposal, [confirmed])
    except OSError:
        intent.path(root).unlink(missing_ok=True)
        raise
    label = config.tracker.ready_label
    analysed = proposal.analysed
    handed = {
        runs.HANDOFF_ENV: str(number),
        runs.CLAIM_ENV: intent.at,
        runs.ISSUE_ENV: runs.digest(analysed.issue.body if analysed else ""),
    }
    try:
        tracker.remove_label(number, label)
        tracker.add_labels(number, [label])
        changed = _changed(tracker, analysed, label)
        if changed:
            tracker.remove_label(number, label)  # the fresh label blesses no unanalysed edit
            record(root, CHANGED, proposal, [f"The issue changed: {changed}"])  # consumed
            intent.path(root).unlink(missing_ok=True)
            return flow.Outcome(
                flow.EXIT_STOPPED,
                f"Did not start #{number}: {changed} since ariane next analysed it; its"
                f" `{label}` label was removed. Next: read the issue, then run ariane next.",
            )
        child = launch(number, handed)
    except (TrackerError, OSError) as exc:
        what = "launch" if isinstance(exc, OSError) else f"relabel (`{label}`)"
        record(root, "start refused", proposal, [f"The {what} failed: {exc}"])
        intent.path(root).unlink(missing_ok=True)
        return flow.Outcome(
            flow.EXIT_STOPPED,
            f"Did not start #{number}: the {what} failed ({exc}). Next: fix it, then run {START}.",
        )
    started = f"Started #{number} in the background (process {child.pid})"
    problems = []
    launched = dataclasses.replace(intent, pid=child.pid, state="launched")
    try:
        _write(root, launched)
    except OSError as exc:
        problems.append(f"its reservation could not be written ({exc})")
    registered, code = _registered(root, number, intent.at, child)
    status = "registered as running" if registered else "not registered yet"
    if code is not None and not registered:
        status = f"ended (exit code {code}) before it registered as running"
    try:
        record(
            root,
            "start",
            proposal,
            [confirmed, f"Started: #{number}, process {child.pid}; {status}"],
        )
        if registered or code is not None:
            intent.path(root).unlink(missing_ok=True)
        else:  # it may still register: the reservation holds the proposals back meanwhile
            _write(root, dataclasses.replace(launched, state="recorded"))
    except OSError as exc:
        problems.append(f"next.md could not record it ({exc})")
    logs.emit("next.started", f"#{number} started in the background, process {child.pid}; {status}")
    out = output_path(root, number)
    if problems:
        return flow.Outcome(
            flow.EXIT_STOPPED,
            f"{started}, but {'; '.join(problems)}. Next: follow it with ariane status {number};"
            " the next ariane next records the start.",
        )
    if code is not None and not registered:
        return flow.Outcome(
            flow.EXIT_STOPPED,
            f"{started}, but it {status}. Next: read its output {out}, then run ariane next.",
        )
    journal = ticket.folder_path(flow.worktree_path(root, number), number) / ticket.JOURNAL
    waiting = "" if registered else f", not registered as running after {REGISTER_SECONDS:g} s"
    return flow.Outcome(
        flow.EXIT_OK,
        f"{started}{waiting}; its journal will be {journal}, its output {out}."
        f" Next: follow it with ariane status {number}.",
    )


def _changed(tracker: Tracker, analysed: QueuedIssue | None, label: str) -> str:
    """What changed in the issue since `analysed`, read again after the relabel (its body, its
    labels other than `label`), or "": an edit made before the fresh label is seen here, one
    made after it is refused by the issue gate (ADR 0059)."""
    if analysed is None:
        return "it was not analysed"
    now = tracker.peek_issue(analysed.issue.number)
    if now.issue.body != analysed.issue.body:
        return "its body changed"
    if set(now.labels) - {label} != set(analysed.labels) - {label}:
        return "its labels changed"
    return ""


def _registered(root: Path, number: int, since: str, child: Launched) -> tuple[bool, int | None]:
    """Wait until ticket `number` registered as running since `since` (live, or already
    ended), its process ended, or `REGISTER_SECONDS` passed: whether it registered, and the
    process's exit code if it ended."""
    deadline = time.monotonic() + REGISTER_SECONDS
    where = runs.folder(root)
    while True:
        code = child.poll()
        with contextlib.suppress(OSError):
            if runs.registered_since(where, number, since):
                return True, code
        if code is not None or time.monotonic() >= deadline:
            return False, code
        time.sleep(POLL_SECONDS)


def _write(root: Path, reservation: Reservation) -> None:
    """Write `reservation` whole: a reader never finds half of it."""
    path = reservation.path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    draft = path.with_suffix(f".{os.getpid()}.tmp")
    draft.write_text(json.dumps(dataclasses.asdict(reservation)), encoding="utf-8")
    os.replace(draft, path)


def _user() -> str:
    try:
        return getpass.getuser()
    except (OSError, KeyError, ImportError):
        return "unknown"


def spawn(
    root: Path, number: int, handed: Mapping[str, str], environ: Mapping[str, str]
) -> subprocess.Popen[bytes]:
    """Run `ariane start <number>` detached from the terminal (its own session or process
    group, no input), its output appended to `output_path`, with the variables `handed` of its
    handoff (`runs.HANDOFF_ENV` and the others) so that it registers inside the handoff lock,
    under its reservation, and runs only the issue `ariane next` analysed."""
    out = output_path(root, number)
    out.parent.mkdir(parents=True, exist_ok=True)
    argv = [sys.executable, "-m", "ariane", "start", str(number)]
    env = {**environ, **handed}
    with out.open("ab") as file:
        if sys.platform == "win32":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            return subprocess.Popen(
                argv,
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=file,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
        return subprocess.Popen(
            argv,
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
