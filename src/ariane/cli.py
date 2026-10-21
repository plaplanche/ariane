"""The `ariane` command line (C23). Every command ends with one line: what it did, what next."""

from __future__ import annotations

import argparse
import datetime
import functools
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from ariane import (
    __version__,
    config,
    flow,
    git,
    logs,
    next_ticket,
    process,
    report,
    risk,
    shadow,
    ticket,
    update,
    verify,
)
from ariane.claude_code import ClaudeCodeRuntime
from ariane.codex import CodexRuntime
from ariane.github import GitHubTracker
from ariane.opencode import OpenCodeRuntime
from ariane.pi import PiRuntime
from ariane.runtime import AgentRuntime, RoutedRuntime
from ariane.tracker import TrackerError

EXIT_OK = flow.EXIT_OK
EXIT_STOPPED = flow.EXIT_STOPPED
EXIT_USAGE = 2
_TOKENS: dict[str, str] = {}


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
    process.make_undumpable()
    reaping = process.set_child_subreaper()
    try:
        root = git.repo_root(Path.cwd())
    except git.GitError as exc:
        return _say(EXIT_USAGE, f"Did nothing: {exc}. Next: run ariane inside a git repository.")
    if args.command == "report":
        logs.configure(level, logs.log_path(root, "report"))
        return _report(root, args.since)
    if args.command == "judge":
        logs.configure(level, logs.log_path(root, f"judge-{args.issue}"))
        return _say_outcome(shadow.judge(root, args.issue, args.verdict, args.minutes, args.note))
    if args.command == "next":
        logs.configure(level, logs.log_path(root, "next"))
        return _next(root, args.start)
    if reaping is not None and args.command in ("start", "update", "verify"):
        return _say(
            EXIT_USAGE,
            f"Did nothing: Ariane could not become the subreaper ({reaping}), so it could not"
            " stop what an agent leaves running. Next: run Ariane where"
            " prctl(PR_SET_CHILD_SUBREAPER) is allowed.",
        )
    if args.command == "verify":
        logs.configure(level, logs.log_path(root, "verify-" + args.branch.replace("/", "-")))
        return _verify(root, args.branch, args.issue)
    if args.command == "update":
        logs.configure(level, logs.log_path(root, f"update-{args.issue}"))
        return _start(root, args.issue, updating=True)
    logs.configure(level, logs.log_path(root, args.issue))
    if args.command == "status":
        return _status(root, args.issue)
    if args.shadow and args.restart:
        return _say(
            EXIT_USAGE,
            f"Did not start #{args.issue}: --restart does not apply to shadow tickets. Next:"
            f" remove the clone at {shadow.clone_path(root, args.issue)}, then run"
            f" ariane start {args.issue} --shadow.",
        )
    return _start(root, args.issue, args.shadow, args.restart)


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
    start.add_argument(
        "--shadow",
        action="store_true",
        help="run the ticket in a separate clone, without push or pull request",
    )
    start.add_argument(
        "--restart",
        action="store_true",
        help="start a stopped or interrupted ticket over: remove its working trees and keep its"
        " branch as ariane-restarted/<issue>-<time>",
    )
    upd = sub.add_parser(
        "update",
        parents=[common],
        help="merge the base branch into a delivered ticket's branch, replay, review, push on go",
    )
    upd.add_argument("issue", type=_issue_number, help="issue number")
    status = sub.add_parser(
        "status", parents=[common], help="show a ticket's state, read from its folder"
    )
    status.add_argument("issue", type=_issue_number, help="issue number")
    nxt = sub.add_parser(
        "next",
        parents=[common],
        help="propose the next ticket of the queue that can start next to the running ones",
    )
    nxt.add_argument(
        "--start",
        action="store_true",
        help="start the proposal last printed, in the background, if it has not changed",
    )
    rep = sub.add_parser(
        "report",
        parents=[common],
        help="show cost, agent time, human time, gates bypassed, shadow results",
    )
    rep.add_argument(
        "--since",
        type=_date,
        metavar="YYYY-MM-DD",
        help="keep tickets started on or after this day (default: all)",
    )
    verify = sub.add_parser(
        "verify",
        parents=[common],
        help="check and review a local branch finished by hand, then record it on the branch",
    )
    verify.add_argument("branch", help="a branch that exists locally")
    verify.add_argument(
        "--issue",
        type=_issue_number,
        help="give this issue's text to the reviewer (default: the branch's commit messages)",
    )
    judge = sub.add_parser(
        "judge",
        parents=[common],
        help="record your verdict and time on a shadow ticket",
    )
    judge.add_argument("issue", type=_issue_number, help="issue number")
    judge.add_argument("verdict", choices=shadow.VERDICTS, help="is the diff acceptable?")
    judge.add_argument(
        "--minutes",
        type=_minutes,
        required=True,
        help=f"human time spent on the ticket, 0 to {shadow.MAX_MINUTES}",
    )
    judge.add_argument("--note", help="free text kept with the verdict")
    return parser


def _version_line() -> str:
    py = sys.version_info
    return f"ariane {__version__} (Python {py.major}.{py.minor}.{py.micro}, {sys.platform})"


def _runtime(cfg: config.Config) -> RoutedRuntime:
    """The runtime of each role, as `[agents.<role>] runtime` says (ADR 0029)."""
    runtimes: dict[str, AgentRuntime] = {}
    for role, agent in (("implementer", cfg.implementer), ("reviewer", cfg.reviewer)):
        if agent.runtime == config.OPENCODE:
            runtimes[role] = OpenCodeRuntime(model=agent.model)
        elif agent.runtime == config.CODEX:
            runtimes[role] = CodexRuntime(api_key_env=agent.api_key_env)
        elif agent.runtime == config.PI:
            runtimes[role] = PiRuntime(api_key_env=agent.api_key_env)
        else:
            runtimes[role] = ClaudeCodeRuntime()
    return RoutedRuntime(runtimes)


def _issue_number(text: str) -> int:
    value = text.removeprefix("#")
    if not value.isdigit() or int(value) <= 0:
        raise argparse.ArgumentTypeError(f"not an issue number: {text}")
    return int(value)


def _minutes(text: str) -> int:
    if not text.isdigit() or int(text) > shadow.MAX_MINUTES:
        raise argparse.ArgumentTypeError(
            f"not a whole number from 0 to {shadow.MAX_MINUTES}: {text}"
        )
    return int(text)


def _date(text: str) -> str:
    try:
        return datetime.date.fromisoformat(text).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a date (YYYY-MM-DD): {text}") from None


def _report(root: Path, since: str | None) -> int:
    result = report.build(root, since, _report_tracker(root), _max_escape_rate(root))
    for line in result.lines:
        print(line)
    return result.exit_code


def _take_token(token_env: str) -> str:
    """Read the tracker token and remove it from Ariane's environment (C21, ADR 0017).

    The value is kept in `_TOKENS`, for the tracker and the push only.
    """
    if token_env in _TOKENS:
        return _TOKENS[token_env]
    names = [n for n in os.environ if n.upper() == token_env.upper()]
    value = next((os.environ[n] for n in names if os.environ[n]), "")
    for name in names:
        del os.environ[name]
    if value:
        _TOKENS[token_env] = value
    return value


def _environment_with(token_env: str, token: str) -> dict[str, str]:
    """A copy of the environment for the run; the token is in the copy, not in the process."""
    env = dict(os.environ)
    if token:
        env[token_env] = token
    return env


def _max_escape_rate(root: Path) -> float:
    """`[checks_policy] max_escape_rate`, its default without the table or the configuration."""
    try:
        policy = config.load(root).checks_policy
    except config.ConfigError:
        policy = None
    return risk.DEFAULT_MAX_ESCAPE_RATE if policy is None else policy.max_escape_rate


def _report_tracker(root: Path) -> GitHubTracker | None:
    """The tracker for the waiting times, or None without configuration or token."""
    try:
        cfg = config.load(root)
    except config.ConfigError:
        return None
    token = _take_token(cfg.tracker.token_env)
    if not token:
        return None
    logs.add_secrets([token])
    return GitHubTracker(
        repository=cfg.tracker.repository,
        token=token,
        api_url=cfg.tracker.api_url,
        ready_label=cfg.tracker.ready_label,
    )


def _next(root: Path, starting: bool) -> int:
    """`ariane next`, or `ariane next --start` (ADR 0059)."""
    try:
        cfg = config.load(root)
    except config.ConfigError as exc:
        return _say(EXIT_USAGE, f"Refused configuration: {exc}. Next: fix ariane.toml.")
    token = _take_token(cfg.tracker.token_env)
    if not token:
        return _say(
            EXIT_USAGE,
            f"Did nothing: environment variable {cfg.tracker.token_env} is empty."
            f" Next: set it to a token with access to {cfg.tracker.repository}.",
        )
    logs.add_secrets([token])
    tracker = GitHubTracker(
        repository=cfg.tracker.repository,
        token=token,
        api_url=cfg.tracker.api_url,
        ready_label=cfg.tracker.ready_label,
    )
    environ = _environment_with(cfg.tracker.token_env, token)
    try:
        if not starting:
            proposal = next_ticket.show(root, cfg, tracker)
            print("\n".join(proposal.lines()))
            code = EXIT_OK if proposal.number is not None else EXIT_STOPPED
            return _say(code, proposal.last_line())
        launch = functools.partial(next_ticket.spawn, root, environ=environ)
        proposal, outcome = next_ticket.start(root, cfg, tracker, launch)
    except (TrackerError, git.GitError, OSError) as exc:
        return _say(EXIT_STOPPED, f"Did nothing: {exc}. Next: fix it, then run ariane next.")
    print("\n".join(proposal.lines()))
    return _say_outcome(outcome)


def _start(
    root: Path,
    number: int,
    shadowed: bool = False,
    restarting: bool = False,
    updating: bool = False,
) -> int:
    """`ariane start`, or `ariane update` when `updating`: both read the issue through the gate."""
    try:
        cfg = config.load(root)
    except config.ConfigError as exc:
        return _say(EXIT_USAGE, f"Refused configuration: {exc}. Next: fix ariane.toml.")
    token = _take_token(cfg.tracker.token_env)
    if not token:
        return _say(
            EXIT_USAGE,
            f"Did not {'update' if updating else 'start'} #{number}: environment variable"
            f" {cfg.tracker.token_env} is empty."
            f" Next: set it to a token with access to {cfg.tracker.repository}.",
        )
    logs.add_secrets([token])
    tracker = GitHubTracker(
        repository=cfg.tracker.repository,
        token=token,
        api_url=cfg.tracker.api_url,
        ready_label=cfg.tracker.ready_label,
    )
    run = shadow.start if shadowed else functools.partial(flow.start, restarting=restarting)
    if updating:
        run = update.update
    outcome = run(
        number,
        repo_root=root,
        config=cfg,
        tracker=tracker,
        runtime=_runtime(cfg),
        environ=_environment_with(cfg.tracker.token_env, token),
    )
    if outcome.detail:
        print(outcome.detail, file=sys.stderr)
    return _say(outcome.exit_code, outcome.line)


def _verify(root: Path, branch: str, number: int | None) -> int:
    try:
        cfg = config.load(root)
    except config.ConfigError as exc:
        return _say(EXIT_USAGE, f"Refused configuration: {exc}. Next: fix ariane.toml.")
    tracker = None
    token = ""
    if number is not None:
        token = _take_token(cfg.tracker.token_env)
        if not token:
            return _say(
                EXIT_USAGE,
                f"Did not verify {branch}: environment variable {cfg.tracker.token_env} is empty."
                f" Next: set it to a token with access to {cfg.tracker.repository}, or leave"
                " out --issue.",
            )
        logs.add_secrets([token])
        tracker = GitHubTracker(
            repository=cfg.tracker.repository,
            token=token,
            api_url=cfg.tracker.api_url,
            ready_label=cfg.tracker.ready_label,
        )
    outcome = verify.verify(
        branch,
        repo_root=root,
        config=cfg,
        runtime=_runtime(cfg),
        environ=_environment_with(cfg.tracker.token_env, token),
        tracker=tracker,
        issue_number=number,
    )
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


def _say_outcome(outcome: flow.Outcome) -> int:
    return _say(outcome.exit_code, outcome.line)


def _say(code: int, line: str) -> int:
    print(line)
    return code


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
