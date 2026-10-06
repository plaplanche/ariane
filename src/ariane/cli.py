"""The `ariane` command line (C23). Every command ends with one line: what it did, what next."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from ariane import __version__, config, flow, git, ticket
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
        root = git.repo_root(Path.cwd())
    except git.GitError as exc:
        return _say(EXIT_USAGE, f"Did nothing: {exc}. Next: run ariane inside a git repository.")
    if args.command == "status":
        return _status(root, args.issue)
    return _start(root, args.issue)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ariane", description="Turn tickets into reviewed pull requests."
    )
    parser.add_argument("--version", action="version", version=f"ariane {__version__}")
    sub = parser.add_subparsers(dest="command")
    start = sub.add_parser("start", help="run the ticket of an issue up to its pull request")
    start.add_argument("issue", type=_issue_number, help="issue number")
    status = sub.add_parser("status", help="show a ticket's state, read from its folder")
    status.add_argument("issue", type=_issue_number, help="issue number")
    return parser


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
    for base in (flow.worktree_path(root, number), root):
        folder = ticket.folder_path(base, number)
        if (folder / ticket.STATUS).is_file():
            fields = ticket.read_status(folder)
            return _say(
                EXIT_OK,
                f"Ticket #{number} is {fields.get('State', 'unknown')}"
                f" ({fields.get('Detail', 'no detail')}), read from {folder}."
                f" Next: {fields.get('Next', 'see its journal')}.",
            )
    return _say(EXIT_STOPPED, f"No ticket folder for #{number}. Next: run ariane start {number}.")


def _say(code: int, line: str) -> int:
    print(line)
    return code


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
