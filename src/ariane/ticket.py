"""The ticket folder (C1): every document of a ticket, readable without Ariane (C23)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ariane.tracker import Issue

WORK_DIR = "work"
BRIEF = "brief.md"
JOURNAL = "journal.md"
STATUS = "status.md"
CHECKS = "checks.md"


def folder_path(root: Path, number: int) -> Path:
    return root / WORK_DIR / str(number)


def relative_folder(number: int) -> str:
    return f"{WORK_DIR}/{number}"


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ")


class TicketFolder:
    """Ariane's records of one ticket.

    Ariane keeps the journal in memory and rewrites the whole file at every entry, so an agent
    that edits or deletes the folder cannot alter what Ariane records.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._brief = ""
        self._journal = ""

    def create(self, issue: Issue) -> None:
        self.path.mkdir(parents=True, exist_ok=False)
        self._brief = brief(issue)
        self.write(BRIEF, self._brief)
        self._journal = f"# Journal of ticket #{issue.number}\n"
        self.write(JOURNAL, self._journal)

    def log(self, step: str, detail: str = "") -> None:
        entry = f"\n## {now()} {step}\n"
        if detail:
            entry += f"\n{detail.rstrip()}\n"
        self._journal += entry
        self.write(JOURNAL, self._journal)

    def restore(self) -> None:
        """Rewrite the brief and journal as Ariane recorded them, whatever an agent did."""
        self.write(BRIEF, self._brief)
        self.write(JOURNAL, self._journal)

    def set_status(self, state: str, detail: str, next_action: str) -> None:
        self.write(
            STATUS,
            f"# Status\n\n- State: {state}\n- Updated: {now()}\n- Detail: {detail}\n"
            f"- Next: {next_action}\n",
        )

    def write(self, name: str, text: str) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        _write(self.path / name, text)


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


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")
