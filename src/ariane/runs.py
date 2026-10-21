"""The run registry: which tickets Ariane runs on a repository, so that the push guard tells
another run's own branch bookkeeping from an agent's change to git (C11, ADR 0017)."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from ariane import git, process, restart
from ariane.stop import GUARD, Stop
from ariane.tracker import Issue, IssueRefused, Tracker

FOLDER = "runs"
LOCK = ".lock"  # serializes every read and write of the registry
ENDED = "ended.jsonl"  # one line per run that ended: number, branch, start and end
REMOTE = "origin"
HANDOFF = "next"  # `<repo>.ariane/next`: its lock covers `ariane next --start`'s handoff
HANDOFF_ENV = "ARIANE_NEXT_LAUNCH"  # set to `<n>` in the `ariane start <n>` it launches
CLAIM_ENV = "ARIANE_NEXT_CLAIM"  # and to the time of the reservation it registers under
ISSUE_ENV = "ARIANE_NEXT_ISSUE"  # and to the digest of the issue body `ariane next` analysed
WATCH_SECONDS = 0.2  # how often a run reads the registry for the runs it can vouch for


@dataclass(frozen=True)
class Run:
    number: int
    branch: str
    pid: int
    started: str  # ISO 8601, UTC
    kept: str = ""  # with `--restart`, the name its previous branch is kept under (ADR 0047)


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def folder(repo_root: Path) -> Path:
    """`<repo>.ariane/runs`, next to the tickets' working trees."""
    return repo_root.parent / f"{repo_root.name}.ariane" / FOLDER


def alive(pid: int) -> bool:
    """Whether process `pid` exists (signal 0 on POSIX, an open handle on Windows)."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        try:
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return bool(ok) and code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read(path: Path) -> Run | None:
    try:
        return Run(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


@contextlib.contextmanager
def _locked(where: Path) -> Iterator[None]:
    """Hold `where/.lock` for the block: registration, reclaiming stale entries, ending a run
    and reading the registry never interleave. The system frees the lock when its process dies,
    so a crashed run never leaves it held."""
    where.mkdir(parents=True, exist_ok=True)
    with (where / LOCK).open("a+b") as file:
        if sys.platform == "win32":
            import msvcrt

            file.seek(0)
            while True:
                try:
                    msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.01)
            try:
                yield
            finally:
                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)


def handoff_folder(where: Path) -> Path:
    """`<repo>.ariane/next`, beside the registry `where`."""
    return where.parent / HANDOFF


def locked(where: Path) -> contextlib.AbstractContextManager[None]:
    """Hold `where/.lock` for the block, as the registry does with its own (`_locked`)."""
    return _locked(where)


def launched(number: int) -> bool:
    """Whether this process is the `ariane start <number>` that `ariane next --start` launched."""
    return os.environ.get(HANDOFF_ENV) == str(number)


def digest(body: str) -> str:
    """The digest of an issue body, as `ariane next --start` passes it in `ISSUE_ENV`."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def read_issue(tracker: Tracker, number: int) -> Issue:
    """`tracker.read_issue`; in the ticket `ariane next --start` launched, `IssueRefused`
    unless the body is the one `ariane next` analysed (`ISSUE_ENV`): an edit made before the
    relabel is not blessed by it (ADR 0060)."""
    issue = tracker.read_issue(number)
    if launched(number) and os.environ.get(ISSUE_ENV) != digest(issue.body):
        refused = IssueRefused(f"issue #{number} changed since ariane next analysed it")
        refused.next_action = "read the issue, label it again if it is right, then run ariane next"
        raise refused
    return issue


def _handoff(where: Path, number: int) -> contextlib.AbstractContextManager[None]:
    """The handoff lock of `ariane next --start` (ADR 0060): a registration waits while it
    checks a proposal and launches it, so its check sees every run registered before its own;
    the ticket it launches (`HANDOFF_ENV`) registers inside it, under its reservation."""
    if launched(number):
        return contextlib.nullcontext()
    return _locked(handoff_folder(where))


def _claimed(where: Path, number: int) -> None:
    """In the ticket `ariane next --start` launched, `Stop` unless its reservation is still
    there (`CLAIM_ENV`): once a later `ariane next` dropped it (its starter died, and it did not
    register in time), proposals no longer count it, so it may not register outside the lock."""
    if not launched(number):
        return
    try:
        left = json.loads((handoff_folder(where) / f"{number}.json").read_text(encoding="utf-8"))
        held = left["at"] == os.environ.get(CLAIM_ENV)
    except (OSError, ValueError, TypeError, KeyError):
        held = False
    if not held:
        raise Stop(
            f"the reservation of ariane next --start for #{number} was dropped before it"
            " registered as running",
            f"run ariane next, then ariane next --start to start #{number} again",
        )


@contextlib.contextmanager
def registered(where: Path, number: int, branch: str, kept: str = "") -> Iterator[Run]:
    """Record ticket `number` as running in `where/<number>` for the time of the block, then
    append the run to `ended.jsonl` and remove the entry, however the block ends. A live entry
    for the same ticket is another run of it: `Stop`. A stale one (dead process) is replaced.
    `kept` is the branch a restart renames the previous `branch` to, registered before it."""
    entry = where / str(number)
    run = Run(number, branch, os.getpid(), now(), kept)
    with _handoff(where, number), _locked(where):
        _claimed(where, number)  # under the registry's lock, which a reconciliation reads under
        other = _read(entry)
        if other is not None and alive(other.pid):
            raise Stop(
                f"ticket #{number} is already running (process {other.pid})",
                "wait for that run to end, or stop it",
            )
        entry.unlink(missing_ok=True)  # stale: under the lock, nobody registered it since
        draft = where / f"{number}.{run.pid}.tmp"
        draft.write_text(json.dumps(asdict(run)), encoding="utf-8")
        try:
            os.link(draft, entry)  # atomic: an entry is always whole
        finally:
            draft.unlink(missing_ok=True)
    try:
        yield run
    finally:  # the registry never hides how the run ended
        with contextlib.suppress(OSError), _locked(where):
            try:
                _publish_end(where, run)  # first: a reader always finds the run in one place
            except OSError:
                pass  # the entry stays: once its process is gone, readers count it as ended
            else:
                _release(entry, run)


def _publish_end(where: Path, run: Run) -> None:
    with (where / ENDED).open("a", encoding="utf-8") as file:
        file.write(json.dumps({**asdict(run), "ended": now()}) + "\n")


def _release(entry: Path, run: Run) -> None:
    """Remove `entry` if it is still `run`'s: never another run's registration."""
    if _read(entry) == run:
        entry.unlink(missing_ok=True)


def running(where: Path) -> dict[int, Run]:
    """The registered runs whose process exists; stale entries are moved to the history."""
    if not where.is_dir():
        return {}
    with _locked(where):
        _reclaim(where)
        return _live(where)


def _live(where: Path) -> dict[int, Run]:
    found: dict[int, Run] = {}
    for path in where.iterdir():
        run = _read(path) if path.name.isdigit() else None
        if run is not None and alive(run.pid):
            found[run.number] = run
    return found


def registered_since(where: Path, number: int, since: str) -> bool:
    """Whether a run of ticket `number` registered at or after `since`: live, or ended."""
    if not where.is_dir():
        return False
    with _locked(where):
        _reclaim(where)
        live = _live(where).get(number)
        ended = _ended(where, since)
    runs = [live] if live is not None else []
    return any(run.number == number and run.started >= since for run in [*runs, *ended])


def _reclaim(where: Path) -> None:
    """An entry whose process is gone (a crashed run, or one that could not publish its end)
    is published to the history, ended now, then removed; unreadable, it is removed. If the
    history cannot be written the entry stays, so the run is always found in one place."""
    for path in [p for p in where.iterdir() if p.name.isdigit()]:
        run = _read(path)
        if run is not None and alive(run.pid):
            continue
        if run is not None:
            try:
                _publish_end(where, run)
            except OSError:
                continue
        path.unlink(missing_ok=True)


def genuine(run: Run) -> bool:
    """Whether `run` is an Ariane run Ariane can vouch for, not an entry an agent wrote: its
    process exists, is not a descendant of this one (every agent process is, Ariane being the
    subreaper on Linux, ADR 0031), and on Linux its command line is `... start <number>`."""
    if not alive(run.pid) or run.pid in process.descendants():
        return False
    return _started_as(run.pid, run.number)


def _started_as(pid: int, number: int) -> bool:
    """On Linux, whether `pid` runs `start <number>`; elsewhere it cannot be read (a residual of
    ADR 0017), so the live process is taken as enough."""
    if not sys.platform.startswith("linux"):
        return True
    try:
        words = Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").split("\0")
    except OSError:
        return False
    return any(w == "start" and words[i + 1 : i + 2] == [str(number)] for i, w in enumerate(words))


@contextlib.contextmanager
def watching(where: Path) -> Iterator[dict[int, Run]]:
    """The other runs seen live and `genuine` while the block runs, read every `WATCH_SECONDS`
    by a thread of Ariane's own process, which no agent reaches: a run that starts and ends
    during one agent session is seen too (C11)."""
    witnessed: dict[int, Run] = {}
    done = threading.Event()

    def watch() -> None:
        while True:
            with contextlib.suppress(OSError):
                during(where, now(), witnessed)
            if done.wait(WATCH_SECONDS):
                return

    thread = threading.Thread(target=watch, name="ariane-runs", daemon=True)
    thread.start()
    try:
        yield witnessed
    finally:
        done.set()
        thread.join()


def during(where: Path, since: str, witnessed: dict[int, Run]) -> set[int]:
    """The other runs whose branch bookkeeping the guard tolerates, read under the lock (a run
    ending meanwhile is in one place or the other). The entries and the history are files an
    agent can write, so only what Ariane can vouch for counts: a live entry that is `genuine`,
    added to `witnessed`; and a run that ended at or after `since` (a stale entry is ended when
    reclaimed) only if this run saw it live (`witnessed`) with the same process and start."""
    if not where.is_dir():
        return set()
    with _locked(where):
        _reclaim(where)
        live = {number: run for number, run in _live(where).items() if genuine(run)}
        for number, run in live.items():  # an entry is written once: a rewrite is not its run's
            if number not in witnessed or witnessed[number].pid != run.pid:
                witnessed[number] = run
        gone = _ended(where, since)
    return set(live) | {run.number for run in gone if witnessed.get(run.number) == run}


def _ended(where: Path, since: str) -> set[Run]:
    found = set()
    with contextlib.suppress(OSError):
        for line in (where / ENDED).read_text(encoding="utf-8").splitlines():
            with contextlib.suppress(ValueError, KeyError, TypeError, AttributeError):
                ended = json.loads(line)
                if ended.pop("ended") >= since:
                    found.add(Run(**ended))
    return found


def kept_branches(witnessed: dict[int, Run], numbers: Iterable[int]) -> set[str]:
    """The kept branches of the runs in `numbers` that the guard tolerates: only a name a
    restart of that very ticket chose when it started (`restart.is_kept_name`), as first
    witnessed. The entry is agent-writable: any other name, `main` included, is never exempt."""
    found = set()
    for m in numbers:
        run = witnessed.get(m)
        if run is not None and restart.is_kept_name(run.kept, run.number, run.started):
            found.add(run.kept)
    return found


def _bookkeeping(numbers: set[int]) -> set[str]:
    """The `key=value` entries git writes for another run's branch `ariane/<m>`, and no other."""
    allowed = set()
    for m in numbers:
        section = f"branch.ariane/{m}"
        allowed |= {
            f"{section}.remote={REMOTE}",
            f"{section}.merge=refs/heads/ariane/{m}",
        }
    return allowed


def foreign_changes(
    before: dict[str, str],
    after: dict[str, str],
    numbers: set[int],
    kept: Iterable[str] = (),
) -> list[str]:
    """`git.snapshot_changes(before, after)` without those that are another run's own: the
    branch `ariane/<m>` of a ticket in `numbers`, the branches in `kept` (the names other runs
    registered for their previous branch when restarting, `Run.kept`), and the `remote` and
    `merge` keys of `ariane/<m>` added to or removed from the shared config. Anything else is
    kept, so the guard still stops on it."""
    allowed = _bookkeeping(numbers)
    refs = {f"ref refs/heads/ariane/{m}" for m in numbers}
    refs |= {f"ref refs/heads/{name}" for name in kept if name}
    keys = next((k for k in {*before, *after} if k.startswith("keys ")), None)
    shared = keys.removeprefix("keys ") if keys else None
    config_ok = same_keys = False
    if keys is not None and before.get(keys) != after.get(keys):  # listed only when it changed
        where = Path(keys.removeprefix("keys ")).parent
        old, new = (_entries(git.config_keys(where, s.get(keys, ""))) for s in (before, after))
        same_keys = old == new  # a comment only: the file's digest says it
        delta = Counter(new)
        delta.subtract(old)
        moved = {entry for entry, count in delta.items() if count}
        # Every other entry in the same order: reordering duplicates changes their effect.
        config_ok = (
            bool(moved)
            and moved <= allowed
            and [e for e in old if e not in allowed] == [e for e in new if e not in allowed]
        )
    kept = []
    for line in git.snapshot_changes(before, after):
        part = line.partition(": ")[2]
        if part in refs:
            continue
        if (config_ok and part in (f"file {shared}", keys)) or (same_keys and part == keys):
            continue
        if _shared_setting(part, shared, allowed):  # the `keys` part decides for that file
            continue
        kept.append(line)
    return kept


def tracking_fast_forward(
    cwd: Path,
    guard: dict[str, str],
    now: dict[str, str],
    changes: list[str],
    ref: str,
    remote_base: Callable[[], str],
) -> list[str]:
    """`changes` without the move of the base's tracking `ref` when it is the only one left and
    goes from the commit in `guard` to a descendant that the remote's base points to now
    (`remote_base`, read only then): another run fetched a base that advanced by a merge. `guard`
    then takes the new commit, so that a later move is measured from it. Any other move of `ref`
    (backwards, sideways, to a commit that is not the remote's base, a deletion) is kept, so the
    guard still stops on it (C11, ADR 0055). Git is read only once the rest of it is unchanged."""
    key = f"ref {ref}"
    if changes != [f"changed: {key}"]:
        return changes
    old, new = guard.get(key, ""), now.get(key, "")
    if not old or not new or new != remote_base() or not git.is_ancestor(cwd, old, new):
        return changes
    guard[key] = new
    return []


def guard_stop(after: str, changes: list[str], quiet: str) -> Stop | None:
    """The stop of a run whose guard found `changes` (`foreign_changes`) after `after`, or None;
    `quiet` is the advice that ends its next action."""
    written = [c for c in changes if c.partition(": ")[2].startswith("instructions ")]
    if written:
        return Stop(
            f"{after} changed instruction files the reviewer can load",
            "inspect and remove them (they are outside the repository); Ariane pushed"
            f" nothing; {quiet}",
            "\n".join(f"- {line}" for line in written),
            category=GUARD,
        )
    if changes:
        return Stop(
            f"{after} changed git configuration, hooks or local branches",
            f"inspect .git/config, .git/hooks and the branches; Ariane pushed nothing; {quiet}",
            "\n".join(f"- {line}" for line in changes),
            category=GUARD,
        )
    return None


def survivors_stop(after: str, killed: dict[int, str]) -> Stop:
    """The stop of a run whose step `after` left the `killed` processes (pid to name) running,
    which Ariane killed (C10, ADR 0031): a guard violation."""
    listing = "\n".join(f"- {name} (pid {pid})" for pid, name in sorted(killed.items()))
    return Stop(
        f"{after} left {len(killed)} process(es) running after it ended; Ariane killed them",
        "find what started them in the background; Ariane pushed nothing",
        listing,
        category=GUARD,
    )


def remote_stop(after: str, changed: list[str], quiet: str) -> Stop:
    """The stop of a run whose remote refs `changed` (`git.remote_changes`) during `after`."""
    return Stop(
        f"the remote changed during {after} ({', '.join(changed)})",
        f"check it was not the agent; if a person pushed, start the ticket again; {quiet}",
        category=GUARD,
    )


def _entries(listing: str) -> list[str]:
    """`key=value` entries of a `git config --list --null` listing (`git.config_keys`)."""
    return [e.replace("\n", "=", 1) for e in listing.split("\0") if e]


def _shared_setting(part: str, shared: str | None, allowed: set[str]) -> bool:
    """Whether `part` is a `setting` line of the shared config whose entry is in `allowed`."""
    scope, _, rest = part.removeprefix("setting ").partition("\t")
    origin, _, entry = rest.partition("\t")
    if not part.startswith("setting ") or scope != "local" or shared is None:
        return False
    if not origin.startswith("file:") or entry not in allowed:
        return False
    path = origin.removeprefix("file:")
    if not Path(path).is_absolute():  # git names it relative to a main checkout: `.git/config`
        return shared.endswith("/" + path)
    return Path(path).resolve() == Path(shared).resolve()
