"""`ariane next`: propose the next ticket of the queue that can start safely next to the
running ones, and start it on the owner's confirmation (C11, C22, C23, ADR 0059)."""

from __future__ import annotations

import contextlib
import getpass
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ariane import flow, git, logs, process, runs, slots, ticket
from ariane.config import Config, NextConfig
from ariane.globs import glob_regex, is_glob
from ariane.metrics import METRICS
from ariane.runtime import StopReason
from ariane.stop import Stop
from ariane.tracker import QueuedIssue, Tracker, TrackerError

RECORD = "next.md"
MODULE_DOCS = "docs/architecture/modules/"
START = "ariane next --start"
PROPOSAL = "Proposal: "  # the line of a `next.md` entry that `--start` compares
# `Needs #N`, `Needs #N and #M`, `Needs #N, #M`: at the start of a line, a list marker allowed.
_NEEDS = re.compile(r"^\s*(?:[-*]\s+)?Needs\s+(#\d+(?:\s*(?:,|and|&)\s*#\d+)*)", re.MULTILINE)
_NUMBER = re.compile(r"#(\d+)")
# Before and after a word of the body (quotes, brackets, punctuation), never part of a path.
_EDGES = re.compile(r"^[`'\"(\[{]+|[`'\"()\[\]{},;:!?.]+$")
_PATH = re.compile(r"[\w.*/-]+")
_FILE_NAME = re.compile(r"[\w-]+\.[A-Za-z]\w*")


@dataclass(frozen=True)
class Candidate:
    """An issue of the queue and why it cannot start now; no reason: it can."""

    number: int
    reasons: tuple[str, ...]

    def line(self) -> str:
        why = "; ".join(self.reasons) if self.reasons else "can start"
        return f"- #{self.number}: {why}"


@dataclass(frozen=True)
class Proposal:
    """What `ariane next` found: the running tickets, the issues looked at, the reasons that
    hold for all of them (no run slot, a quota) and the proposed issue, if any."""

    running: tuple[int, ...]
    candidates: tuple[Candidate, ...]
    blockers: tuple[str, ...]
    number: int | None
    next_action: str  # when nothing is proposed

    def summary(self) -> str:
        """The proposal in one phrase, compared by `--start` with the one last printed."""
        if self.number is None:
            return "nothing"
        others = ", ".join(f"#{m}" for m in self.running)
        return f"#{self.number} ({f'no shared file with {others}' if others else 'nothing runs'})"

    def lines(self) -> list[str]:
        shown = ", ".join(f"#{m}" for m in self.running) or "none"
        return [f"Running: {shown}.", *(c.line() for c in self.candidates)]

    def last_line(self) -> str:
        if self.number is not None:
            return f"Next: {self.summary()}. Start it with {START}."
        why = "; ".join(self.blockers) or (
            "no issue of the queue can start" if self.candidates else "the queue is empty"
        )
        return f"Nothing to start: {why}. Next: {self.next_action}."


def needs(body: str) -> list[int]:
    """The issues a `Needs #N` line of `body` names, in order, each once."""
    found: list[int] = []
    for match in _NEEDS.finditer(body):
        found += [int(n) for n in _NUMBER.findall(match.group(1)) if int(n) not in found]
    return found


def expected_paths(
    body: str, labels: Sequence[str], root: Path, settings: NextConfig
) -> tuple[str, ...]:
    """The paths, and globs, an issue is expected to touch (ADR 0059): the file paths its body
    names (a folder `a/b/` as `a/b/**`; a bare file name only if it is at the root of `root` or
    a module file), the source files and tests of each `docs/architecture/modules/<m>.md`, and
    the `[next] paths` globs of its labels."""
    found: list[str] = []
    for word in body.split():
        path = _path(_EDGES.sub("", word).removeprefix("./"), root)
        if path and path not in found:
            found.append(path)
    for path in list(found):
        if path.startswith(MODULE_DOCS) and path.endswith(".md") and not is_glob(path):
            found += [p for p in _module_files(root, path[len(MODULE_DOCS) : -3]) if p not in found]
    for label, globs in settings.paths:
        if label in labels:
            found += [g for g in globs if g not in found]
    return tuple(found)


def _path(word: str, root: Path) -> str:
    if "://" in word or not _PATH.fullmatch(word) or word.startswith("/") or ".." in word:
        return ""
    if "/" not in word:
        if not _FILE_NAME.fullmatch(word):
            return ""
        if (root / word).is_file():
            return word
        return MODULE_DOCS + word if (root / MODULE_DOCS / word).is_file() else ""
    if word.endswith("/"):
        return word + "**"
    last = word.rsplit("/", 1)[1]
    return word if "." in last or is_glob(last) else ""  # `owner/name`, `ariane/12`: no file


def _module_files(root: Path, module: str) -> list[str]:
    """`src/<package>/<module>.py` and the tests whose name holds the module's name."""
    parts = module.split("_")
    found = sorted(p.relative_to(root).as_posix() for p in root.glob(f"src/*/{module}.py"))
    for test in sorted((root / "tests").rglob("test_*.py")):
        words = test.stem.split("_")
        if any(words[i : i + len(parts)] == parts for i in range(len(words))):
            found.append(test.relative_to(root).as_posix())
    return found


def shared(first: Sequence[str], second: Sequence[str]) -> list[str]:
    """The paths both lists name: the same path or glob, or a path one's glob matches."""
    found: set[str] = set()
    for a in first:
        for b in second:
            if a == b:
                found.add(a)
            elif is_glob(a) and not is_glob(b) and glob_regex(a).fullmatch(b):
                found.add(b)
            elif is_glob(b) and not is_glob(a) and glob_regex(b).fullmatch(a):
                found.add(a)
    return sorted(found)


def propose(
    root: Path, config: Config, tracker: Tracker, slot_folder: Path | None = None
) -> Proposal:
    """Read the queue, the running tickets, the run slots and the last run, then propose the
    first issue of the queue that can start. Starts nothing."""
    settings = config.next
    queue = tracker.queue(config.tracker.next_label)
    by_number = {q.issue.number: q for q in queue}
    running = runs.running(runs.folder(root))
    files = {m: _running_files(root, config, run, by_number.get(m)) for m, run in running.items()}
    blockers, action = _blockers(root, slot_folder)
    candidates = []
    for queued in [q for q in queue if q.issue.number not in running][: settings.look_ahead]:
        reasons = _reasons(root, tracker, settings, queued, files)
        candidates.append(Candidate(queued.issue.number, (*reasons, *blockers)))
    number = next((c.number for c in candidates if not c.reasons), None)
    if not action:
        action = (
            "wait for a running ticket to end or a needed issue to close, then run ariane next"
            if candidates
            else f"label an issue `{config.tracker.next_label}`, then run ariane next"
        )
    return Proposal(tuple(sorted(running)), tuple(candidates), blockers, number, action)


def _reasons(
    root: Path,
    tracker: Tracker,
    settings: NextConfig,
    queued: QueuedIssue,
    files: Mapping[int, Sequence[str]],
) -> list[str]:
    number = queued.issue.number
    branch = flow.branch_name(number)
    if flow.worktree_path(root, number).exists() or git.local_branch_exists(root, branch):
        return [f"already started (branch {branch}); see ariane status {number}"]
    reasons = []
    for other in needs(queued.issue.body):
        try:
            done = tracker.closed_as_completed(other)
        except TrackerError as exc:
            reasons.append(f"waits on #{other} (unreadable: {exc})")
            continue
        if not done:
            reasons.append(f"waits on #{other}")
    expected = expected_paths(queued.issue.body, queued.labels, root, settings)
    for m in sorted(files):
        common = shared(expected, files[m])
        if common:
            reasons.append(f"shares {', '.join(common)} with running #{m}")
    return reasons


def _running_files(
    root: Path, config: Config, run: runs.Run, queued: QueuedIssue | None
) -> list[str]:
    """A running ticket's files: its branch's changes since its start base (its tree's
    uncommitted work included), plus its own expected files, from the queue or its brief."""
    worktree = flow.worktree_path(root, run.number)
    found: list[str] = []
    with contextlib.suppress(git.GitError, process.CommandNotFoundError):
        base = git.merge_base(root, f"{flow.REMOTE}/{config.base_branch}", run.branch)
        if worktree.is_dir():
            found = git.changed_paths(worktree, base)
        else:
            found = [p for p in git.changed_between(root, base, run.branch) if p]
    body, labels = (queued.issue.body, queued.labels) if queued is not None else ("", ())
    if queued is None:
        with contextlib.suppress(OSError):
            body = (ticket.folder_path(worktree, run.number) / ticket.BRIEF).read_text("utf-8")
    expected = expected_paths(body, labels, root, config.next)
    return found + [p for p in expected if p not in found]


def _blockers(root: Path, slot_folder: Path | None) -> tuple[tuple[str, ...], str]:
    """What stops every issue from starting now, and the next action for it."""
    found, action = [], ""
    try:
        with slots.held(slot_folder):
            pass
    except Stop as exc:
        found.append(f"no free run slot ({exc.reason})")
        action = "wait for a run to end, then run ariane next"
    quota = last_quota_stop(root)
    if quota is not None:
        found.append(f"the last run, #{quota}, stopped on a quota of its agent")
        action = action or f"once the quota resets, run ariane start {quota} --restart"
    return tuple(found), action


def last_quota_stop(root: Path) -> int | None:
    """The ticket of the last run that ended, if it stopped on a quota: its outcome is
    `stopped` and its last agent session ended with the stop reason `quota` (ADR 0059)."""
    ended = []
    with contextlib.suppress(OSError):
        for line in (runs.folder(root) / runs.ENDED).read_text(encoding="utf-8").splitlines():
            with contextlib.suppress(ValueError, KeyError, TypeError):
                entry = json.loads(line)
                ended.append((str(entry["ended"]), int(entry["number"])))
    if not ended:
        return None
    number = max(ended)[1]
    path = ticket.folder_path(flow.worktree_path(root, number), number) / METRICS
    try:
        metrics = json.loads(path.read_text(encoding="utf-8"))
        sessions = metrics.get("sessions") or []
        quota = sessions[-1].get("stop_reason") == StopReason.QUOTA if sessions else False
    except (OSError, ValueError, AttributeError, TypeError):
        return None
    return number if metrics.get("outcome") == "stopped" and quota else None


def record_path(root: Path) -> Path:
    """`<repo>.ariane/next.md`, next to the tickets' working trees."""
    return root.parent / f"{root.name}.ariane" / RECORD


def output_path(root: Path, number: int) -> Path:
    """`<repo>.ariane/logs/<n>.out`: the output of a ticket started in the background, beside
    its technical log."""
    return logs.log_path(root, number).with_suffix(".out")


def record(root: Path, title: str, proposal: Proposal, extra: Sequence[str] = ()) -> None:
    """Append one entry to `next.md`: its time and title, the running tickets, the reason of
    every issue looked at, the proposal and the `extra` lines."""
    path = record_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    items = [line.removeprefix("- ") for line in proposal.lines()]
    items += [*extra, f"{PROPOSAL}{proposal.summary()}"]
    lines = [f"## {ticket.now()}: {title}", "", *(f"- {item}" for item in items)]
    head = "" if path.is_file() else "# Proposals of ariane next\n\n"
    with path.open("a", encoding="utf-8") as file:
        file.write(head + "\n".join(lines) + "\n\n")


def last_printed(root: Path) -> str | None:
    """The proposal of the last entry of `next.md`, None without one."""
    try:
        text = record_path(root).read_text(encoding="utf-8")
    except OSError:
        return None
    found = [line for line in text.splitlines() if line.startswith("- " + PROPOSAL)]
    return found[-1].removeprefix("- " + PROPOSAL) if found else None


def show(root: Path, config: Config, tracker: Tracker, slot_folder: Path | None = None) -> Proposal:
    """`ariane next`: propose, and record the proposal."""
    proposal = propose(root, config, tracker, slot_folder)
    record(root, "proposal", proposal)
    logs.emit("next.proposed", f"proposal: {proposal.summary()}")
    return proposal


Launch = Callable[[int], int]  # starts `ariane start <n>` in the background: its process id


def start(
    root: Path,
    config: Config,
    tracker: Tracker,
    launch: Launch,
    slot_folder: Path | None = None,
) -> tuple[Proposal, flow.Outcome]:
    """`ariane next --start`: propose again; if the proposal is the one last printed, put the
    issue's ready label back (remove, then add, as a maintainer would) and `launch` it."""
    printed = last_printed(root)
    proposal = propose(root, config, tracker, slot_folder)
    if printed is None or printed != proposal.summary():
        was = printed or "none printed"
        record(root, "start refused", proposal, [f"Printed before: {was}"])
        return proposal, flow.Outcome(
            flow.EXIT_STOPPED,
            f"Did not start: the proposal changed since it was printed (was {was}, now"
            f" {proposal.summary()}). Next: read it above, then run {START} to confirm it.",
        )
    number = proposal.number
    if number is None:
        record(root, "start refused", proposal)
        return proposal, flow.Outcome(flow.EXIT_STOPPED, proposal.last_line())
    label = config.tracker.ready_label
    try:
        tracker.remove_label(number, label)
        tracker.add_labels(number, [label])
    except TrackerError as exc:
        record(root, "start refused", proposal, [f"Relabel failed: {exc}"])
        return proposal, flow.Outcome(
            flow.EXIT_STOPPED,
            f"Did not start #{number}: the label `{label}` could not be put back ({exc})."
            f" Next: check the token can label issues, then run {START}.",
        )
    pid = launch(number)
    journal = ticket.folder_path(flow.worktree_path(root, number), number) / ticket.JOURNAL
    confirmed = f"Confirmed by: {_user()} ({START})"
    record(root, "start", proposal, [confirmed, f"Started: #{number}, process {pid}"])
    logs.emit("next.started", f"#{number} started in the background, process {pid}")
    return proposal, flow.Outcome(
        flow.EXIT_OK,
        f"Started #{number} in the background (process {pid}); its journal will be {journal},"
        f" its output {output_path(root, number)}. Next: follow it with ariane status {number}.",
    )


def _user() -> str:
    try:
        return getpass.getuser()
    except (OSError, KeyError, ImportError):
        return "unknown"


def spawn(root: Path, number: int, environ: Mapping[str, str]) -> int:
    """Run `ariane start <number>` detached from the terminal (its own session or process
    group, no input), its output appended to `output_path`; return its process id."""
    out = output_path(root, number)
    out.parent.mkdir(parents=True, exist_ok=True)
    argv = [sys.executable, "-m", "ariane", "start", str(number)]
    with out.open("ab") as file:
        if sys.platform == "win32":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            child = subprocess.Popen(
                argv,
                cwd=root,
                env=dict(environ),
                stdin=subprocess.DEVNULL,
                stdout=file,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
        else:
            child = subprocess.Popen(
                argv,
                cwd=root,
                env=dict(environ),
                stdin=subprocess.DEVNULL,
                stdout=file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    return child.pid
