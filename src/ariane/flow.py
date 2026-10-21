"""`ariane start`: one issue becomes a pull request whose checks Ariane replayed (ADR 0006)."""

from __future__ import annotations

import contextlib
import functools
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from ariane import checks, context, git, logs, process, replay, review, review_session, runs, ticket
from ariane.config import CheckConfig, Config
from ariane.delivery import FAILURES, Delivery, PullRequestRefused
from ariane.full_replay import after_delivery
from ariane.metrics import METRICS, Metrics, keep_refused, stopped_metrics_path
from ariane.redact import redact
from ariane.restart import Restarted, kept_name, lock_path, locked, prepare, with_restart
from ariane.review_history import Round, feedback
from ariane.risk import Tier
from ariane.runtime import AgentRuntime, SessionResult, StopReason, for_role, session_for
from ariane.slots import held as held_slot
from ariane.stop import CHECKS, GUARD, SPEC, Stop, category_of, describe
from ariane.tracker import Issue, Tracker, TrackerError

REMOTE = "origin"
SETUP_TIMEOUT_S = 30 * 60
EXIT_OK = 0
EXIT_STOPPED = 1
EXIT_INTERRUPTED = 130
MAX_FIX_ROUNDS = 2
_FAILURES = FAILURES
_Env = Mapping[str, str] | None  # a parallel check's environment, with its own slot


@dataclass(frozen=True)
class Outcome:
    exit_code: int
    line: str  # what was done, then the next possible action (C23)
    detail: str = ""  # shown before the line, for example a failing setup's output


QUIET = "only Ariane runs git commands in the repository or pushes to it while a ticket runs"


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
    restarting: bool = False,
) -> Outcome:
    try:
        issue = runs.read_issue(tracker, number)
    except TrackerError as exc:
        keep_refused(worktree_path(repo_root, number), number, exc)  # the gate's refusal: `spec`
        return Outcome(exc.exit_code, f"Did not start #{number}: {exc}. Next: {exc.next_action}.")
    except KeyboardInterrupt as exc:
        keep_refused(worktree_path(repo_root, number), number, exc)  # an interrupt: `infra`
        return _interrupted_before_start(number)
    branch = branch_name(number)
    worktree = worktree_path(repo_root, number)
    with contextlib.ExitStack() as registry:  # the entry goes however the run ends (C11)
        try:
            registry.enter_context(locked(lock_path(repo_root, number), number))
            slot = registry.enter_context(held_slot())  # to the run's end (ADR 0050)
            kept = kept_name(number) if restarting else ""  # registered before the rename
            registry.enter_context(runs.registered(runs.folder(repo_root), number, branch, kept))
            witnessed = registry.enter_context(runs.watching(runs.folder(repo_root)))
            url, refs_before, instructions, restarted = prepare(
                repo_root, config.base_branch, branch, worktree, kept
            )
            run = _TicketRun(issue, config, tracker, runtime, environ, worktree, branch, url, slot)
            run.base_instructions = instructions
            run.restarted = restarted
            run.witnessed = witnessed
        except (Stop, KeyboardInterrupt, *_FAILURES) as exc:
            keep_refused(worktree, number, exc)  # lock, slot, registry or preparation: `infra`
            reason, next_action = describe(exc)
            left = worktree.exists() or git.local_branch_exists(repo_root, branch)
            if left and not isinstance(exc, Stop):  # a preparation interrupted after creating them
                next_action = with_restart(next_action, number)
            code = EXIT_INTERRUPTED if isinstance(exc, KeyboardInterrupt) else EXIT_STOPPED
            return Outcome(code, f"Did not start ticket #{number}: {reason}. Next: {next_action}.")
        return run.execute(refs_before)


def _interrupted_before_start(number: int) -> Outcome:
    """Ctrl-C before the ticket folder exists: nothing to record, one line, exit 130."""
    reason, next_action = describe(KeyboardInterrupt())
    line = f"Did not start ticket #{number}: {reason}. Next: {next_action}."
    return Outcome(EXIT_INTERRUPTED, line)


class _TicketRun:
    remote = REMOTE
    restartable = True  # a stop names `--restart` unless the branch was pushed (ADR 0047)
    updating = ""  # the base an update merges: the prompts say so (ADR 0033)

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
        slot: int,
    ) -> None:
        self.issue = issue
        self.slot = slot
        self.config = config
        self.tracker = tracker
        self.runtime = runtime
        self.environ = environ
        self.worktree = worktree
        self.branch = branch
        self.url = url
        self.number = issue.number
        self.base_instructions = ""
        self.residuals = review.residuals_in(worktree)  # the tree is the base commit (ADR 0057)
        self.restarted: Restarted | None = None
        self.pushed = False  # this run pushed the branch: it is never restarted (ADR 0047)
        self.not_updated: list[str] = []
        self.changed: list[str] = []
        self.truncated: list[str] = []  # the files whose hunks the last reviewed diff lacked
        self.reviews: list[Round] = []  # the reviewed rounds, for the next ones (ADR 0059)
        self.changes: dict[str, git.Changes] = {}  # per replayed commit, from the start commit
        self.tier: Tier | None = None  # the last replayed round's risk tier (ADR 0056)
        self.check_failed = False  # a replayed round failed a check: later rounds are high
        self.processes_before: set[int] = set()
        self.registry = worktree.parent.parent / runs.FOLDER  # `runs.folder` of the repository
        self.witnessed: dict[int, runs.Run] = {}  # the other runs this run has seen live
        # Parallel checks share the guard: each reads git, compares and advances it in turn.
        self.guard_lock = threading.RLock()
        self.secrets = context.known_secrets(environ, config.tracker.token_env)
        self.folder = ticket.TicketFolder(worktree, issue.number, secrets=self.secrets)
        self.metrics = Metrics(issue.number, "delivered", lambda t: self.folder.write(METRICS, t))
        # Agent sessions and anything running code an agent wrote get an allow list (ADR 0024).
        untrusted = functools.partial(
            context.untrusted_environment,
            environ,
            token_env=config.tracker.token_env,
            remotes=git.remotes(worktree),
            declared=config.env,
            slot=slot,
        )
        logins = review_session.agent_logins(runtime, config.implementer, config.reviewer)
        self.agent_envs = {kind: untrusted(login_variables=names) for kind, names in logins.items()}
        self.untrusted_env = untrusted()

    def execute(self, refs_before: dict[str, str]) -> Outcome:
        try:
            self.processes_before = set(process.descendants(exited=True))
            if self.restarted is not None:
                self.metrics.restarted_from = self.restarted.metrics()
            # Taken before the setup: instruction files it writes are not part of the baseline.
            self.guard_since = runs.now()  # other runs active since may touch their branches
            guard = self.state().snapshot
            cached, setup_error = replay.set_up_ticket_tree(self, guard)
            self.folder.create(self.issue)
            if self.restarted is not None:  # the journal opens with it (ADR 0047)
                text = self.restarted.journal(self.number)
                self.folder.log("ticket.restarted", "Ticket started over", text)
            self.metrics.step("folder opened")
            self.folder.log(
                "ticket.started",
                "Ticket started",
                f"Issue #{self.number} ({self.issue.url}), branch `{self.branch}` from"
                f" `{self.remote}/{self.config.base_branch}`, working tree `{self.worktree}`,"
                f" slot {self.slot} (`{context.SLOT_VARIABLE}`).",
            )
            env, token_env = self.config.env, self.config.tracker.token_env
            if note := context.declared_secrets(self.environ, env, token_env):
                self.folder.log("ticket.env.declared_secret", "Declared secrets passed", note)
            if setup_error is not None:
                raise setup_error
            text = "No setup command." if not self.config.setup else "Passed."
            self.folder.log("ticket.setup", "Setup", text + cached)
            self.folder.set_status("implementing", "implementer session running", "wait")
            self._commit_record(f"#{self.number}: open the ticket folder")
            start_commit = self.start_commit = git.head(self.worktree)
            ignored_before = git.ignored(self.worktree)
            result = self._implement()
            self.verify("the agent session", start_commit, guard, refs_before)
            self._warn_ignored(ignored_before)
            self._commit_agent_work(start_commit, result)
            return self._check_and_deliver(start_commit, guard, refs_before)
        except (Stop, KeyboardInterrupt, *_FAILURES) as exc:
            return self._stopped(exc)

    def state(self) -> git.GitState:
        """The guard's view of git (configuration, hooks, refs, the base's tracking ref), of the
        instruction files the reviewer can load outside its tree (ADR 0031), branch and head."""
        reviewer_tree = self.worktree.with_name(f"{self.number}-review")
        read = git.state(
            self.worktree,
            ignore_ref=self.branch,
            watch_refs=[f"refs/remotes/{self.remote}/{self.config.base_branch}"],
        )
        instructions = git.instruction_snapshot(
            review_session.instruction_dirs(reviewer_tree),
            self.config.reviewer.runtime,
            self.agent_envs["reviewer"],
        )
        return git.GitState(read.snapshot | instructions, read.branch, read.head)

    def survivors(self, after: str) -> Stop | None:
        """Kill the processes `after` left running (C10, ADR 0031); they are counted in
        `metrics.json` and stop the ticket as a guard violation."""
        process.kill_survivors(self.processes_before)
        killed = process.take_killed()  # with those each command's own teardown killed
        if not killed:
            return None
        self.metrics.surviving_processes(len(killed))
        return runs.survivors_stop(after, killed)

    def setup(
        self, cwd: Path, command: tuple[str, ...] | None, guard: dict[str, str], env: _Env = None
    ) -> Stop | None:
        """Run the setup command (C8) in `cwd` in `env` or the run's, without credentials (it may
        run agent-written code), then, before anything else runs, compare git and the instruction
        files to `guard` (ADR 0031); an error is journaled once the folder exists."""
        if not command:
            return None
        try:
            env = self.untrusted_env if env is None else env
            done = process.run(command, cwd=cwd, timeout_s=SETUP_TIMEOUT_S, env=env)
        except process.CommandNotFoundError as exc:
            return Stop(f"setup failed: {exc}", "install it or fix project.setup")
        survived = self.survivors(f"setup `{' '.join(command)}`") or self._unchanged("setup", guard)
        if survived is not None:
            self.metrics.guard_violation()
            return survived
        if not done.ok:
            status = "timed out" if done.timed_out else f"exit {done.returncode}"
            return Stop(
                f"setup `{' '.join(command)}` failed ({status})",
                "fix the setup command, then start the ticket again",
                ticket.fenced(done.output),
            )
        if leftovers := git.untracked(cwd):
            listing = "\n".join(f"- `{path}`" for path in leftovers)
            return Stop(
                "setup left files that git does not ignore",
                "add them to .gitignore, then start the ticket again",
                listing,
            )
        return None

    def _implement(self, fix_round: int = 0, findings: str = "", task: str = "") -> SessionResult:
        """The implementer session, a fix round's (C10), or an update's for `task` (ADR 0033)."""
        agent = self.config.implementer
        done = self.config.definition_of_done
        docs = self.config.documentation
        args = (self.issue, self.branch, self.config.checks, done, docs)
        made = functools.partial(context.implementer_prompt, *args, update=self.updating, task=task)
        prompt = made(fix_round=fix_round, findings=findings)
        recorded = made(fix_round=fix_round, findings=findings, recorded=True, read_at=ticket.now())
        name = f"Fix session {fix_round}" if fix_round else "Update session" if task else ""
        name = name or "Implementer session"
        tokens_cap = "none" if agent.max_tokens is None else f"{agent.max_tokens} tokens"
        env = self.agent_envs["implementer"]
        session = session_for(agent, "implementer", cwd=self.worktree, prompt=prompt, env=env)
        self.folder.log(
            "ticket.session.started",
            f"{name} started",
            f"Runtime {for_role(self.runtime, session.role).name}, model {agent.model}, tools"
            f" {', '.join(agent.tools)},"
            f" runtime cost cap {agent.max_budget_usd:g} USD, Ariane token cap {tokens_cap},"
            f" time limit {agent.timeout_minutes:g} min.\n\n"
            f"Context given to the agent:\n\n{ticket.fenced(recorded)}",
        )
        result = self.metrics.run_session(for_role(self.runtime, session.role), session, fix_round)
        denials = "\n".join(f"- {d}" for d in result.permission_denials) or "none"
        self.folder.log(
            "ticket.session.stopped",
            f"{name} stopped: {result.stop_reason.value}",
            f"{result.usage_text()}\n\n"
            f"Refused tool calls:\n{denials}\n\n"
            f"Agent summary:\n\n{ticket.fenced(result.summary)}",
        )
        return result

    def verify(
        self,
        after: str,
        start_commit: str,
        guard: dict[str, str],
        refs_before: dict[str, str],
        expected_head: str | None = None,
    ) -> None:
        """C11: after untrusted code ran, nothing escaped the ticket branch (violations counted).
        Git is read once (`state`, ADR 0053)."""
        try:
            keep = "inspect the working tree; Ariane pushed nothing"
            survived = self.survivors(after)
            if survived is not None:
                raise survived
            with self.guard_lock:  # no other check advances the guard past this snapshot
                now = self.state()
                if (branch := now.branch) != self.branch:
                    detached = branch or "detached"
                    raise Stop(f"{after} left branch {self.branch} (now {detached})", keep)
                # Every time: the shallow file or a replacement ref can change a commit's ancestry.
                if not git.is_ancestor(self.worktree, start_commit, now.head):
                    raise Stop(f"{after} rewrote the ticket branch's history", keep)
                if expected_head is not None and now.head != expected_head:
                    raise Stop(f"{after} moved the ticket branch", keep)
                stopped = self._unchanged(after, guard, now.snapshot)
            if stopped is None and (changed := self._remote_changes(refs_before)):
                stopped = runs.remote_stop(after, changed, QUIET)
            if stopped is not None:
                raise stopped
        except Stop as exc:
            self.metrics.guard_violation()
            exc.category = GUARD  # every stop of the post-session check (ADR 0058)
            raise
        logs.emit("guard.verified", f"after {after}: branch, history, git and remote unchanged")
        self.folder.log(
            "ticket.guard.verified",
            f"Verified after {after}",
            "Same branch and history, git unchanged, remote unchanged.",
        )

    def _unchanged(
        self, after: str, guard: dict[str, str], now: dict[str, str] | None = None
    ) -> Stop | None:
        """The stop when git or the reviewer's instruction files differ from `guard`, apart from
        another run's own branch, its branch keys and its kept branch (C11, ADR 0017, ADR 0047),
        and a fast-forward of the base's tracking ref to the remote's base (ADR 0055).
        Git is read first: a run registers before its git writes, so any it shows is in `during`;
        under `guard_lock` until `guard` advanced, so no parallel check compares an older read."""
        with self.guard_lock:
            now = self.state().snapshot if now is None else now
            others = runs.during(self.registry, self.guard_since, self.witnessed) - {self.number}
            changes = runs.foreign_changes(
                guard, now, others, runs.kept_branches(self.witnessed, others)
            )
            tracking = f"refs/remotes/{self.remote}/{self.config.base_branch}"
            changes = runs.tracking_fast_forward(
                self.worktree, guard, now, changes, tracking, self._remote_base
            )
        return runs.guard_stop(after, changes, QUIET)

    def _remote_base(self) -> str:
        """The commit the remote's base branch points to now ("" when it has none)."""
        refs = git.remote_refs(self.worktree, self.url)
        return refs.get(f"refs/heads/{self.config.base_branch}", "")

    def _remote_changes(self, refs_before: dict[str, str]) -> list[str]:
        return git.remote_changes(
            self.worktree, self.url, REMOTE, self.branch, self.config.base_branch, refs_before
        )

    def _warn_ignored(self, before: set[str]) -> None:
        """Ignored files the agent created can make checks pass without being delivered."""
        if new := sorted(git.ignored(self.worktree) - before):
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
    ) -> bool:
        """C10: a fresh implementer session fixes the findings in the ticket's working tree;
        False when the round left the head where it was: nothing to replay or review."""
        self.metrics.fix_round(round_)
        self.folder.set_status("implementing", f"fix round {round_} running", "wait")
        self.folder.log(
            "ticket.fix.round",
            f"Fix round {round_} began",
            f"Findings given to the fix session (data from the reviewer):\n\n"
            f"{ticket.fenced(findings)}",
        )
        ignored_before = git.ignored(self.worktree)
        head_before = git.head(self.worktree)
        result = self._implement(round_, findings)
        self.verify(f"fix session {round_}", start_commit, guard, refs_before)
        self._warn_ignored(ignored_before)
        self._commit_agent_work(start_commit, result, f"#{self.number}: fix round {round_}")
        if git.head(self.worktree) != head_before:
            return True
        self.metrics.unchanged_fix_round()
        self.folder.log(
            "ticket.fix.unchanged",
            f"Fix round {round_} changed nothing",
            f"The fix session's summary (data from the agent):\n\n{ticket.fenced(result.summary)}",
        )
        return False

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
                category=GUARD,
            )
        changed = [
            p
            for p in git.changed_paths(self.worktree, start_commit)
            if not p.startswith(ticket.WORK_DIR + "/")
        ]
        exclude = f":(exclude){ticket.WORK_DIR}"
        message = redact(message or f"#{self.number}: {self.issue.title}", self.secrets)
        if git.commit(self.worktree, [".", exclude], message, env=self.untrusted_env):
            listing = "\n".join(f"- `{p}`" for p in changed)
            self.folder.log("ticket.work.committed", "Agent work committed", listing)
        self.changed = changed
        self._flag_untouched_docs(changed)
        if result.stop_reason is not StopReason.FINISHED:
            raise Stop(
                f"the implementer session stopped: {result.stop_text()}",
                f"read work/{self.number}/journal.md; its work is kept on the branch",
                category=result.stop_category(),
            )
        if not changed:
            raise Stop(
                "the agent changed no file", "clarify the issue, then start again", category=SPEC
            )

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
        reviewed = unchanged = 0
        failed: list[checks.CheckResult] = []
        for round_ in range(MAX_FIX_ROUNDS + 1):
            if round_ and not self._fix(
                round_, start_commit, guard, refs_before, feedback(self.reviews, settled, failed)
            ):
                unchanged = round_
                break
            checked = git.head(self.worktree)
            results = replay.replay(self, checked, start_commit, guard, refs_before)
            report = checks.report(results, checked, self.changed, self.tier)
            self.folder.write(ticket.CHECKS, report)
            self.folder.log(
                "ticket.checks.replayed",
                "Checks replayed by Ariane",
                checks.summary_table(results) + "\n\n" + checks.summary_line(results),
            )
            self.metrics.step("checks replayed")
            failed = checks.blocking_failures(results)
            if failed and not round_:
                names = ", ".join(r.name for r in failed)
                raise Stop(
                    f"blocking checks failed: {names}",
                    f"read work/{self.number}/checks.md in {self.worktree}",
                    category=CHECKS,
                )
            if not failed:
                reviewed = round_
                settled = replay.review_round(
                    self, checked, start_commit, guard, refs_before, results, round_
                )
            if settled is not None and settled.go and not failed:
                break
        last = functools.partial(self.verify, "the delivery", start_commit, guard, refs_before)
        return self._deliver(checked, settled, reviewed, results, unchanged, last)

    def _deliver(
        self,
        checked: str,
        settled: review.Settled | None,
        reviewed: int,
        results: list[checks.CheckResult],
        unchanged: int = 0,
        last_guard: Callable[[], None] = lambda: None,
    ) -> Outcome:
        """Push, open the pull request and publish the statuses (C11)."""
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
            context.token_value(self.environ, self.config.tracker.token_env),
            self.environ,
            checked,
            settled,
            reviewed,
            last_guard,
            self.truncated,
            lambda: setattr(self, "pushed", True),
            self.tier,
            replay.sensitive(self, checked),
        )
        self.metrics.delivered_red(len(checks.blocking_failures(results)))
        self.metrics.finish(
            "needs a human" if delivery.draft else "delivered", review.not_green(settled, results)
        )
        try:
            done = delivery.deliver(results)
        except PullRequestRefused as exc:
            raise Stop(exc.reason, exc.next_action, category=exc.category) from None
        after_delivery(self, checked, results, done)  # never changes what was delivered (#186)
        if done.draft:
            why = (
                f"fix round {unchanged} changed nothing"
                if unchanged
                else f"the review is still no-go after {MAX_FIX_ROUNDS} fix rounds"
            )
            return Outcome(
                EXIT_STOPPED,
                f"Opened draft pull request {done.pull_url} for issue #{self.number}: {why}."
                " Next: finish by hand, then run `ariane verify`.",
            )
        return Outcome(
            EXIT_OK,
            f"Opened pull request {done.pull_url} for issue #{self.number}, checks replayed green,"
            " review go. Next: review and merge it.",
        )

    def all_checks(self) -> tuple[CheckConfig, ...]:
        return (*self.config.checks, *self.config.documentation.checks())

    def _commit_record(self, message: str) -> None:
        self.folder.restore()
        folder = ticket.relative_folder(self.number)
        git.commit(self.worktree, [folder], redact(message, self.secrets), env=self.untrusted_env)

    def _stopped(self, exc: BaseException) -> Outcome:
        reason, next_action = describe(exc)
        if self.restartable and not self.pushed:
            next_action = with_restart(next_action, self.number)
        detail = exc.detail if isinstance(exc, Stop) else str(exc)
        logs.emit("run.stopped", f"ticket #{self.number}: {reason}")
        # Ctrl-C or an error can end a command before its survivors were counted.
        process.kill_survivors(self.processes_before)
        self.metrics.surviving_processes(len(process.take_killed()))
        if self.folder.exists():
            # Recording the stop must not hide the reason: report it even if this fails.
            with contextlib.suppress(*_FAILURES):
                self.folder.log("ticket.stopped", f"Stopped: {reason}", detail)
                status = exc.status if isinstance(exc, Stop) else "stopped"
                self.metrics.finish(status, category_of(exc), self.pushed)
                self.folder.set_status(status, reason, next_action)
                self._commit_record(f"#{self.number}: record the stop")
        else:  # stopped in the first setup: the metrics go outside the repository (ADR 0031)
            path = stopped_metrics_path(self.worktree, self.number)
            self.metrics.keep_stopped(path, category_of(exc))
        code = EXIT_INTERRUPTED if isinstance(exc, KeyboardInterrupt) else EXIT_STOPPED
        return Outcome(
            code, f"Stopped ticket #{self.number}: {reason}. Next: {next_action}.", detail
        )
