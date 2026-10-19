"""The machine-wide slot of a run (C11, C22, ADR 0050): a number from 0 to 15 that no other
Ariane run on the machine holds at the same time, given to the project as `ARIANE_SLOT`
(`context.SLOT_VARIABLE`)."""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import IO

from ariane.stop import Stop

COUNT = 16
REASON = f"{COUNT} Ariane runs already hold a slot on this machine"
NEXT_ACTION = "wait for one to end"


def folder() -> Path:
    """`~/.ariane/slots/`, shared by every Ariane run of the user on the machine."""
    return Path.home() / ".ariane" / "slots"


def try_lock(file: IO[bytes]) -> bool:
    """Take an operating-system lock on `file` without waiting; closing the file, or the end of
    the process, releases it."""
    if sys.platform == "win32":
        import msvcrt

        file.seek(0)
        try:
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(file: IO[bytes]) -> None:
    """Release the lock now on Windows, where a lock may outlive its closed file for a moment;
    on POSIX, closing the file releases it at once."""
    if sys.platform == "win32":
        import msvcrt

        file.seek(0)
        with contextlib.suppress(OSError):
            msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)


@contextlib.contextmanager
def held(where: Path | None = None) -> Iterator[int]:
    """Hold the lowest free slot `k` (its file `<where>/<k>.lock` locked) for the block.
    All held: `Stop`, without waiting."""
    where = folder() if where is None else where
    where.mkdir(parents=True, exist_ok=True)
    for k in range(COUNT):
        file = (where / f"{k}.lock").open("a+b")
        if try_lock(file):
            with file:  # closing the file releases the lock
                try:
                    yield k
                finally:
                    _unlock(file)
            return
        file.close()
    raise Stop(REASON, NEXT_ACTION)


@contextlib.contextmanager
def several(count: int, where: Path | None = None) -> Iterator[list[int]]:
    """Hold up to `count` more slots for the block, as many as are free, lowest first: the
    slots of the parallel checks beyond the run's own (ADR 0052). None free: an empty list."""
    with contextlib.ExitStack() as stack:
        taken: list[int] = []
        for _ in range(count):
            try:
                taken.append(stack.enter_context(held(where)))
            except Stop:
                break
        yield taken
