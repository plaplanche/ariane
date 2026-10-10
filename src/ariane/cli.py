"""The `ariane` command line (C23). Every command ends with one line: what it did, what next."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from ariane import __version__, config, flow, git, logs, process, ticket
from ariane.claude_code import ClaudeCodeRuntime
from ariane.github import GitHubTracker

EXIT_OK = flow.EXIT_OK
EXIT_STOPPED = flow.EXIT_STOPPED
EXIT_USAGE = 2


def main(argv: Sequence[str] | None = None) -> int:
    _utf8_console()
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return _say(EXIT_USAGE, "Did nothing: no command given. Next: run ariane start <issue>.")
    try:
        level = logs.resolve_level(args.log_level, os.environ)
    except ValueError as exc:
        return _say(
            EXIT_USAGE, (f"Did nothing: {exc}. Next: set --log-level or {logs.LEVEL_VARIABLE}.")
        )
    logs.configure(level)
    try:
        root = git.repo_root(Path.cwd())
    except git.GitError as exc:
        return _say(EXIT_USAGE, f"Did nothing: {exc}. Next: run ariane inside a git repository.")
    logs.configure(level, logs.log_path(root, args.issue))
    if args.command == "status":
        return _status(root, args.issue)
    return _start(root, args.issue)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ariane", description="Turn tickets into reviewed pull requests."
    )
    parser.add_argument("--version", action="version", version=_version_line())
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--log-level",
        metavar="LEVEL",
        help=f"technical log level: debug, info, warning or error (default: {logs.LEVEL_VARIABLE},"
        f" else {logs.DEFAULT_LEVEL})",
    )
    sub = parser.add_subparsers(dest="command")
    start = sub.add_parser(
        "start", parents=[common], help="run the ticket of an issue up to its pull request"
    )
    start.add_argument("issue", type=_issue_number, help="issue number")
    status = sub.add_parser(
        "status", parents=[common], help="show a ticket's state, read from its folder"
    )
    status.add_argument("issue", type=_issue_number, help="issue number")
    return parser


def _version_line() -> str:
    py = sys.version_info
    return f"ariane {__version__} (Python {py.major}.{py.minor}.{py.micro}, {sys.platform})"


def _issue_number(text: str) -> int:
    value = text.removeprefix("#")
    if not value.isdigit() or int(value) <= 0:
        raise argparse.ArgumentTypeError(f"not an issue number: {text}")
    return int(value)


def _start(root: Path, number: int) -> int:
    try:
        cfg = config.load(root)
    except config.ConfigError as exc:
        return _say(EXIT_USAGE, f"Refused configuration: {exc}. Next: fix ariane.toml.")
    token = os.environ.get(cfg.tracker.token_env, "")
    if not token:
        return _say(
            EXIT_USAGE,
            f"Did not start #{number}: environment variable {cfg.tracker.token_env} is empty."
            f" Next: set it to a token with access to {cfg.tracker.repository}.",
        )
    logs.add_secrets([token])
    tracker = GitHubTracker(
        repository=cfg.tracker.repository, token=token, api_url=cfg.tracker.api_url
    )
    outcome = flow.start(
        number,
        repo_root=root,
        config=cfg,
        tracker=tracker,
        runtime=ClaudeCodeRuntime(),
        environ=os.environ,
    )
    if outcome.detail:
        print(outcome.detail, file=sys.stderr)
    return _say(outcome.exit_code, outcome.line)


def _status(root: Path, number: int) -> int:
    fields: dict[str, str] | None = None
    where = ""
    for base in (flow.worktree_path(root, number), root):
        folder = ticket.folder_path(base, number)
        if (folder / ticket.STATUS).is_file():
            fields, where = ticket.read_status(folder), f", read from {folder}"
            break
    merged, problem = _merged(root, number)
    relative = ticket.relative_folder(number)
    if merged is not None and fields is None:
        try:
            text = git.show_on_branch(root, flow.REMOTE, merged, relative + "/" + ticket.STATUS)
        except git.GitError:
            return _say(
                EXIT_OK,
                f"Ticket #{number}: merged into {merged} (last action unknown: no readable"
                f" {ticket.STATUS}). Next: nothing.",
            )
        fields = ticket.parse_status(text)
        where = f", read from {flow.REMOTE}/{merged}"
    if fields is None:
        return _say(
            EXIT_STOPPED, f"No ticket folder for #{number}. Next: run ariane start {number}."
        )
    action = fields.get("Last action", "unknown")
    at = fields.get("At", "unknown time")
    if merged is not None:
        return _say(
            EXIT_OK,
            f"Ticket #{number}: merged into {merged} (last action: {action}, {at}). Next: nothing.",
        )
    note = f" Could not read the remote ({problem}), so a merge is not shown." if problem else ""
    return _say(
        EXIT_OK,
        f"Ticket #{number} is {action} ({fields.get('Detail', 'no detail')}){where}.{note}"
        f" Next: {fields.get('Next', 'see its journal')}.",
    )


def _merged(root: Path, number: int) -> tuple[str | None, str]:
    """The base branch holding the ticket's folder on the remote, or why that is unknown."""
    try:
        base = config.load(root).base_branch
        git.fetch(root, flow.REMOTE, base)
    except (config.ConfigError, git.GitError, process.CommandNotFoundError) as exc:
        return None, str(exc).splitlines()[0] if str(exc) else type(exc).__name__
    if git.path_exists_on_branch(root, flow.REMOTE, base, ticket.relative_folder(number)):
        return base, ""
    return None, ""


def _say(code: int, line: str) -> int:
    print(line)
    return code


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
