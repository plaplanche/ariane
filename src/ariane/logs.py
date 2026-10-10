"""Log types and technical logs (ADR 0022, C21).

Every functional log type (a journal entry) and technical log type (a record of the `ariane`
logger) is declared here once, with a stable identifier, a level and a one-line meaning.
`docs/logs.md` is generated from these declarations.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from ariane.redact import redact

LOGGER_NAME = "ariane"
LEVEL_VARIABLE = "ARIANE_LOG_LEVEL"
DEFAULT_LEVEL = "warning"
LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}
FUNCTIONAL = "functional"
TECHNICAL = "technical"


@dataclass(frozen=True)
class LogType:
    id: str
    kind: str
    level: str
    meaning: str


def _declare(kind: str, rows: Iterable[tuple[str, str, str]]) -> dict[str, LogType]:
    return {id_: LogType(id_, kind, level, meaning) for id_, level, meaning in rows}


FUNCTIONAL_TYPES = _declare(
    FUNCTIONAL,
    [
        ("ticket.started", "info", "The ticket folder was opened for an issue."),
        ("ticket.setup", "info", "The setup command ran, or there was none."),
        ("ticket.session.started", "info", "The implementer session started, with its context."),
        ("ticket.session.stopped", "info", "The implementer session ended, with cost and summary."),
        (
            "ticket.guard.verified",
            "info",
            "Nothing escaped the ticket branch after untrusted code.",
        ),
        ("ticket.work.committed", "info", "The agent's work was committed on the ticket branch."),
        (
            "ticket.docs.not_updated",
            "info",
            "Documents mapped to changed files that the ticket left untouched.",
        ),
        ("ticket.checks.worktree", "info", "The clean working tree used to replay the checks."),
        ("ticket.checks.replayed", "info", "The checks were replayed by Ariane, with the result."),
        ("ticket.review.started", "info", "A reviewer session started, with its model and limits."),
        (
            "ticket.review.stopped",
            "info",
            "A reviewer session stopped, with its cost and tokens.",
        ),
        ("ticket.review.invalid", "warning", "The reviewer's answer was invalid; asking again."),
        (
            "ticket.review.verdict",
            "info",
            "The review ended: verdict, findings, definition of done.",
        ),
        ("ticket.delivering", "info", "Delivery began: push and pull request."),
        ("ticket.pushed", "info", "The ticket branch was pushed."),
        ("ticket.delivered", "info", "The pull request was opened."),
        ("ticket.warning.ignored_files", "warning", "The agent created files that git ignores."),
        ("ticket.warning.replay_not_removed", "warning", "The replay working tree stayed."),
        ("ticket.warning.statuses_refused", "warning", "The tracker refused commit statuses."),
        ("ticket.stopped", "error", "The ticket stopped; the reason and the next action follow."),
    ],
)

TECHNICAL_TYPES = _declare(
    TECHNICAL,
    [
        ("git.command", "debug", "A git command is run, with its arguments."),
        ("process.started", "debug", "A subprocess started."),
        ("process.exited", "debug", "A subprocess ended, with its exit code and duration."),
        ("github.request", "info", "A GitHub API call and its status."),
        ("guard.verified", "info", "A guard verification passed."),
        ("journal.warning", "warning", "A warning was written to the ticket journal."),
        ("run.stopped", "error", "A ticket run stopped."),
    ],
)

_logger = logging.getLogger(LOGGER_NAME)
_logger.addHandler(logging.NullHandler())


def functional(type_id: str) -> LogType:
    """The declared journal entry type; an undeclared one is an error."""
    try:
        return FUNCTIONAL_TYPES[type_id]
    except KeyError:
        raise ValueError(f"undeclared functional log type: {type_id}") from None


def parse_level(name: str) -> int:
    try:
        return LEVELS[name.strip().lower()]
    except KeyError:
        raise ValueError(f"invalid log level {name!r}: use one of {', '.join(LEVELS)}") from None


def resolve_level(option: str | None, environ: Mapping[str, str]) -> int:
    """The level from `--log-level`, else `ARIANE_LOG_LEVEL`, else warning."""
    if option is not None:
        return parse_level(option)
    return parse_level(environ.get(LEVEL_VARIABLE) or DEFAULT_LEVEL)


def log_path(repo_root: Path, number: int) -> Path:
    """The ticket's log file, beside the repository's working trees, outside the repository."""
    return repo_root.parent / f"{repo_root.name}.ariane" / "logs" / f"{number}.log"


class _Redactor(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        self.secrets: list[str] = []

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage(), self.secrets)
        record.args = None
        return True


_redactor = _Redactor()
_logger.addFilter(_redactor)


def add_secrets(secrets: Iterable[str]) -> None:
    _redactor.secrets.extend(s for s in secrets if s)


def configure(level: int, log_file: Path | None = None) -> None:
    """Send records of at least `level` to standard error and, if given, to `log_file`."""
    for handler in list(_logger.handlers):
        if not isinstance(handler, logging.NullHandler):
            _logger.removeHandler(handler)
            handler.close()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(log_type)s %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    for handler in handlers:
        handler.setFormatter(formatter)
        _logger.addHandler(handler)
    _logger.setLevel(level)
    _redactor.secrets.clear()


def emit(type_id: str, message: str) -> None:
    """Write one technical record naming its declared type."""
    declared = TECHNICAL_TYPES[type_id]
    _logger.log(LEVELS[declared.level], message, extra={"log_type": type_id})
