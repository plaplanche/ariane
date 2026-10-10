"""`ariane start`: one issue becomes a pull request whose checks Ariane replayed (ADR 0006)."""

from __future__ import annotations

import contextlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ariane import checks, context, git, logs, process, review, ticket
from ariane.config import CheckConfig, Config
from ariane.delivery import FAILURES, Delivery, PullRequestRefused
from ariane.redact import redact
from ariane.review_session import ReviewFailed, ReviewSession
from ariane.runtime import AgentRuntime, Session, SessionResult, StopReason
from ariane.tracker import Issue, Tracker, TrackerError

REMOTE = "origin"
SETUP_TIMEOUT_S = 30 * 60
EXIT_OK = 0
EXIT_STOPPED = 1
MAX_FIX_ROUNDS = 2
_FAILURES = FAILURES


@dataclass(frozen=True)
class Outcome:
    exit_code: int
    line: str  # what was done, then the next possible action (C23)
    detail: str = ""  # shown before the line, for example a failing setup's output


QUIET = "nobody runs git commands in the repository or pushes to it while a ticket runs"


class Stop(Exception):
    """The ticket stops here; `reason` and `next_action` go to the user and the journal."""

    def __init__(
        self, reason: str, next_action: str, detail: str = "", status: str = "stopped"
    ) -> None:
        super().__init__(reason)
        self.status = status
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
        return Outcome(EXIT_STOPPED, f"Did not start #{number}: {exc}. Next: check the number.")
    branch = branch_name(number)
    worktree = worktree_path(repo_root, number)
    try:
        url, refs_before = _prepare(repo_root, config, branch, worktree)
        run = _TicketRun(issue, config, tracker, runtime, environ, worktree, branch, url)
    except (Stop, *_FAILURES) as exc:
        reason, next_action = _describe(exc)
        return Outcome(
            EXIT_STOPPED, f"Did not start ticket #{number}: {reason}. Next: {next_action}."
        )
    return run.execute(refs_before)


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
    refs = git.remote_refs(repo_root, url)
    if f"refs/heads/{branch}" in refs:
        raise Stop(
            f"branch {branch} already exists on {REMOTE}",
            "close its pull request and delete the branch, then start again",
        )
    git.add_worktree(repo_root, worktree, branch, f"{REMOTE}/{config.base_branch}")
    return url, refs


def _token(environ: Mapping[str, str], token_env: str) -> str:
    name = token_env.upper()
    return next((v for k, v in environ.items() if k.upper() == name and v), "")


def _describe(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, Stop):
        return exc.reason, exc.next_action
    first = str(exc).splitlines()[0].rstrip(":") if str(exc) else type(exc).__name__
    return first, "read the error above and retry"


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
        self.not_updated: list[str] = []
        self.secrets = context.known_secrets(environ, config.tracker.token_env)
        self.folder = ticket.TicketFolder(worktree, issue.number, secrets=self.secrets)
        remotes = git.remotes(worktree)
        token_env = config.tracker.token_env
        # Agent sessions and anything running code an agent wrote get no credential.
        self.agent_env = context.untrusted_environment(
            environ, token_env=token_env, remotes=remotes, login_variables=runtime.login_variables
        )
        self.untrusted_env = context.untrusted_environment(
            environ, token_env=token_env, remotes=remotes
        )

    def execute(self, refs_before: dict[str, str]) -> Outcome:
        try:
            setup_error = self._setup(self.worktree)
            self.folder.create(self.issue)
            self.folder.log(
                "ticket.started",
                "Ticket started",
                f"Issue #{self.number} ({self.issue.url}), branch `{self.branch}` from"
                f" `{REMOTE}/{self.config.base_branch}`, working tree `{self.worktree}`.",
            )
            if setup_error is not None:
                raise setup_error
            self.folder.log(
                "ticket.setup", "Setup", "No setup command." if not self.config.setup else "Passed."
            )
            self.folder.set_status("implementing", "implementer session running", "wait")
            self._commit_record(f"#{self.number}: open the ticket folder")
            start_commit = git.head(self.worktree)
            guard = git.config_snapshot(self.worktree, ignore_ref=self.branch)
            ignored_before = git.ignored(self.worktree)
            result = self._implement()
            self._verify("the agent session", start_commit, guard, refs_before)
            self._warn_ignored(ignored_before)
            self._commit_agent_work(start_commit, result)
            return self._check_and_deliver(start_commit, guard, refs_before)
        except (Stop, *_FAILURES) as exc:
            return self._stopped(exc)

    def _setup(self, cwd: Path) -> Stop | None:
        """Run the setup command (C8) in `cwd` without credentials (it may run agent-written code).

        An error is journaled once the folder exists.
        """
        if not self.config.setup:
            return None
        command = self.config.setup
        try:
            done = process.run(command, cwd=cwd, timeout_s=SETUP_TIMEOUT_S, env=self.untrusted_env)
        except process.CommandNotFoundError as exc:
            return Stop(f"setup failed: {exc}", "install it or fix project.setup")
        if not done.ok:
            status = "timed out" if done.timed_out else f"exit {done.returncode}"
            return Stop(
                f"setup `{' '.join(command)}` failed ({status})",
                "fix the setup command, then start the ticket again",
                ticket.fenced(done.output),
            )
        leftovers = git.untracked(cwd)
        if leftovers:
            listing = "\n".join(f"- `{path}`" for path in leftovers)
            return Stop(
                "setup left files that git does not ignore",
                "add them to .gitignore, then start the ticket again",
                listing,
            )
        return None

    def _implement(self, fix_round: int = 0, findings: str = "") -> SessionResult:
        """The implementer session, or the fresh session of fix round `fix_round` (C10)."""
        agent = self.config.implementer
        done = self.config.definition_of_done
        docs = self.config.documentation
        args = (self.issue, self.branch, self.config.checks, done, docs)
        prompt = context.implementer_prompt(*args, fix_round=fix_round, findings=findings)
        recorded = context.implementer_prompt(
            *args, fix_round=fix_round, findings=findings, recorded=True, read_at=ticket.now()
        )
        name = f"Fix session {fix_round}" if fix_round else "Implementer session"
        tokens_cap = "none" if agent.max_tokens is None else f"{agent.max_tokens} tokens"
        session = Session(
            role="implementer",
            model=agent.model,
            tools=agent.tools,
            max_budget_usd=agent.max_budget_usd,
            max_tokens=agent.max_tokens,
            timeout_s=agent.timeout_minutes * 60,
            cwd=self.worktree,
            prompt=prompt,
            env=self.agent_env,
        )
        self.folder.log(
            "ticket.session.started",
            f"{name} started",
            f"Runtime {self.runtime.name}, model {agent.model}, tools {', '.join(agent.tools)},"
            f" runtime cost cap {agent.max_budget_usd:g} USD, Ariane token cap {tokens_cap},"
            f" time limit {agent.timeout_minutes:g} min.\n\n"
            f"Context given to the agent:\n\n{ticket.fenced(recorded)}",
        )
        result = self.runtime.run(session)
        cost, tokens = result.usage()
        denials = "\n".join(f"- {d}" for d in result.permission_denials) or "none"
        cap = f"Cap reached: {result.cap}.\n\n" if result.cap else ""
        self.folder.log(
            "ticket.session.stopped",
            f"{name} stopped: {result.stop_reason.value}",
            f"{cap}Cost {cost} (as reported), tokens {tokens}.\n\n"
            f"Refused tool calls:\n{denials}\n\n"
            f"Agent summary:\n\n{ticket.fenced(result.summary)}",
        )
        return result

    def _verify(
        self,
        after: str,
        start_commit: str,
        guard: dict[str, str],
        refs_before: dict[str, str],
        expected_head: str | None = None,
    ) -> None:
        """C11: after untrusted code ran, nothing escaped the ticket branch."""
        keep = "inspect the working tree; Ariane pushed nothing"
        branch = git.current_branch(self.worktree)
        if branch != self.branch:
            raise Stop(f"{after} left branch {self.branch} (now {branch or 'detached'})", keep)
        if not git.is_ancestor(self.worktree, start_commit, "HEAD"):
            raise Stop(f"{after} rewrote the ticket branch's history", keep)
        if expected_head is not None and git.head(self.worktree) != expected_head:
            raise Stop(f"{after} moved the ticket branch", keep)
        changes = git.snapshot_changes(
            guard, git.config_snapshot(self.worktree, ignore_ref=self.branch)
        )
        if changes:
            raise Stop(
                f"{after} changed git configuration, hooks or local branches",
                f"inspect .git/config, .git/hooks and the branches; Ariane pushed nothing; {QUIET}",
                "\n".join(f"- {line}" for line in changes),
            )
        changed = self._remote_changes(refs_before)
        if changed:
            raise Stop(
                f"the remote changed during {after} ({', '.join(changed)})",
                f"check it was not the agent; if a person pushed, start the ticket again; {QUIET}",
            )
        logs.emit("guard.verified", f"after {after}: branch, history, git and remote unchanged")
        self.folder.log(
            "ticket.guard.verified",
            f"Verified after {after}",
            "Same branch and history, git unchanged, remote unchanged.",
        )

    def _remote_changes(self, refs_before: dict[str, str]) -> list[str]:
        """Refs that differ from the start, except a fast-forward of the base branch (a merge)."""
        refs = git.remote_refs(self.worktree, self.url)
        base = f"refs/heads/{self.config.base_branch}"
        changed = sorted(r for r in {*refs, *refs_before} if refs.get(r) != refs_before.get(r))
        if (
            base in changed
            and base in refs
            and base in refs_before
            and git.fast_forwarded(
                self.worktree, REMOTE, self.config.base_branch, refs_before[base], refs[base]
            )
        ):
            changed.remove(base)
        return changed

    def _warn_ignored(self, before: set[str]) -> None:
        """Ignored files the agent created can make checks pass without being delivered."""
        new = sorted(git.ignored(self.worktree) - before)
        if new:
            self.folder.log(
                "ticket.warning.ignored_files",
                "Warning: new files ignored by git",
                "The checks see them but the pull request does not carry them:\n"
                + "\n".join(f"- `{p}`" for p in new),
            )

    def _fix(
        self,
        round_: int,
        start_commit: str,
        guard: dict[str, str],
        refs_before: dict[str, str],
        findings: str,
    ) -> None:
        """C10: a fresh implementer session fixes the findings in the ticket's working tree."""
        self.folder.set_status("implementing", f"fix round {round_} running", "wait")
        self.folder.log(
            "ticket.fix.round",
            f"Fix round {round_} began",
            f"Findings given to the fix session (data from the reviewer):\n\n"
            f"{ticket.fenced(findings)}",
        )
        ignored_before = git.ignored(self.worktree)
        result = self._implement(round_, findings)
        self._verify(f"fix session {round_}", start_commit, guard, refs_before)
        self._warn_ignored(ignored_before)
        self._commit_agent_work(start_commit, result, f"#{self.number}: fix round {round_}")

    def _commit_agent_work(
        self, start_commit: str, result: SessionResult, message: str = ""
    ) -> None:
        # This ticket's own folder is rewritten by Ariane anyway (an agent's `git commit -a`
        # picks up Ariane's journal); other tickets' records must stay untouched.
        own = ticket.relative_folder(self.number) + "/"
        records = [
            p
            for p in git.committed_paths(self.worktree, start_commit, ticket.WORK_DIR)
            if not p.startswith(own)
        ]
        if records:
            raise Stop(
                f"the agent committed changes to ticket records ({', '.join(records)})",
                "inspect the branch; Ariane pushed nothing",
            )
        changed = [
            p
            for p in git.changed_paths(self.worktree, start_commit)
            if not p.startswith(ticket.WORK_DIR + "/")
        ]
        exclude = f":(exclude){ticket.WORK_DIR}"
        if git.commit(
            self.worktree,
            [".", exclude],
            redact(message or f"#{self.number}: {self.issue.title}", self.secrets),
            env=self.untrusted_env,
        ):
            self.folder.log(
                "ticket.work.committed",
                "Agent work committed",
                "\n".join(f"- `{p}`" for p in changed),
            )
        self._flag_untouched_docs(changed)
        if result.stop_reason is not StopReason.FINISHED:
            raise Stop(
                f"the implementer session stopped: {result.stop_reason.value}",
                f"read work/{self.number}/journal.md; its work is kept on the branch",
            )
        if not changed:
            raise Stop("the agent changed no file", "clarify the issue, then start again")

    def _flag_untouched_docs(self, changed: list[str]) -> None:
        """C25: journal the documents mapped to changed files that the ticket did not change."""
        missing = self.config.documentation.not_updated(changed)
        self.not_updated = missing
        if missing:
            self.folder.log(
                "ticket.docs.not_updated",
                "Documentation not updated",
                "Documents covering changed files that the ticket left untouched:\n"
                + "\n".join(f"- `{d}`" for d in missing),
            )

    def _check_and_deliver(
        self, start_commit: str, guard: dict[str, str], refs_before: dict[str, str]
    ) -> Outcome:
        """C10: replay the checks and review; after a `no-go` (or blocking checks failing after
        a fix round) up to two fix rounds, then deliver, as a draft if still `no-go`."""
        settled: review.Settled | None = None
        reviewed = 0
        failed: list[checks.CheckResult] = []
        for round_ in range(MAX_FIX_ROUNDS + 1):
            if round_:
                self._fix(
                    round_, start_commit, guard, refs_before, review.fix_feedback(settled, failed)
                )
            checked = git.head(self.worktree)
            replay, results = self._replay(checked, start_commit, guard, refs_before)
            try:
                self.folder.write(ticket.CHECKS, checks.report(results, checked))
                self.folder.log(
                    "ticket.checks.replayed",
                    "Checks replayed by Ariane",
                    checks.summary_table(results) + "\n\n" + checks.summary_line(results),
                )
                failed = checks.blocking_failures(results)
                if failed and not round_:
                    names = ", ".join(r.name for r in failed)
                    raise Stop(
                        f"blocking checks failed: {names}",
                        f"read work/{self.number}/checks.md in {self.worktree}",
                    )
                if not failed:
                    reviewed = round_
                    args = (replay, checked, start_commit, guard, refs_before, results, round_)
                    settled = self._review(*args)
            finally:
                self._remove_replay(replay)
            if settled is not None and settled.go and not failed:
                break
        delivery = Delivery(
            self.issue,
            self.tracker,
            self.folder,
            self.worktree,
            self.branch,
            self.config.base_branch,
            self.url,
            self._commit_record,
            self.secrets,
            _token(self.environ, self.config.tracker.token_env),
            self.environ,
            checked,
            settled,
            reviewed,
        )
        try:
            done = delivery.deliver(results)
        except PullRequestRefused as exc:
            raise Stop(exc.reason, exc.next_action) from None
        if done.draft:
            return Outcome(
                EXIT_STOPPED,
                f"Opened draft pull request {done.pull_url} for issue #{self.number}: the review"
                f" is still no-go after {MAX_FIX_ROUNDS} fix rounds. Next: finish by hand, then"
                " run `ariane verify`.",
            )
        return Outcome(
            EXIT_OK,
            f"Opened pull request {done.pull_url} for issue #{self.number}, checks replayed green,"
            " review go. Next: review and merge it.",
        )

    def _all_checks(self) -> tuple[CheckConfig, ...]:
        return (*self.config.checks, *self.config.documentation.checks())

    def _replay(
        self, checked: str, start_commit: str, guard: dict[str, str], refs_before: dict[str, str]
    ) -> tuple[Path, list[checks.CheckResult]]:
        """C9: set up and run every check in a clean working tree at the delivered commit.

        The tree is kept for the reviewer; the caller removes it."""
        replay = self.worktree.with_name(f"{self.number}-replay")
        if replay.exists():
            raise Stop(
                f"the replay working tree already exists at {replay}", "remove it, then retry"
            )
        git.add_detached_worktree(self.worktree, replay, checked)
        try:
            self.folder.log(
                "ticket.checks.worktree",
                "Checks working tree",
                f"Setup and checks run in a clean working tree `{replay}` at `{checked}`,"
                f" not in `{self.worktree}`.",
            )
            setup_error = self._setup(replay)
            if setup_error is not None:
                raise setup_error
            results = checks.run_checks(self._all_checks(), replay, self.untrusted_env)
            if git.current_branch(replay) or git.head(replay) != checked:
                raise Stop("the checks moved the replay working tree's head", "inspect it")
            self._verify("the checks", start_commit, guard, refs_before, expected_head=checked)
        except BaseException:
            self._remove_replay(replay)
            raise
        return replay, results

    def _review(
        self,
        replay: Path,
        checked: str,
        start_commit: str,
        guard: dict[str, str],
        refs_before: dict[str, str],
        results: list[checks.CheckResult],
        round_: int,
    ) -> review.Settled:
        """C10, C26: review `round_` in the replay tree; the record is `review-<round>.md`."""
        diff = git.diff(self.worktree, start_commit, checked, ticket.WORK_DIR)
        tree_before = git.status(replay)

        def after_session() -> None:
            self._verify("the reviewer", start_commit, guard, refs_before, expected_head=checked)
            self._verify_replay(replay, checked, tree_before)

        sessions = ReviewSession(
            self.runtime,
            self.config.reviewer,
            self.folder,
            self.issue,
            self.agent_env,
            self._all_checks(),
            self.config.definition_of_done,
        )
        try:
            answer = sessions.run(replay, checked, diff, results, self.not_updated, after_session)
        except ReviewFailed as exc:
            raise Stop(exc.reason, exc.next_action, exc.detail, status="needs a human") from None
        settled = review.settle(answer, self.config.definition_of_done, results)
        model = self.config.reviewer.model
        self.folder.write(
            ticket.review_file(round_), review.record(settled, checked, model, round_)
        )
        self.folder.log(
            "ticket.review.verdict",
            f"Review {round_}: {settled.verdict}",
            review.findings_table(settled),
        )
        return settled

    def _verify_replay(self, replay: Path, checked: str, tree_before: str) -> None:
        """The reviewer reads only: the replay tree has the same head and no edited file."""
        if git.current_branch(replay) or git.head(replay) != checked:
            raise Stop("the reviewer moved the replay working tree's head", "inspect it")
        if git.status(replay) != tree_before:
            raise Stop(
                "the reviewer changed files in the working tree",
                "inspect the review session; Ariane pushed nothing",
                status="needs a human",
            )

    def _remove_replay(self, replay: Path) -> None:
        try:
            git.remove_worktree(self.worktree, replay)
        except _FAILURES as exc:
            self.folder.log(
                "ticket.warning.replay_not_removed",
                "Warning: replay working tree not removed",
                f"`{replay}`: {exc}",
            )

    def _commit_record(self, message: str) -> None:
        self.folder.restore()
        folder = ticket.relative_folder(self.number)
        git.commit(self.worktree, [folder], redact(message, self.secrets), env=self.untrusted_env)

    def _stopped(self, exc: BaseException) -> Outcome:
        reason, next_action = _describe(exc)
        detail = exc.detail if isinstance(exc, Stop) else str(exc)
        logs.emit("run.stopped", f"ticket #{self.number}: {reason}")
        if self.folder.exists():
            # Recording the stop must not hide the reason: report it even if this fails.
            with contextlib.suppress(*_FAILURES):
                self.folder.log("ticket.stopped", f"Stopped: {reason}", detail)
                status = exc.status if isinstance(exc, Stop) else "stopped"
                self.folder.set_status(status, reason, next_action)
                self._commit_record(f"#{self.number}: record the stop")
        return Outcome(
            EXIT_STOPPED, f"Stopped ticket #{self.number}: {reason}. Next: {next_action}.", detail
        )
