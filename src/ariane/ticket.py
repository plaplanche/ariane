"""The ticket folder (C1): every document of a ticket, readable without Ariane (C23)."""

from __future__ import annotations

import re
import shutil
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from ariane.redact import redact
from ariane.tracker import Issue

WORK_DIR = "work"
BRIEF = "brief.md"
JOURNAL = "journal.md"
STATUS = "status.md"
CHECKS = "checks.md"
RECORDS = (BRIEF, JOURNAL, STATUS, CHECKS)
_BACKTICKS = re.compile(r"`+")


def folder_path(root: Path, number: int) -> Path:
    return root / WORK_DIR / str(number)


def relative_folder(number: int) -> str:
    return f"{WORK_DIR}/{number}"


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ")


def fence(text: str) -> str:
    """A backtick fence longer than any backtick run inside `text`."""
    longest = max((len(run) for run in _BACKTICKS.findall(text)), default=0)
    return "`" * max(3, longest + 1)


def fenced(text: str, info: str = "text") -> str:
    marks = fence(text)
    return f"{marks}{info}\n{text.rstrip()}\n{marks}"


class TicketFolder:
    """Ariane's records of one ticket, in `root/work/<n>/`.

    Ariane keeps every record in memory and rewrites it whole, so an agent that edits,
    deletes, replaces with a link, or adds files in the folder cannot alter what Ariane
    records. Known secrets and token formats are masked in everything written.
    """

    def __init__(self, root: Path, number: int, secrets: Sequence[str] = ()) -> None:
        self.root = root
        self.path = folder_path(root, number)
        self._secrets = [s for s in secrets if s]
        self._records: dict[str, str] = {}

    def create(self, issue: Issue) -> None:
        if self.path.exists() or self.path.is_symlink():
            raise FileExistsError(f"ticket folder already exists: {self.path}")
        self.write(BRIEF, brief(issue))
        self.write(JOURNAL, f"# Journal of ticket #{issue.number}\n")

    def exists(self) -> bool:
        return JOURNAL in self._records

    def log(self, step: str, detail: str = "") -> None:
        entry = f"\n## {now()} {step}\n"
        if detail:
            entry += f"\n{detail.rstrip()}\n"
        self.write(JOURNAL, self._records.get(JOURNAL, "") + entry)

    def set_status(self, state: str, detail: str, next_action: str) -> None:
        self.write(
            STATUS,
            f"# Status\n\n- State: {state}\n- Updated: {now()}\n- Detail: {detail}\n"
            f"- Next: {next_action}\n",
        )

    def write(self, name: str, text: str) -> None:
        self._records[name] = redact(text, self._secrets)
        self._ensure_folder()
        target = self.path / name
        if target.is_symlink() or target.is_dir():
            _remove(target)
        target.write_text(self._records[name], encoding="utf-8", newline="\n")

    def restore(self) -> None:
        """Rewrite the folder exactly as Ariane recorded it, whatever an agent did."""
        self._ensure_folder()
        for entry in self.path.iterdir():
            if entry.name not in self._records:
                _remove(entry)
        for name, text in self._records.items():
            self.write(name, text)

    def _ensure_folder(self) -> None:
        """Make every folder from the root down a real directory, never a link or a file."""
        self.root.mkdir(parents=True, exist_ok=True)
        current = self.root
        for part in self.path.relative_to(self.root).parts:
            current = current / part
            if current.is_symlink() or (current.exists() and not current.is_dir()):
                _remove(current)
            current.mkdir(exist_ok=True)


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def brief(issue: Issue) -> str:
    return (
        f"# Product brief: {issue.title}\n\n"
        "- Status: draft\n"
        "- Approved: not yet\n"
        f"- Source: issue #{issue.number} ({issue.url})\n\n"
        "## Issue\n\n"
        "Prefilled from the issue title and body (never its comments).\n\n"
        f"{issue.body.strip() or '(empty body)'}\n"
    )


def read_status(path: Path) -> dict[str, str]:
    """Parse `status.md` into its fields (State, Updated, Detail, Next)."""
    fields = {}
    for line in (path / STATUS).read_text(encoding="utf-8").splitlines():
        if line.startswith("- ") and ": " in line:
            key, _, value = line[2:].partition(": ")
            fields[key] = value
    return fields
