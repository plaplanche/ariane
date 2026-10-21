"""`ariane next`: propose the next ticket of the queue that can start safely next to the
running ones, and start it on the owner's confirmation (C11, C22, C23, ADR 0060)."""

from __future__ import annotations

import contextlib
import json
import posixpath
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ariane import flow, git, logs, process, runs, slots, ticket
from ariane.config import Config, NextConfig
from ariane.globs import glob_regex, is_glob, overlap
from ariane.metrics import METRICS
from ariane.runtime import StopReason
from ariane.stop import Stop
from ariane.tracker import QueuedIssue, Tracker, TrackerError

RECORD = "next.md"
MODULE_DOCS = "docs/architecture/modules/"
START = "ariane next --start"
PROPOSAL = "Proposal: "  # the line of a `next.md` entry that `--start` compares
PRINTED = ("proposal", "start refused")  # the entries whose proposal `--start` may confirm
GRACE = timedelta(seconds=60)  # a reservation whose process is gone still holds this long
SHOWN = 3  # the files named for two overlapping globs, beyond which they are counted
# `Needs #N`, `Needs #N and #M`, `Needs #N, #M`: at the start of a line, a list marker allowed.
_NEEDS = re.compile(r"^\s*(?:[-*]\s+)?Needs\s+(#\d+(?:\s*(?:,|and|&)\s*#\d+)*)", re.MULTILINE)
_NUMBER = re.compile(r"#(\d+)")
# What separates the words of the body (spaces, quotes, brackets: `[a.py](a.py)` names a.py).
_WORDS = re.compile(r"[\s`'\"()\[\]{},;]+")
_TRAILING = re.compile(r"[:!?.]+$")  # the punctuation after a word, never part of a path
_REFERENCE = re.compile(r"(?::\d+)+$|#L\d+(?:-L?\d+)?$")  # `a.py:65`, `a.py#L3-L9`: a.py
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
    analysed: QueuedIssue | None = field(default=None, compare=False)  # the proposed issue

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
    """The paths, and globs, an issue is expected to touch (ADR 0060): the file paths its body
    names (a folder `a/b/` as `a/b/**`; a bare file name only if it is at the root of `root` or
    a module file), the source files and tests of each `docs/architecture/modules/<m>.md`, and
    the `[next] paths` globs of its labels."""
    found: list[str] = []
    for word in _WORDS.split(body):
        path = _path(_normal(_TRAILING.sub("", _REFERENCE.sub("", _TRAILING.sub("", word)))), root)
        if path and path not in found:
            found.append(path)
    for path in list(found):
        if path.startswith(MODULE_DOCS) and path.endswith(".md") and not is_glob(path):
            found += [p for p in _module_files(root, path[len(MODULE_DOCS) : -3]) if p not in found]
    for label, globs in settings.paths:
        if label in labels:
            found += [g for g in globs if g not in found]
    return tuple(found)


def _normal(word: str) -> str:
    """`word` as git names the path (`a/./b.py`, `./a//b.py`: `a/b.py`; a folder keeps its
    `/`), or "" for no relative path inside the repository (`/a`, `../a`, a URL)."""
    if not word or "://" in word or not _PATH.fullmatch(word) or word.startswith("/"):
        return ""
    path = posixpath.normpath(word)
    if path == "." or path == ".." or path.startswith("../"):
        return ""
    return path + "/" if word.endswith("/") else path


def _path(word: str, root: Path) -> str:
    if not word:
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
    """`src/<package>/<module>.py` and the tests whose name holds the module's name; a module
    not created yet is the glob `src/*/<module>.py`, so a ticket about to add it still shares
    it with another that names it."""
    parts = module.split("_")
    found = sorted(p.relative_to(root).as_posix() for p in root.glob(f"src/*/{module}.py"))
    found = found or [f"src/*/{module}.py"]
    for test in sorted((root / "tests").rglob("test_*.py")):
        words = test.stem.split("_")
        if any(words[i : i + len(parts)] == parts for i in range(len(words))):
            found.append(test.relative_to(root).as_posix())
    return found


def shared(first: Sequence[str], second: Sequence[str], known: Sequence[str] = ()) -> list[str]:
    """The paths both lists can name: the same path or glob, a path one's glob matches, or
    two globs some path matches (`overlap`), named by the `known` files both match (counted
    beyond `SHOWN`), else as the two globs."""
    found: set[str] = set()
    for a in first:
        for b in second:
            if a == b:
                found.add(a)
            elif not overlap(a, b):
                continue
            elif not (is_glob(a) and is_glob(b)):
                found.add(b if is_glob(a) else a)
            else:
                found.update(_both(a, b, known))
    return sorted(found)


def _both(a: str, b: str, known: Sequence[str]) -> list[str]:
    """How two overlapping globs are named: the `known` files both match, else the globs."""
    both = [p for p in known if glob_regex(a).fullmatch(p) and glob_regex(b).fullmatch(p)]
    if both and len(both) <= SHOWN:
        return both
    return [f"{min(a, b)} and {max(a, b)}" + (f" ({len(both)} files)" if both else "")]


def propose(
    root: Path, config: Config, tracker: Tracker, slot_folder: Path | None = None
) -> Proposal:
    """Read the queue, the running tickets, the run slots and the last run, then propose the
    first issue of the queue that can start. Starts nothing."""
    settings = config.next
    queue = tracker.queue(config.tracker.next_label)
    by_number = {q.issue.number: q for q in queue}
    running = runs.running(runs.folder(root))
    starting = {r.number: r for r in pending(root) if r.number not in running}
    files: dict[int, list[str]] = {}
    unknown: list[str] = []  # a running ticket whose files cannot be read holds every issue
    for m, run in sorted(running.items()):
        try:
            files[m] = _running_files(root, config, tracker, run, by_number.get(m))
        except _Unknown as exc:
            unknown.append(f"the files of running #{m} are not known ({exc})")
    unknown += [f"#{r.number} is starting (process {r.pid})" for r in starting.values()]
    blockers, action = _blockers(root, slot_folder)
    blockers = (*unknown, *blockers)
    if unknown:
        action = "wait for the running tickets to start their branches, then run ariane next"
    known = _known(root, files)
    candidates = []
    left = [q for q in queue if q.issue.number not in running and q.issue.number not in starting]
    for queued in left[: settings.look_ahead]:
        reasons = _reasons(root, tracker, settings, queued, files, known)
        candidates.append(Candidate(queued.issue.number, (*reasons, *blockers)))
    number = next((c.number for c in candidates if not c.reasons), None)
    if not action:
        action = (
            "wait for a running ticket to end or a needed issue to close, then run ariane next"
            if candidates
            else f"label an issue `{config.tracker.next_label}`, then run ariane next"
        )
    analysed = by_number[number] if number is not None else None
    return Proposal(tuple(sorted(running)), tuple(candidates), blockers, number, action, analysed)


def _reasons(
    root: Path,
    tracker: Tracker,
    settings: NextConfig,
    queued: QueuedIssue,
    files: Mapping[int, Sequence[str]],
    known: Sequence[str],
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
        common = shared(expected, files[m], known)
        if common:
            reasons.append(f"shares {', '.join(common)} with running #{m}")
    return reasons


class _Unknown(Exception):
    """A running ticket's files cannot be read: no issue is proposed next to it."""


def _running_files(
    root: Path, config: Config, tracker: Tracker, run: runs.Run, queued: QueuedIssue | None
) -> list[str]:
    """A running ticket's files: its branch's changes since its start base (its tree's
    uncommitted work included), plus its own expected files, from its issue's body and labels
    (the queue's entry, else read from the tracker). `_Unknown` when either cannot be read,
    for example while the run prepares its branch."""
    worktree = flow.worktree_path(root, run.number)
    try:
        if not git.local_branch_exists(root, run.branch):
            raise _Unknown(f"its branch {run.branch} does not exist yet")
        base = git.merge_base(root, f"{flow.REMOTE}/{config.base_branch}", run.branch)
        if worktree.is_dir():
            found = git.changed_paths(worktree, base)
        else:
            found = [p for p in git.changed_between(root, base, run.branch) if p]
    except (git.GitError, process.CommandNotFoundError) as exc:
        raise _Unknown(f"git cannot read its changes: {exc}") from None
    try:
        issue = queued if queued is not None else tracker.peek_issue(run.number)
    except TrackerError as exc:
        raise _Unknown(f"its issue cannot be read: {exc}") from None
    expected = expected_paths(issue.issue.body, issue.labels, root, config.next)
    return found + [p for p in expected if p not in found]


def _known(root: Path, files: Mapping[int, Sequence[str]]) -> list[str]:
    """The files that name two overlapping globs: the main checkout's files (tracked, or
    untracked and not ignored) and the running tickets' changes."""
    found: set[str] = set()
    with contextlib.suppress(git.GitError, process.CommandNotFoundError):
        listing = git.out(["ls-files", "--cached", "--others", "--exclude-standard"], root)
        found.update(p for p in listing.splitlines() if p)
    for paths in files.values():
        found.update(p for p in paths if not is_glob(p))
    return sorted(found)


@dataclass(frozen=True)
class Reservation:
    """A start of `ariane next --start` (ADR 0060), from before its first external write until
    its ticket registers: by `pid` (`next --start`'s own, then the launched ticket's), since
    `at`; `state` is `intent`, `launched` or `recorded` (its start entry is in `next.md`)."""

    number: int
    pid: int
    at: str
    state: str

    def path(self, root: Path) -> Path:
        return reservations_folder(root) / f"{self.number}.json"

    def pending(self, root: Path) -> bool:
        """Its ticket has not registered since `at` (live or ended) and may still: its process
        lives, or the reservation is recent."""
        if runs.registered_since(runs.folder(root), self.number, self.at):
            return False
        try:
            recent = datetime.now(UTC) - datetime.fromisoformat(self.at) < GRACE
        except (ValueError, TypeError):
            recent = False
        return runs.alive(self.pid) or recent


def reservations_folder(root: Path) -> Path:
    """`<repo>.ariane/next`, the folder of the handoff lock and of the reservations."""
    return runs.handoff_folder(runs.folder(root))


def reservations(root: Path) -> list[Reservation]:
    """Every reservation written, readable or not yet removed."""
    found = []
    with contextlib.suppress(OSError):
        for path in sorted(reservations_folder(root).glob("*.json")):
            with contextlib.suppress(OSError, ValueError, TypeError):
                found.append(Reservation(**json.loads(path.read_text(encoding="utf-8"))))
    return found


def pending(root: Path) -> list[Reservation]:
    """The reservations whose ticket has not registered as running and may still."""
    return [r for r in reservations(root) if r.pending(root)]


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
    `stopped` and its last agent session ended with the stop reason `quota` (ADR 0060)."""
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
    """The proposal `--start` may confirm: the last entry of `next.md`'s, if that entry is a
    printed proposal (`PRINTED`); None after a start, which consumes it, or without one."""
    try:
        text = record_path(root).read_text(encoding="utf-8")
    except OSError:
        return None
    entries = text.split("\n## ")[1:]
    if not entries or entries[-1].split("\n", 1)[0].rsplit(": ", 1)[-1] not in PRINTED:
        return None
    found = [line for line in entries[-1].splitlines() if line.startswith("- " + PROPOSAL)]
    return found[-1].removeprefix("- " + PROPOSAL) if found else None
