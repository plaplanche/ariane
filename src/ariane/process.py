"""Run external commands: argument lists, PATH resolution, UTF-8 output, process-tree timeouts."""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

# After a timeout kill, how long to wait for the pipes to close before giving up on the output.
_DRAIN_SECONDS = 10.0


class CommandNotFoundError(Exception):
    """The executable is not on the PATH."""

    def __init__(self, name: str) -> None:
        super().__init__(f"command not found on PATH: {name}")
        self.name = name


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
    """Resolve an executable through the PATH, so that Windows `.cmd` shims are found."""
    path = (env if env is not None else os.environ).get("PATH")
    found = shutil.which(name, path=path)
    if found is None:
        raise CommandNotFoundError(name)
    return found


def decode(data: bytes | None) -> str:
    """Decode process output as UTF-8 whatever the system locale; invalid bytes are replaced."""
    if not data:
        return ""
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
    """Run `argv` without a shell. On timeout the whole process tree is killed."""
    if not argv:
        raise ValueError("empty command")
    args = [resolve(argv[0], env), *argv[1:]]
    kwargs: dict[str, object] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
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
    data = input_text.encode("utf-8") if input_text is not None else None
    timed_out = False
    try:
        out, err = proc.communicate(data, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_tree(proc.pid)
        try:
            out, err = proc.communicate(timeout=_DRAIN_SECONDS)
        except subprocess.TimeoutExpired:  # a descendant escaped the tree and holds the pipes
            proc.kill()
            out, err = b"", b""
    return Completed(
        argv=tuple(argv),
        returncode=None if timed_out else proc.returncode,
        stdout=decode(out),
        stderr=decode(err),
        timed_out=timed_out,
        duration_s=time.monotonic() - start,
    )


def kill_tree(pid: int) -> None:
    """Kill a process and all its descendants."""
    if sys.platform == "win32":
        subprocess.run(
            [resolve("taskkill"), "/T", "/F", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pid, signal.SIGKILL)
