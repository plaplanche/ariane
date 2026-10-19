"""Run external commands: argument lists, PATH resolution, UTF-8 output, process-tree cleanup."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, NamedTuple

from ariane import logs

# After the process exits or is killed, how long to wait for its pipes to close.
_DRAIN_SECONDS = 10.0
_PR_SET_DUMPABLE = 4
_PR_SET_CHILD_SUBREAPER = 36
# How long to keep stopping, killing and reaping the processes that outlived a command.
_REAP_SECONDS = 5.0


class CommandNotFoundError(Exception):
    """The executable is not on the PATH."""

    def __init__(self, name: str) -> None:
        super().__init__(f"command not found on PATH: {name}")


@dataclass(frozen=True)
class Completed:
    """The outcome of one command."""

    argv: tuple[str, ...]
    returncode: int | None  # None when the command was killed at its time or idle limit
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float
    stopped: bool = False  # the caller asked for the stop (`stream`)
    idle: bool = False  # killed at its idle limit: no output line for too long (`stream`)

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    @property
    def output(self) -> str:
        """Standard output then standard error, as one text."""
        if self.stdout and self.stderr:
            return self.stdout.rstrip("\n") + "\n" + self.stderr
        return self.stdout or self.stderr


def make_undumpable() -> None:
    """On Linux, mark this process not dumpable so a same-user process cannot read its memory
    or environment block (`prctl(PR_SET_DUMPABLE, 0)`). A no-op elsewhere; a failure is only
    journaled as a warning (C21, ADR 0017)."""
    if not sys.platform.startswith("linux"):
        return
    try:
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(_PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "prctl(PR_SET_DUMPABLE) failed")
    except (OSError, AttributeError) as exc:
        logs.emit("process.undumpable_failed", f"Could not make the process undumpable: {exc}")


def set_child_subreaper(on: bool = True) -> str | None:
    """On Linux, make this process the reaper of its orphaned descendants
    (`prctl(PR_SET_CHILD_SUBREAPER)`): a process an agent starts in a new session stays a
    descendant of Ariane, which `kill_survivors` finds. A no-op elsewhere. Returns why it
    failed, or None: on a failure Ariane runs no agent, setup or check (C10, ADR 0031)."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(_PR_SET_CHILD_SUBREAPER, int(on), 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "prctl(PR_SET_CHILD_SUBREAPER) failed")
    except (OSError, AttributeError) as exc:
        logs.emit("process.subreaper_failed", f"Could not become the subreaper: {exc}")
        return str(exc)
    return None


class _Proc(NamedTuple):
    """One process of `/proc`: what `kill_survivors` needs of its `stat`."""

    parent: int
    state: str
    name: str
    group: int = 0  # process group id
    session: int = 0  # session id


def _process_table() -> dict[int, _Proc]:
    """Linux: every process as pid -> `_Proc`, from `/proc`. A zombie's `stat` still holds its
    process group and session."""
    table = {}
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        try:
            with open(f"/proc/{entry.name}/stat", "rb") as file:
                stat = decode(file.read())
        except OSError:
            continue
        head, _, tail = stat.rpartition(")")
        fields = tail.split()
        if len(fields) >= 4 and all(field.isdigit() for field in fields[1:4]):
            name = head.partition("(")[2]
            parent, group, session = (int(field) for field in fields[1:4])
            table[int(entry.name)] = _Proc(parent, fields[0], name, group, session)
    return table


def descendants(*, exited: bool = False) -> dict[int, str]:
    """The running descendants of this process (pid -> command name) on Linux; empty
    elsewhere. Exited processes not yet reaped are left out unless `exited`: the `before` of
    `kill_survivors` includes them, so it never reaps a child someone else waits for."""
    if not sys.platform.startswith("linux"):
        return {}
    tree = _tree(_process_table())
    return {pid: name for pid, (state, name) in tree.items() if exited or state not in _GONE}


_GONE = ("Z", "X")


def _tree(table: Mapping[int, _Proc]) -> dict[int, tuple[str, str]]:
    """The descendants of this process in `table`: pid -> (state, command name)."""
    children: dict[int, list[int]] = {}
    for pid, proc in table.items():
        children.setdefault(proc.parent, []).append(pid)
    found = {}
    pending = list(children.get(os.getpid(), []))
    while pending:
        pid = pending.pop()
        found[pid] = (table[pid].state, table[pid].name)
        pending += children.get(pid, [])
    return found


# The processes `kill_survivors` killed that no caller has taken yet (`take_killed`).
_killed: dict[int, str] = {}
# Commands of several threads (parallel checks, ADR 0052): a spawn and a survivor scan never
# overlap, and a scan spares the commands other threads still wait for.
_lock = threading.RLock()
_running: dict[int, int] = {}  # pid of each command `run` or `stream` waits for -> its thread
_cancelled: set[int] = set()  # threads whose next commands are refused (`cancel`)
_shielded: set[int] = set()  # threads whose commands `cancel` neither kills nor refuses


class Cancelled(Exception):
    """The command was not started: its thread was cancelled (`cancel`)."""


def cancel(threads: Collection[int]) -> None:
    """Kill the process trees of the commands `threads` run now and refuse the ones they start
    next, until `resume`; a thread in `shielded` keeps its command (ADR 0052)."""
    with _lock:
        _cancelled.update(threads)
        for pid, owner in list(_running.items()):
            if owner in threads and owner not in _shielded:
                kill_tree(pid)


def resume(threads: Collection[int]) -> None:
    with _lock:
        _cancelled.difference_update(threads)


@contextlib.contextmanager
def shielded() -> Iterator[None]:
    """The commands this thread runs in the block are not cancelled (creating or removing a
    tree is never left half done)."""
    me = threading.get_ident()
    with _lock:
        _shielded.add(me)
    try:
        yield
    finally:
        with _lock:
            _shielded.discard(me)


def _busy(table: Mapping[int, _Proc], own: int | None = None) -> set[int]:
    """The processes of the commands other threads still wait for (all but `own`): each one,
    its descendants and the members of its process group and session."""
    roots = {pid for pid in _running if pid != own and pid in table}
    groups = _groups(table, roots)
    found = set(roots) | {pid for pid, proc in table.items() if {proc.group, proc.session} & groups}
    children: dict[int, list[int]] = {}
    for pid, proc in table.items():
        children.setdefault(proc.parent, []).append(pid)
    pending = list(found)
    while pending:
        for pid in children.get(pending.pop(), []):
            if pid not in found:
                found.add(pid)
                pending.append(pid)
    return found


def take_killed() -> dict[int, str]:
    """The processes killed for outliving their command since the last call, then forgets them.

    Under the lock of the survivor scans: a record another worker adds is either taken here or
    left for the next call, never cleared unseen."""
    with _lock:
        taken = dict(_killed)
        _killed.clear()
    return taken


def kill_survivors(
    before: Collection[int], left: Mapping[int, str] | None = None
) -> dict[int, str]:
    """Kill the descendants that are not in `before` and reap them; returns them with `left`
    (what the command left in its own group, already killed with it), and keeps them all for
    `take_killed`.

    Called once a session or command ended: anything it started is still running only if it
    left its process group (C10, ADR 0031). A scan of `/proc` is not atomic, so each survivor
    is stopped first (a stopped process cannot fork) and the scans go on until every survivor
    is stopped and none is new; then all are killed. A process that forks and exits faster
    than a scan may never be seen running, so the process group and session of every new
    process found, running or exited (read before it is reaped), are stopped and killed as a
    whole too, unless Ariane or a process in `before` belongs to them. The scans end only when
    one finds no survivor and no newly exited child to reap: a process that forks and exits to
    change pids leaves such a child (Ariane is the subreaper). Linux only; elsewhere it finds
    nothing.
    """
    if not sys.platform.startswith("linux"):
        return {}
    with _lock:
        return _kill_survivors(before, left)


def _kill_survivors(before: Collection[int], left: Mapping[int, str] | None) -> dict[int, str]:
    found: dict[int, str] = {}
    groups: set[int] = set()
    killed: set[int] = set()  # the groups already sent SIGKILL
    me = os.getpid()
    # 0 would be this process's own group for `killpg`; a group of a process in `before` stays
    # protected even after that process is gone.
    kept = {0, os.getpgid(0), os.getsid(0)}
    deadline = time.monotonic() + _REAP_SECONDS
    while True:
        table = _process_table()
        spared = {*before, *_busy(table)}  # what other threads' commands run is not a survivor
        kept |= _groups(table, spared)
        tree = _tree(table)
        exited = {p for p, proc in table.items() if proc.parent == me and proc.state == "Z"}
        # Read from the scan's table, before the exited ones are reaped.
        new_groups = _groups(table, (tree.keys() | exited) - spared) - kept - groups
        groups = (groups | new_groups) - kept
        reaped = [pid for pid in exited if pid not in spared and _wait(pid)]
        members = {pid for pid, proc in table.items() if {proc.group, proc.session} & groups}
        alive = {
            pid: (table[pid].state, table[pid].name)
            for pid in (tree.keys() | members) - {me}
            if pid not in spared and table[pid].state not in _GONE
        }
        if not alive and not reaped and not new_groups:
            if not groups - killed:
                break
            # Nothing seen running, but groups found earlier were only stopped: kill them, then
            # scan again for what that leaves to reap.
            _signal_groups(groups - killed, signal.SIGKILL)
            killed |= groups
            time.sleep(0.01)
            continue
        if time.monotonic() > deadline:
            # Not all stopped in time (one may sit in uninterruptible I/O): kill them anyway,
            # the signal is queued and none is left running unsignalled.
            _signal_groups(groups, signal.SIGKILL)
            killed |= groups
            _signal(alive, signal.SIGKILL)
            listing = ", ".join(f"{name} ({pid})" for pid, (_, name) in sorted(alive.items()))
            logs.emit("process.survivors_remaining", f"Could not kill: {listing or 'none'}")
            found.update({pid: name for pid, (_, name) in alive.items()})
            break
        new = {pid: name for pid, (_, name) in alive.items() if pid not in found}
        if new or new_groups:
            _signal_groups(groups, signal.SIGSTOP)
            _signal(new, signal.SIGSTOP)
            found.update(new)
        elif all(state in ("T", "t") for state, _ in alive.values()):
            _signal_groups(groups, signal.SIGKILL)
            killed |= groups
            _signal(alive, signal.SIGKILL)
            time.sleep(0.01)
        else:
            time.sleep(0.01)  # a stop signal is not delivered yet
    found = dict(left or {}) | found
    if found:
        listing = ", ".join(f"{name} ({pid})" for pid, name in sorted(found.items()))
        logs.emit("process.survivors_killed", f"Killed processes that outlived it: {listing}")
        _killed.update(found)
    return found


def _groups(table: Mapping[int, _Proc], pids: Collection[int]) -> set[int]:
    """The process groups and sessions of the `pids` listed in `table`."""
    return {g for pid in pids if pid in table for g in (table[pid].group, table[pid].session)}


def _signal(pids: Collection[int], signum: int) -> None:
    for pid in pids:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signum)


def _signal_groups(groups: Collection[int], signum: int) -> None:
    if sys.platform == "win32":
        return
    for group in groups:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(group, signum)


def _wait(pid: int) -> bool:
    """Reap an exited child; False if it was not this process's to reap."""
    if sys.platform == "win32":
        return False
    try:
        return os.waitpid(pid, os.WNOHANG)[0] == pid
    except ChildProcessError:
        return False


def resolve(name: str, env: Mapping[str, str] | None = None) -> str:
    """Resolve an executable through the absolute PATH entries only.

    Unlike `shutil.which` on Windows, the current directory is never searched, so a `git.cmd`
    dropped in a working tree cannot shadow the real one. Windows `.cmd` shims are found
    through PATHEXT.
    """
    if os.path.dirname(name):
        return name
    source = env if env is not None else os.environ
    if sys.platform == "win32":
        exts = [""] + [e for e in source.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if e]
    else:
        exts = [""]
    for entry in source.get("PATH", "").split(os.pathsep):
        if not entry or not os.path.isabs(entry):
            continue
        for ext in exts:
            candidate = os.path.join(entry, name + ext)
            if os.path.isfile(candidate) and (
                sys.platform == "win32" or os.access(candidate, os.X_OK)
            ):
                return candidate
    raise CommandNotFoundError(name)


def decode(data: bytes) -> str:
    """Decode process output as UTF-8 whatever the system locale; invalid bytes are replaced."""
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n")


def run(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout_s: float | None = None,
    env: Mapping[str, str] | None = None,
    input_text: str | None = None,
    merge_stderr: bool = False,
) -> Completed:
    """Run `argv` without a shell.

    The process gets its own process group. When it exits or reaches its time limit, the whole
    group is killed, so background children cannot outlive it or hold its output open; on Linux,
    so is any descendant that left the group, and every descendant still running when the
    command exited by itself is counted (`kill_survivors`, `take_killed`).
    """
    return _execute(argv, cwd, timeout_s, env, input_text, merge_stderr, None, None)


def stream(
    argv: Sequence[str],
    *,
    cwd: Path,
    on_line: Callable[[str], bool],
    timeout_s: float | None = None,
    idle_timeout_s: float | None = None,
    env: Mapping[str, str] | None = None,
    input_text: str | None = None,
) -> Completed:
    """Like `run`, but `on_line` sees each line of standard output while the command runs.

    When `on_line` returns True the whole process tree is killed and `Completed.stopped` is set.
    When no standard-output line has arrived for `idle_timeout_s`, the whole process tree is
    killed and `Completed.idle` is set (C5).
    """
    return _execute(argv, cwd, timeout_s, env, input_text, False, on_line, idle_timeout_s)


def _shown(arg: str, limit: int = 200) -> str:
    """An argument for the log, cut when long (a prompt can be 200 KB)."""
    return arg if len(arg) <= limit else f"{arg[:limit]}... ({len(arg)} characters)"


def _execute(
    argv: Sequence[str],
    cwd: Path,
    timeout_s: float | None,
    env: Mapping[str, str] | None,
    input_text: str | None,
    merge_stderr: bool,
    on_line: Callable[[str], bool] | None,
    idle_timeout_s: float | None,
) -> Completed:
    if not argv:
        raise ValueError("empty command")
    args = [resolve(argv[0], env), *argv[1:]]
    kwargs: dict[str, object] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    logs.emit("process.started", " ".join(_shown(arg) for arg in args))
    before = set(descendants(exited=True))
    start = time.monotonic()
    me = threading.get_ident()
    with _lock:  # no survivor scan sees the child before it is registered
        if me in _cancelled and me not in _shielded:
            raise Cancelled(f"not started, the replay is stopping: {' '.join(argv)}")
        proc = subprocess.Popen(
            args,
            cwd=cwd,
            env=dict(env) if env is not None else None,
            stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
            **kwargs,  # type: ignore[call-overload]
        )
        _running[proc.pid] = me
    stop = threading.Event()

    def seen(line: str) -> None:
        if on_line is not None and not stop.is_set() and on_line(line):
            stop.set()
            kill_tree(proc.pid)

    out = _Reader(proc.stdout, seen if on_line is not None else None)
    err = _Reader(proc.stderr)
    if input_text is not None and proc.stdin is not None:
        threading.Thread(target=_feed, args=(proc.stdin, input_text), daemon=True).start()
    left: dict[int, str] = {}
    try:
        timed_out, idle = _wait_limits(proc, start, timeout_s, out, idle_timeout_s)
        if not timed_out and not idle and not stop.is_set():
            # The command ended by itself: what it started and still runs outlived it, in its
            # group or not. Named before the group is killed, so it is counted (C10, ADR 0031).
            left = _left(before, proc.pid)
    finally:
        # Whatever ended the wait (exit, timeout, Ctrl-C, any error), nothing outlives the call.
        kill_tree(proc.pid)
        # Reap the child and let the readers reach the end of the pipes, best effort.
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=_DRAIN_SECONDS)
        with _lock:
            _running.pop(proc.pid, None)
        # What left the group dies too, before the caller goes on (C10, ADR 0031).
        kill_survivors(before, left)
    completed = Completed(
        argv=tuple(argv),
        returncode=None if timed_out or idle else proc.returncode,
        stdout=out.text(),
        stderr=err.text(),
        timed_out=timed_out,
        duration_s=time.monotonic() - start,
        stopped=stop.is_set(),
        idle=idle,
    )
    exit_text = (
        "timed out"
        if timed_out
        else f"no output line for {idle_timeout_s:g} s (idle limit)"
        if idle
        else "stopped by the caller"
        if completed.stopped
        else f"exit {completed.returncode}"
    )
    logs.emit("process.exited", f"{argv[0]}: {exit_text} in {completed.duration_s:.2f} s")
    return completed


def _left(before: Collection[int], own: int) -> dict[int, str]:
    """The running descendants that were not there before the command `own` started, except
    what other threads' commands run."""
    if not sys.platform.startswith("linux"):
        return {}
    with _lock:
        table = _process_table()
        spared = {*before, *_busy(table, own)}
        return {
            pid: name
            for pid, (state, name) in _tree(table).items()
            if pid not in spared and state not in _GONE
        }


def _wait_limits(
    proc: subprocess.Popen[bytes],
    start: float,
    timeout_s: float | None,
    out: _Reader,
    idle_timeout_s: float | None,
) -> tuple[bool, bool]:
    """Wait for the command to exit; (timed out, idle) when a limit ended the wait first."""
    while True:
        now = time.monotonic()
        waits = []
        if timeout_s is not None:
            waits.append(start + timeout_s - now)
        if idle_timeout_s is not None:
            waits.append(out.last_line + idle_timeout_s - now)
        try:
            proc.wait(timeout=max(min(waits), 0) if waits else None)
            return False, False
        except subprocess.TimeoutExpired:
            now = time.monotonic()
            if timeout_s is not None and now >= start + timeout_s:
                return True, False
            if idle_timeout_s is not None and now >= out.last_line + idle_timeout_s:
                return False, True


class _Reader:
    """Read a pipe to its end in a thread, so a full pipe never blocks the child.

    With `on_line`, the pipe is read line by line and each decoded line is passed to it.
    """

    def __init__(
        self, pipe: IO[bytes] | None, on_line: Callable[[str], None] | None = None
    ) -> None:
        self._chunks: list[bytes] = []
        self._thread: threading.Thread | None = None
        self._on_line = on_line
        self.last_line = time.monotonic()  # when the last line arrived (`on_line` only)
        if pipe is not None:
            self._thread = threading.Thread(target=self._read, args=(pipe,), daemon=True)
            self._thread.start()

    def _read(self, pipe: IO[bytes]) -> None:
        with contextlib.suppress(OSError, ValueError):
            if self._on_line is not None:
                for line in iter(pipe.readline, b""):
                    self.last_line = time.monotonic()
                    self._chunks.append(line)
                    self._on_line(decode(line).rstrip("\n"))
                return
            for chunk in iter(lambda: pipe.read(65536), b""):
                self._chunks.append(chunk)

    def text(self) -> str:
        if self._thread is not None:
            self._thread.join(_DRAIN_SECONDS)
        return decode(b"".join(self._chunks))


def _feed(stdin: IO[bytes], text: str) -> None:
    with contextlib.suppress(OSError, ValueError):
        stdin.write(text.encode("utf-8"))
        stdin.close()


def kill_tree(pid: int) -> None:
    """Kill a process and all its descendants (its process group on POSIX)."""
    if sys.platform == "win32":
        subprocess.run(
            [resolve("taskkill"), "/T", "/F", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGKILL)
