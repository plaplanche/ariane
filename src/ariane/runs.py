"""The run registry: which tickets Ariane runs on a repository, so that the push guard tells
another run's own branch bookkeeping from an agent's change to git (C11, ADR 0017)."""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from ariane import git
from ariane.stop import Stop

FOLDER = "runs"
LOCK = ".lock"  # serializes every read and write of the registry
ENDED = "ended.jsonl"  # one line per run that ended: number, branch, start and end
REMOTE = "origin"


@dataclass(frozen=True)
class Run:
    number: int
    branch: str
    pid: int
    started: str  # ISO 8601, UTC


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
def registered(where: Path, number: int, branch: str) -> Iterator[Run]:
    """Record ticket `number` as running in `where/<number>` for the time of the block, then
    append the run to `ended.jsonl` and remove the entry, however the block ends. A live entry
    for the same ticket is another run of it: `Stop`. A stale one (dead process) is replaced."""
    entry = where / str(number)
    run = Run(number, branch, os.getpid(), now())
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
            with contextlib.suppress(OSError):
                _publish_end(where, run)  # first: a reader always finds the run in one place
            _release(entry, run)


def _publish_end(where: Path, run: Run) -> None:
    with (where / ENDED).open("a", encoding="utf-8") as file:
        file.write(json.dumps({**asdict(run), "ended": now()}) + "\n")


def _release(entry: Path, run: Run) -> None:
    """Remove `entry` if it is still `run`'s: never another run's registration."""
    if _read(entry) == run:
        entry.unlink(missing_ok=True)


def running(where: Path) -> dict[int, Run]:
    """The registered runs whose process exists; stale entries are removed."""
    if not where.is_dir():
        return {}
    with _locked(where):
        return _live(where)


def _live(where: Path) -> dict[int, Run]:
    found: dict[int, Run] = {}
    for path in where.iterdir():
        if not path.name.isdigit():
            continue
        run = _read(path)
        if run is not None and alive(run.pid):
            found[run.number] = run
        else:
            path.unlink(missing_ok=True)  # stale: its process is gone, or it is unreadable
    return found


def during(where: Path, since: str) -> set[int]:
    """The tickets registered as running now, or that ended at or after `since`, read under
    the lock: a run ending meanwhile is in one or the other."""
    if not where.is_dir():
        return set()
    with _locked(where):
        return set(_live(where)) | _ended(where, since)


def _ended(where: Path, since: str) -> set[int]:
    numbers = set()
    with contextlib.suppress(OSError):
        for line in (where / ENDED).read_text(encoding="utf-8").splitlines():
            with contextlib.suppress(ValueError, KeyError, TypeError, AttributeError):
                ended = json.loads(line)
                if ended["ended"] >= since:
                    numbers.add(int(ended["number"]))
    return numbers


def _bookkeeping(numbers: set[int], base_branch: str) -> set[str]:
    """The `key=value` entries git writes for another run's branch `ariane/<m>`, and no other."""
    allowed = set()
    for m in numbers:
        section = f"branch.ariane/{m}"
        allowed |= {
            f"{section}.remote={REMOTE}",
            f"{section}.merge=refs/heads/ariane/{m}",
            f"{section}.merge=refs/heads/{base_branch}",  # what `worktree add -b` writes
        }
    return allowed


def foreign_changes(
    before: dict[str, str], after: dict[str, str], numbers: set[int], base_branch: str
) -> list[str]:
    """`git.snapshot_changes(before, after)` without those that are another run's own: the
    branch `ariane/<m>` of a ticket in `numbers`, and its `remote` and `merge` keys added to or
    removed from the shared config. Anything else is kept, so the guard still stops on it."""
    allowed = _bookkeeping(numbers, base_branch)
    refs = {f"ref refs/heads/ariane/{m}" for m in numbers}
    keys = next((k for k in {*before, *after} if k.startswith("keys ")), None)
    shared = keys.removeprefix("keys ") if keys else None
    config_ok = False
    if keys is not None:
        delta = Counter(_entries(after.get(keys, "")))
        delta.subtract(_entries(before.get(keys, "")))
        moved = {entry for entry, count in delta.items() if count}
        config_ok = bool(moved) and moved <= allowed
    kept = []
    for line in git.snapshot_changes(before, after):
        kind, _, part = line.partition(": ")
        if part in refs:
            continue
        if config_ok and part in (f"file {shared}", keys):
            continue
        if config_ok and kind != "changed" and _shared_setting(part, shared, allowed):
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
