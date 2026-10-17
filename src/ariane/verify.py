"""`ariane verify`: a branch finished by hand gets a clean replay of the checks and one review
(C10, C23; ADR 0028). The records are committed on the branch; nothing is pushed."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

from ariane import checks, context, git, process, review, ticket
from ariane.config import CheckConfig, Config
from ariane.flow import (
    EXIT_INTERRUPTED,
    EXIT_OK,
    EXIT_STOPPED,
    REMOTE,
    SETUP_TIMEOUT_S,
    Outcome,
)
from ariane.metrics import METRICS, Metrics
from ariane.redact import redact
from ariane.replay import record_truncation, replay_each, truncation_note
from ariane.review_session import ReviewFailed, ReviewSession, instruction_dirs
from ariane.runtime import AgentRuntime, for_role
from ariane.tracker import Issue, Tracker, TrackerError

VERIFY_DIR = f"{ticket.WORK_DIR}/verify"
REVIEW = "review.md"
PUSH_NEXT = "push the branch and open the pull request"
FIX_NEXT = "fix the findings, then run verify again"


class Refused(Exception):
    """The branch cannot be verified; `reason` and `next_action` go to the user."""

    def __init__(self, reason: str, next_action: str, exit_code: int = EXIT_STOPPED) -> None:
        super().__init__(reason)
        self.exit_code = exit_code
        self.reason = reason
        self.next_action = next_action


def relative_folder(branch: str) -> str:
    return f"{VERIFY_DIR}/{branch}"


def replay_path(repo_root: Path, branch: str) -> Path:
    slug = branch.replace("/", "-")
    return repo_root.parent / f"{repo_root.name}.ariane" / "worktrees" / f"verify-{slug}"


def stopped_metrics_path(repo_root: Path, branch: str) -> Path:
    """Where a verification that ended without committing keeps its `metrics.json`."""
    slug = branch.replace("/", "-")
    return repo_root.parent / f"{repo_root.name}.ariane" / "verify" / slug / METRICS


def verify(
    branch: str,
    *,
    repo_root: Path,
    config: Config,
    runtime: AgentRuntime,
    environ: Mapping[str, str],
    tracker: Tracker | None = None,
    issue_number: int | None = None,
) -> Outcome:
    """Replay the checks and review `branch` at its head; commit the records on top of it."""
    try:
        issue_source = _issue(tracker, issue_number)
        where = _checkout(repo_root, branch)
        return _Verification(branch, repo_root, config, runtime, environ, where, issue_source).run()
    except KeyboardInterrupt:
        return Outcome(
            EXIT_INTERRUPTED,
            f"Stopped verifying {branch}: interrupted by the user. Next: run verify again.",
        )
    except Refused as exc:
        return Outcome(
            exc.exit_code, f"Did not verify {branch}: {exc.reason}. Next: {exc.next_action}."
        )
    except (git.GitError, process.CommandNotFoundError, OSError) as exc:
        first = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        return Outcome(
            EXIT_STOPPED, f"Did not verify {branch}: {first}. Next: read the error, then retry."
        )


def _issue(tracker: Tracker | None, number: int | None) -> Issue | None:
    if tracker is None or number is None:
        return None
    try:
        return tracker.read_issue(number)
    except TrackerError as exc:
        raise Refused(str(exc), exc.next_action, exc.exit_code) from None


def _checkout(repo_root: Path, branch: str) -> Path | None:
    """Where the branch is checked out (None if nowhere); refuse it if that tree is dirty."""
    if not git.local_branch_exists(repo_root, branch):
        raise Refused(f"branch {branch} does not exist locally", "check out or create the branch")
    where = git.worktree_of(repo_root, branch)
    if where is not None:
        dirty = git.status(where)
        if dirty:
            listing = "; ".join(line.strip() for line in dirty.splitlines())
            raise Refused(
                f"branch {branch} is checked out in {where} with uncommitted changes ({listing})",
                "commit or discard them, then run verify again",
            )
    return where


class _Verification:
    def __init__(
        self,
        branch: str,
        repo_root: Path,
        config: Config,
        runtime: AgentRuntime,
        environ: Mapping[str, str],
        where: Path | None,
        issue: Issue | None,
    ) -> None:
        self.branch = branch
        self.repo_root = repo_root
        self.config = config
        self.runtime = runtime
        self.where = where
        self.secrets = context.known_secrets(environ, config.tracker.token_env)
        remotes = git.remotes(repo_root)
        token_env = config.tracker.token_env
        self.reviewer_env = context.untrusted_environment(
            environ,
            token_env=token_env,
            remotes=remotes,
            login_variables=for_role(runtime, "reviewer").login_variables,
        )
        self.untrusted_env = context.untrusted_environment(
            environ, token_env=token_env, remotes=remotes
        )
        self.url = git.push_url(repo_root, REMOTE) if REMOTE in remotes else None
        self.refs_before = git.remote_refs(repo_root, self.url) if self.url else {}
        self.head = git.out(["rev-parse", f"refs/heads/{branch}"], repo_root)
        self.base = self._base()
        # Read once, before any check runs: a check cannot change what the reviewer is told.
        self.base_instructions = git.base_instructions(repo_root, REMOTE, self.config.base_branch)
        self.processes_before = set(process.descendants(exited=True))
        self.truncation = ""  # where the reviewer's diff was cut, if it was
        self.guard = self._snapshot()
        self.metrics = Metrics(issue.number if issue else 0, "verify", lambda text: None)
        self.issue = issue or Issue(
            0,
            f"Branch {branch}",
            "No issue was given. The commit messages of the branch:\n\n"
            + (git.commit_messages(repo_root, self.base, self.head) or "(none)"),
            "",
        )

    def _base(self) -> str:
        for ref in (f"refs/remotes/{REMOTE}/{self.config.base_branch}", self.config.base_branch):
            if git.git(["rev-parse", "--verify", "--quiet", ref], self.repo_root, check=False).ok:
                return git.merge_base(self.repo_root, ref, self.head)
        raise Refused(
            f"the base branch {self.config.base_branch} is not known locally",
            f"fetch {REMOTE}/{self.config.base_branch}",
        )

    def _snapshot(self) -> dict[str, str]:
        reviewer = replay_path(self.repo_root, self.branch).with_name("reviewer")
        return git.config_snapshot(
            self.repo_root,
            ignore_ref=self.branch,
            watch_refs=[f"refs/remotes/{REMOTE}/{self.config.base_branch}"],
        ) | git.instruction_snapshot(
            instruction_dirs(reviewer), self.config.reviewer.runtime, self.reviewer_env
        )

    def run(self) -> Outcome:
        replay = replay_path(self.repo_root, self.branch)
        records = Path(tempfile.mkdtemp(prefix="ariane-verify-"))
        committed = False
        try:
            outcome = self._replay_and_review(replay, records)
            committed = True
            return outcome
        finally:
            # A stop or Ctrl-C may come before the survivors were counted: none outlives verify.
            process.kill_survivors(self.processes_before)
            self.metrics.surviving_processes(len(process.take_killed()))
            if not committed:
                self._keep_stopped_metrics()
            shutil.rmtree(records, ignore_errors=True)

    def _keep_stopped_metrics(self) -> None:
        """Nothing is committed on a refusal or Ctrl-C (a guard violation may have changed the
        hooks a commit runs): the metrics go outside the repository instead (ADR 0031)."""
        self.metrics.keep_stopped(stopped_metrics_path(self.repo_root, self.branch))

    def _tree_for(self, replay: Path, k: int) -> Path:
        tree = replay.with_name(f"{replay.name}-{k}")
        if tree.exists():
            raise Refused(f"the replay working tree already exists at {tree}", "remove it")
        return tree

    def _setup(self, check: CheckConfig, replay: Path) -> None:
        command = check.setup if check.setup is not None else self.config.setup
        if not command:
            return
        where = f" (in the working tree of check {check.name!r})"
        try:
            done = process.run(
                command, cwd=replay, timeout_s=SETUP_TIMEOUT_S, env=self.untrusted_env
            )
        except process.CommandNotFoundError as exc:
            raise Refused(f"setup failed: {exc}{where}", "install it or fix the setup") from None
        self._survivors(f"setup `{' '.join(command)}`{where}")
        self._guard_unchanged(f"setup `{' '.join(command)}`{where}")
        if not done.ok:
            raise Refused(
                f"setup `{' '.join(command)}` failed (exit {done.returncode}){where}",
                "fix the setup command, then run verify again",
            )
        if git.untracked(replay):
            raise Refused(
                f"setup left files that git does not ignore{where}",
                "add them to .gitignore, then run verify again",
            )

    def _replay_and_review(self, replay: Path, records: Path) -> Outcome:
        all_checks = (*self.config.checks, *self.config.documentation.checks())
        results = replay_each(
            all_checks,
            lambda k: self._tree_for(replay, k),
            create=lambda tree: git.add_detached_worktree(self.repo_root, tree, self.head),
            setup=self._setup,
            verify=lambda tree: self._unchanged(tree, "the checks", ""),
            remove=lambda tree: git.remove_worktree(self.repo_root, tree),
            env=self.untrusted_env,
            trees=[],
        )
        changed = git.changed_between(self.repo_root, self.base, self.head)
        folder = ticket.TicketFolder(records, self.issue.number, secrets=self.secrets)
        folder.create(self.issue)
        diff = (
            git.diff(self.repo_root, self.base, self.head, ticket.WORK_DIR),
            git.name_status(self.repo_root, self.base, self.head, ticket.WORK_DIR),
        )
        record_truncation(folder, diff[0])
        # The temporary journal is not committed: review.md carries the note (ADR 0031).
        self.truncation = truncation_note(diff[0])
        tree = replay.with_name(replay.name + "-reviewer")
        if tree.exists():
            raise Refused(f"the reviewer working tree already exists at {tree}", "remove it")
        git.add_reviewer_worktree(self.repo_root, tree, self.head)
        try:
            return self._review_in(tree, records, folder, all_checks, results, changed, diff)
        finally:
            git.remove_worktree(self.repo_root, tree)

    def _review_in(
        self,
        tree: Path,
        records: Path,
        folder: ticket.TicketFolder,
        all_checks: Sequence[CheckConfig],
        results: list[checks.CheckResult],
        changed: list[str],
        diff: tuple[str, str],
    ) -> Outcome:
        tree_before = git.status(tree)
        sessions = ReviewSession(
            self.runtime,
            self.config.reviewer,
            folder,
            self.issue,
            self.reviewer_env,
            all_checks,
            self.config.definition_of_done,
            self.base_instructions,
            metrics=self.metrics,
        )
        try:
            answer = sessions.run(
                tree,
                self.head,
                diff[0],
                results,
                self.config.documentation.not_updated(changed),
                changed,
                lambda: self._unchanged(tree, "the reviewer", tree_before),
                diff[1],
            )
        except ReviewFailed as exc:
            raise Refused(exc.reason, "read the error, then run verify again") from None
        settled = review.settle(answer, self.config.definition_of_done, results)
        self.metrics.reviewed(settled.go)
        model = self.config.reviewer.model
        texts = {
            REVIEW: review.record(settled, self.head, model) + _truncation_section(self.truncation),
            ticket.CHECKS: checks.report(results, self.head, changed),
        }
        green = settled.go and not checks.blocking_failures(results)
        self.metrics.finish("delivered" if green else "stopped")
        texts[METRICS] = self.metrics.render()
        self._before_commit()
        self._commit(texts, checks.summary_line(results))
        line = (
            f"Verified {self.branch}: {checks.summary_line(results).removeprefix('Summary: ')}"
            f" Review {settled.verdict}. Records committed on the branch, nothing pushed."
            f" Next: {PUSH_NEXT if green else FIX_NEXT}."
        )
        return Outcome(EXIT_OK if green else EXIT_STOPPED, line)

    def _unchanged(self, replay: Path, after: str, tree_before: str) -> None:
        """Untrusted code ran: nothing it started still runs, and git, the instruction files
        the reviewer can load, the branch and the replay tree are as they were."""
        self._survivors(after)
        self._guard_unchanged(after)
        moved = git.out(["rev-parse", f"refs/heads/{self.branch}"], self.repo_root) != self.head
        if git.current_branch(replay) or git.head(replay) != self.head or moved:
            raise Refused(f"{after} moved a head", "inspect the branch and the replay tree")
        if git.status(replay) != tree_before:
            raise Refused(f"{after} changed files in the replay tree", "inspect the session")
        if self.url:
            changed = git.remote_changes(
                self.repo_root,
                self.url,
                REMOTE,
                self.branch,
                self.config.base_branch,
                self.refs_before,
            )
            if changed:
                raise Refused(
                    f"the remote changed during {after} ({', '.join(changed)})",
                    "check it was not the agent, then run verify again",
                )

    def _guard_unchanged(self, after: str) -> None:
        """Refuse when git or the instruction files the reviewer can load differ from the
        guard's snapshot."""
        changes = git.snapshot_changes(self.guard, self._snapshot())
        written = [c for c in changes if c.partition(": ")[2].startswith("instructions ")]
        if written:
            self.metrics.guard_violation()
            raise Refused(
                f"{after} changed instruction files the reviewer can load ({'; '.join(written)})",
                "inspect and remove them (they are outside the repository)",
            )
        if changes:
            self.metrics.guard_violation()
            raise Refused(
                f"{after} changed git configuration, hooks or local branches"
                f" ({'; '.join(changes)})",
                "inspect .git/config, .git/hooks and the branches",
            )

    def _survivors(self, after: str) -> None:
        """Refuse when `after` left processes running; each command's teardown killed them."""
        process.kill_survivors(self.processes_before)
        killed = process.take_killed()
        if killed:
            self.metrics.surviving_processes(len(killed))
            self.metrics.guard_violation()
            raise Refused(
                f"{after} left {len(killed)} process(es) running after it ended; Ariane killed"
                " them",
                "find what started them in the background",
            )

    def _before_commit(self) -> None:
        """The branch and where it is checked out are as they were at the start (minutes ago)."""
        if git.out(["rev-parse", f"refs/heads/{self.branch}"], self.repo_root) != self.head:
            raise Refused(
                f"branch {self.branch} was committed to during the run",
                "run verify again on the new head",
            )
        where = git.worktree_of(self.repo_root, self.branch)
        if where != self.where:
            was = self.where or "nowhere"
            raise Refused(
                f"branch {self.branch} is now checked out in {where or 'nowhere'}, was {was}",
                "run verify again",
            )
        if where is not None and git.status(where):
            raise Refused(
                f"branch {self.branch} is checked out in {where} with uncommitted changes"
                " made during the run",
                "commit or discard them, then run verify again",
            )

    def _commit(self, texts: dict[str, str], summary: str) -> None:
        """Write the redacted records into a working tree of the branch and commit them."""
        temporary = self.where is None
        tree = self.where or replay_path(self.repo_root, self.branch).with_name(
            replay_path(self.repo_root, self.branch).name + "-commit"
        )
        if temporary:
            git.git(["worktree", "add", "--quiet", str(tree), self.branch], self.repo_root)
        try:
            folder = tree / relative_folder(self.branch)
            ticket.ensure_folder(tree, folder)
            for name, text in texts.items():
                ticket.write_file(folder / name, redact(text, self.secrets))
            message = redact(
                f"Verify {self.branch}: record the checks and the review", self.secrets
            )
            committed = git.commit(
                tree,
                [relative_folder(self.branch)],
                f"{message}\n\n{summary}",
                env=self.untrusted_env,
                tolerate_ignored=True,
                unstage=[f"{relative_folder(self.branch)}/{name}" for name in texts],
            )
            if not committed:
                raise Refused(
                    f"nothing was recorded: git found nothing to commit under"
                    f" {relative_folder(self.branch)}",
                    "check that work/ is not ignored, then run verify again",
                )
        finally:
            if temporary:
                git.remove_worktree(self.repo_root, tree)


def _truncation_section(note: str) -> str:
    return f"\n## Diff given to the reviewer\n\n{note}\n" if note else ""
