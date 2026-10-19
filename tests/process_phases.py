"""Count the processes Ariane starts through `process.run`, by phase of a run (#214, ADR 0053).

The phase of a call is named by the innermost frame of Ariane's code, from the call outwards,
that names one: a guard verification inside the replay counts as guard verification, the record
commit of the delivery as a record commit, a listing of the remote as remote listing wherever it
runs. A call no such frame names (preparing the ticket's tree, opening its folder) is setup."""

from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from ariane import process

PHASES = (
    "setup",
    "session",
    "guard verification",
    "remote listing",
    "replay",
    "review",
    "record commits",
    "delivery",
)
# (module, function) of Ariane's code: the phase of the calls made under it.
_FRAMES = {
    ("git.py", "remote_refs"): "remote listing",
    ("flow.py", "_commit_record"): "record commits",
    ("flow.py", "verify"): "guard verification",
    ("flow.py", "verify_remote"): "guard verification",
    ("flow.py", "_unchanged"): "guard verification",
    ("flow.py", "state"): "guard verification",
    ("flow.py", "snapshot"): "guard verification",  # its name before #214
    ("delivery.py", "_last_guard"): "guard verification",
    ("replay.py", "verify_tree"): "guard verification",
    ("replay.py", "_verify_replay"): "guard verification",
    ("replay.py", "replay_each"): "replay",
    ("replay.py", "replay"): "replay",
    ("replay.py", "review_round"): "review",
    ("delivery.py", "deliver"): "delivery",
    ("flow.py", "_implement"): "session",
    ("flow.py", "_commit_agent_work"): "session",
    ("flow.py", "_fix"): "session",
}
_SOURCE = Path(process.__file__).parent


@dataclass
class Count:
    """The processes started, by phase, and their command lines, in order."""

    phases: Counter[str] = field(default_factory=Counter)
    commands: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.phases.values())

    def of(self, phase: str, word: str) -> int:
        """How many commands of `phase` have `word` among their arguments."""
        return sum(1 for p, argv in self.commands if p == phase and word in argv)

    def line(self) -> str:
        return f"{self.total} processes: " + ", ".join(f"{p} {self.phases[p]}" for p in PHASES)


def _phase(frame: object) -> str:
    while frame is not None:
        code = frame.f_code  # type: ignore[attr-defined]
        path = Path(code.co_filename)
        if path.parent == _SOURCE:
            found = _FRAMES.get((path.name, code.co_name))
            if found is not None:
                return found
        frame = frame.f_back  # type: ignore[attr-defined]
    return "setup"


@contextmanager
def counted(monkeypatch: pytest.MonkeyPatch) -> Iterator[Count]:
    """The processes started through `process.run` while the block runs, by phase."""
    count = Count()
    real = process.run

    def counting(argv: list[str], **kwargs: object) -> process.Completed:
        phase = _phase(sys._getframe(1))
        count.phases[phase] += 1
        count.commands.append((phase, tuple(argv)))
        return real(argv, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(process, "run", counting)
    try:
        yield count
    finally:
        monkeypatch.setattr(process, "run", real)
