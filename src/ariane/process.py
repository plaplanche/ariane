"""Run external commands: argument lists, PATH resolution, UTF-8 output, process-tree cleanup."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from ariane import logs

# After the process exits or is killed, how long to wait for its pipes to close.
_DRAIN_SECONDS = 10.0


class CommandNotFoundError(Exception):
    """The executable is not on the PATH."""

    def __init__(self, name: str) -> None:
        super().__init__(f"command not found on PATH: {name}")


@dataclass(frozen=True)
class Completed:
    """The outcome of one command."""

    argv: tuple[str, ...]
    returncode: int | None  # None when the command was killed at its time limit
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    @property
    def output(self) -> str:
        """Standard output then standard error, as one text."""
        if self.stdout and self.stderr:
            return self.stdout.rstrip("\n") + "\n" + self.stderr
        return self.stdout or self.stderr


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
    group is killed, so background children cannot outlive it or hold its output open.
    """
    if not argv:
        raise ValueError("empty command")
    args = [resolve(argv[0], env), *argv[1:]]
    kwargs: dict[str, object] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    logs.emit("process.started", " ".join(args))
    start = time.monotonic()
    proc = subprocess.Popen(
        args,
        cwd=cwd,
        env=dict(env) if env is not None else None,
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
        **kwargs,  # type: ignore[call-overload]
    )
    out = _Reader(proc.stdout)
    err = _Reader(proc.stderr)
    if input_text is not None and proc.stdin is not None:
        threading.Thread(target=_feed, args=(proc.stdin, input_text), daemon=True).start()
    timed_out = False
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
    kill_tree(proc.pid)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=_DRAIN_SECONDS)
    completed = Completed(
        argv=tuple(argv),
        returncode=None if timed_out else proc.returncode,
        stdout=out.text(),
        stderr=err.text(),
        timed_out=timed_out,
        duration_s=time.monotonic() - start,
    )
    exit_text = "timed out" if timed_out else f"exit {completed.returncode}"
    logs.emit("process.exited", f"{argv[0]}: {exit_text} in {completed.duration_s:.2f} s")
    return completed


class _Reader:
    """Read a pipe to its end in a thread, so a full pipe never blocks the child."""

    def __init__(self, pipe: IO[bytes] | None) -> None:
        self._chunks: list[bytes] = []
        self._thread: threading.Thread | None = None
        if pipe is not None:
            self._thread = threading.Thread(target=self._read, args=(pipe,), daemon=True)
            self._thread.start()

    def _read(self, pipe: IO[bytes]) -> None:
        with contextlib.suppress(OSError, ValueError):
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
