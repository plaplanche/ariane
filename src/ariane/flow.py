"""`ariane start`: one issue becomes a pull request whose checks Ariane replayed (ADR 0006)."""

from __future__ import annotations

import contextlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ariane import checks, context, git, process, ticket
from ariane.config import Config
from ariane.runtime import AgentRuntime, Session, SessionResult, StopReason
from ariane.tracker import Issue, Tracker, TrackerError

REMOTE = "origin"
SETUP_TIMEOUT_S = 30 * 60


@dataclass(frozen=True)
class Outcome:
    exit_code: int
    line: str  # what was done, then the next possible action (C23)
    detail: str = ""  # shown before the line, for example a failing setup's output


class Stop(Exception):
    """The ticket stops here; `reason` and `next_action` go to the user and the journal."""

    def __init__(self, reason: str, next_action: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.next_action = next_action
        self.detail = detail


def worktree_path(repo_root: Path, number: int) -> Path:
    return repo_root.parent / f"{repo_root.name}.ariane" / "worktrees" / str(number)


def branch_name(number: int) -> str:
    return f"ariane/{number}"


def start(
    number: int,
    *,
    repo_root: Path,
    config: Config,
    tracker: Tracker,
    runtime: AgentRuntime,
    environ: Mapping[str, str],
) -> Outcome:
    try:
        issue = tracker.read_issue(number)
    except TrackerError as exc:
        return Outcome(1, f"Did not start #{number}: {exc}. Next: check the number and access.")
    branch = branch_name(number)
    worktree = worktree_path(repo_root, number)
    try:
        url, heads_before = _prepare(repo_root, config, branch, worktree)
    except (Stop, git.GitError) as exc:
        reason, next_action = _describe(exc)
        return Outcome(1, f"Did not start ticket #{number}: {reason}. Next: {next_action}.")
    run = _TicketRun(issue, config, tracker, runtime, environ, worktree, branch, url)
    return run.execute(heads_before)


def _prepare(
    repo_root: Path, config: Config, branch: str, worktree: Path
) -> tuple[str, dict[str, str]]:
    """Refuse a ticket already started, then create its branch and working tree."""
    if worktree.exists():
        raise Stop(f"its working tree already exists at {worktree}", "remove it to start over")
    if git.local_branch_exists(repo_root, branch):
        raise Stop(f"branch {branch} already exists locally", "delete it to start over")
    url = git.push_url(repo_root, REMOTE)
    git.fetch(repo_root, REMOTE, config.base_branch)
    heads = git.remote_heads(repo_root, url)
    if branch in heads:
        raise Stop(f"branch {branch} already exists on {REMOTE}", "close its pull request first")
    git.add_worktree(repo_root, worktree, branch, f"{REMOTE}/{config.base_branch}")
    return url, heads


def _describe(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, Stop):
        return exc.reason, exc.next_action
    return str(exc).splitlines()[0].rstrip(":"), "read the error above and retry"


class _TicketRun:
    def __init__(
        self,
        issue: Issue,
        config: Config,
        tracker: Tracker,
        runtime: AgentRuntime,
        environ: Mapping[str, str],
        worktree: Path,
        branch: str,
        url: str,
    ) -> None:
        self.issue = issue
        self.config = config
        self.tracker = tracker
        self.runtime = runtime
        self.environ = environ
        self.worktree = worktree
        self.branch = branch
        self.url = url
        self.number = issue.number
        self.folder = ticket.TicketFolder(ticket.folder_path(worktree, issue.number))

    def execute(self, heads_before: dict[str, str]) -> Outcome:
        try:
            setup_error = self._setup()
            self.folder.create(self.issue)
            self.folder.log(
                "Ticket started",
                f"Issue #{self.number} ({self.issue.url}), branch `{self.branch}` from"
                f" `{REMOTE}/{self.config.base_branch}`, working tree `{self.worktree}`.",
            )
            if setup_error is not None:
                raise setup_error
            self.folder.log("Setup", "No setup command." if not self.config.setup else "Passed.")
            self.folder.set_status("implementing", "implementer session running", "wait")
            self._commit_record(f"#{self.number}: open the ticket folder")
            start_commit = git.head(self.worktree)
            result = self._implement()
            self._verify_agent(start_commit, heads_before)
            self._commit_agent_work(start_commit, result)
            return self._check_and_deliver()
        except (Stop, git.GitError, TrackerError) as exc:
            return self._stopped(exc)

    def _setup(self) -> Stop | None:
        """Run the setup command (C8); an error is returned, journaled once the folder exists."""
        if not self.config.setup:
            return None
        command = self.config.setup
        try:
            done = process.run(command, cwd=self.worktree, timeout_s=SETUP_TIMEOUT_S)
        except process.CommandNotFoundError as exc:
            return Stop(f"setup failed: {exc}", "install it or fix project.setup")
        if not done.ok:
            status = "timed out" if done.timed_out else f"exit {done.returncode}"
            return Stop(
                f"setup `{' '.join(command)}` failed ({status})",
                "fix the setup command, then start the ticket again",
                f"```text\n{done.output.rstrip()}\n```",
            )
        leftovers = git.untracked(self.worktree)
        if leftovers:
            listing = "\n".join(f"- `{path}`" for path in leftovers)
            return Stop(
                "setup left files that git does not ignore",
                "add them to .gitignore, then start the ticket again",
                listing,
            )
        return None

    def _implement(self) -> SessionResult:
        agent = self.config.implementer
        git.guard_pushes(self.worktree)
        prompt = context.implementer_prompt(self.issue, self.branch, self.config.checks)
        env = context.agent_environment(
            self.environ, role="implementer", token_env=self.config.tracker.token_env
        )
        session = Session(
            role="implementer",
            model=agent.model,
            tools=agent.tools,
            max_budget_usd=agent.max_budget_usd,
            timeout_s=agent.timeout_minutes * 60,
            cwd=self.worktree,
            prompt=prompt,
            env=env,
        )
        self.folder.log(
            "Implementer session started",
            f"Runtime {self.runtime.name}, model {agent.model}, tools {', '.join(agent.tools)},"
            f" budget {agent.max_budget_usd:g} USD, time limit {agent.timeout_minutes:g} min.\n\n"
            f"Context given to the agent:\n\n````text\n{prompt}````",
        )
        result = self.runtime.run(session)
        cost = "not reported" if result.cost_usd is None else f"{result.cost_usd:.4f} USD"
        tokens = f"{result.input_tokens} in, {result.output_tokens} out"
        denials = "\n".join(f"- {d}" for d in result.permission_denials) or "none"
        self.folder.log(
            f"Implementer session stopped: {result.stop_reason.value}",
            f"Cost {cost} (as reported), tokens {tokens}.\n\nRefused tool calls:\n{denials}\n\n"
            f"Agent summary:\n\n````text\n{result.summary.rstrip()}\n````",
        )
        return result

    def _verify_agent(self, start_commit: str, heads_before: dict[str, str]) -> None:
        """C11: the agent did not switch branch, rewrite history or push."""
        branch = git.current_branch(self.worktree)
        if branch != self.branch:
            raise Stop(
                f"the agent left branch {self.branch} (now {branch or 'detached'})",
                "inspect the working tree; nothing was pushed by Ariane",
            )
        if not git.is_ancestor(self.worktree, start_commit, "HEAD"):
            raise Stop(
                "the agent rewrote the ticket branch's history",
                "inspect the working tree; nothing was pushed by Ariane",
            )
        for ref, sha in git.remote_heads(self.worktree, self.url).items():
            if heads_before.get(ref) == sha or not git.has_commit(self.worktree, sha):
                continue
            if not git.is_ancestor(self.worktree, sha, start_commit):
                raise Stop(
                    f"a commit made during the agent session was pushed to {ref}",
                    f"inspect and revert {ref} on {REMOTE}",
                )
        self.folder.log("Agent verified", "Same branch, history kept, no push.")

    def _commit_agent_work(self, start_commit: str, result: SessionResult) -> None:
        own = ticket.relative_folder(self.number) + "/"
        changed = [
            p for p in git.changed_paths(self.worktree, start_commit) if not p.startswith(own)
        ]
        if changed:
            git.commit_all(self.worktree, f"#{self.number}: {self.issue.title}")
            self.folder.log("Agent work committed", "\n".join(f"- `{p}`" for p in changed))
        if result.stop_reason is not StopReason.FINISHED:
            raise Stop(
                f"the implementer session stopped: {result.stop_reason.value}",
                f"read work/{self.number}/journal.md; its work is kept on the branch",
            )
        if not changed:
            raise Stop("the agent changed no file", "clarify the issue, then start again")

    def _check_and_deliver(self) -> Outcome:
        commit = git.head(self.worktree)
        results = checks.run_checks(self.config.checks, self.worktree)
        self.folder.write(ticket.CHECKS, checks.report(results, commit))
        self.folder.log(
            "Checks replayed by Ariane",
            checks.summary_table(results) + "\n\n" + checks.summary_line(results),
        )
        failed = checks.blocking_failures(results)
        if failed:
            names = ", ".join(r.name for r in failed)
            raise Stop(
                f"blocking checks failed: {names}",
                f"read work/{self.number}/checks.md in {self.worktree}",
            )
        self.folder.set_status("delivering", "checks green, pushing the branch", "wait")
        self._commit_record(f"#{self.number}: record the checks")
        git.push(self.worktree, self.url, self.branch)
        pull = self.tracker.open_pull_request(
            head=self.branch,
            base=self.config.base_branch,
            title=self.issue.title,
            body=self._pull_request_body(results),
        )
        self.folder.log("Delivered", f"Pull request #{pull.number}: {pull.url}")
        self.folder.set_status(
            "delivered", f"pull request {pull.url}", "review and merge the pull request"
        )
        self._commit_record(f"#{self.number}: record the delivery")
        git.push(self.worktree, self.url, self.branch)
        return Outcome(
            0,
            f"Opened pull request {pull.url} for issue #{self.number}, checks"
            " replayed green. Next: review and merge it.",
        )

    def _pull_request_body(self, results: list[checks.CheckResult]) -> str:
        report = f"{ticket.relative_folder(self.number)}/{ticket.CHECKS}"
        return (
            f"Closes #{self.number}\n\n"
            f"Implemented by an Ariane implementer session; checks replayed by Ariane.\n\n"
            f"{checks.summary_table(results)}\n\n{checks.summary_line(results)}\n\n"
            f"Full report: [{report}]({self.tracker.file_url(self.branch, report)}). "
            f"Journal: `{ticket.relative_folder(self.number)}/{ticket.JOURNAL}`.\n"
        )

    def _commit_record(self, message: str) -> None:
        folder = ticket.relative_folder(self.number)
        self.folder.restore()
        git.commit_paths(self.worktree, [folder], message)

    def _stopped(self, exc: Exception) -> Outcome:
        reason, next_action = _describe(exc)
        detail = exc.detail if isinstance(exc, Stop) else str(exc)
        if self.folder.path.exists():
            self.folder.log(f"Stopped: {reason}", detail)
            self.folder.set_status("stopped", reason, next_action)
            # If this commit fails, the reason is still in the working tree's files.
            with contextlib.suppress(git.GitError):
                self._commit_record(f"#{self.number}: record the stop")
        return Outcome(1, f"Stopped ticket #{self.number}: {reason}. Next: {next_action}.", detail)
