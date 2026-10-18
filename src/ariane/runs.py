"""The run registry: which tickets Ariane runs on a repository, so that the push guard tells
another run's own branch bookkeeping from an agent's change to git (C11, ADR 0017)."""

from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import time
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from ariane import git, process
from ariane.stop import Stop

FOLDER = "runs"
LOCK = ".lock"  # serializes every read and write of the registry
ENDED = "ended.jsonl"  # one line per run that ended: number, branch, start and end
REMOTE = "origin"
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


@contextlib.contextmanager
def registered(where: Path, number: int, branch: str, kept: str = "") -> Iterator[Run]:
    """Record ticket `number` as running in `where/<number>` for the time of the block, then
    append the run to `ended.jsonl` and remove the entry, however the block ends. A live entry
    for the same ticket is another run of it: `Stop`. A stale one (dead process) is replaced.
    `kept` is the branch a restart renames the previous `branch` to, registered before it."""
    entry = where / str(number)
    run = Run(number, branch, os.getpid(), now(), kept)
    with _locked(where):
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
        witnessed.update(live)
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
    config_ok = False
    if keys is not None:
        old, new = _entries(before.get(keys, "")), _entries(after.get(keys, ""))
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
        if config_ok and part in (f"file {shared}", keys):
            continue
        if _shared_setting(part, shared, allowed):  # the `keys` part decides for that file
            continue
        kept.append(line)
    return kept


def _entries(listing: str) -> list[str]:
    """`key=value` entries of a `git config --list --null` listing kept in the snapshot."""
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
