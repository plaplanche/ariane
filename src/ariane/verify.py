"""`ariane verify`: a branch finished by hand gets a clean replay of the checks and one review
(C10, C23; ADR 0028). The records are committed on the branch; nothing is pushed."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path

from ariane import checks, context, git, process, review, ticket
from ariane.config import Config
from ariane.flow import EXIT_OK, EXIT_STOPPED, REMOTE, SETUP_TIMEOUT_S, Outcome
from ariane.redact import redact
from ariane.review_session import ReviewFailed, ReviewSession
from ariane.runtime import AgentRuntime, for_role
from ariane.tracker import Issue, Tracker, TrackerError

VERIFY_DIR = f"{ticket.WORK_DIR}/verify"
REVIEW = "review.md"
PUSH_NEXT = "push the branch and open the pull request"
FIX_NEXT = "fix the findings, then run verify again"


class Refused(Exception):
    """The branch cannot be verified; `reason` and `next_action` go to the user."""

    def __init__(self, reason: str, next_action: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.next_action = next_action


def relative_folder(branch: str) -> str:
    return f"{VERIFY_DIR}/{branch}"


def replay_path(repo_root: Path, branch: str) -> Path:
    slug = branch.replace("/", "-")
    return repo_root.parent / f"{repo_root.name}.ariane" / "worktrees" / f"verify-{slug}"


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
    except Refused as exc:
        return Outcome(
            EXIT_STOPPED, f"Did not verify {branch}: {exc.reason}. Next: {exc.next_action}."
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
        raise Refused(str(exc), "check the issue number") from None


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
        self.head = git.out(["rev-parse", f"refs/heads/{branch}"], repo_root)
        self.base = self._base()
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

    def run(self) -> Outcome:
        replay = replay_path(self.repo_root, self.branch)
        if replay.exists():
            raise Refused(f"the replay working tree already exists at {replay}", "remove it")
        records = Path(tempfile.mkdtemp(prefix="ariane-verify-"))
        git.add_detached_worktree(self.repo_root, replay, self.head)
        try:
            return self._replay_and_review(replay, records)
        finally:
            shutil.rmtree(records, ignore_errors=True)
            git.remove_worktree(self.repo_root, replay)

    def _setup(self, replay: Path) -> None:
        command = self.config.setup
        if not command:
            return
        try:
            done = process.run(
                command, cwd=replay, timeout_s=SETUP_TIMEOUT_S, env=self.untrusted_env
            )
        except process.CommandNotFoundError as exc:
            raise Refused(f"setup failed: {exc}", "install it or fix project.setup") from None
        if not done.ok:
            raise Refused(
                f"setup `{' '.join(command)}` failed (exit {done.returncode})",
                "fix the setup command, then run verify again",
            )
        if git.untracked(replay):
            raise Refused(
                "setup left files that git does not ignore",
                "add them to .gitignore, then run verify again",
            )

    def _replay_and_review(self, replay: Path, records: Path) -> Outcome:
        self._setup(replay)
        all_checks = (*self.config.checks, *self.config.documentation.checks())
        results = checks.run_checks(all_checks, replay, self.untrusted_env)
        self._unchanged(replay, "the checks", "")
        changed = git.changed_paths(replay, self.base)
        folder = ticket.TicketFolder(records, self.issue.number, secrets=self.secrets)
        folder.create(self.issue)
        tree_before = git.status(replay)
        diff = git.diff(replay, self.base, self.head, ticket.WORK_DIR)
        sessions = ReviewSession(
            self.runtime,
            self.config.reviewer,
            folder,
            self.issue,
            self.reviewer_env,
            all_checks,
            self.config.definition_of_done,
        )
        try:
            answer = sessions.run(
                replay,
                self.head,
                diff,
                results,
                self.config.documentation.not_updated(changed),
                lambda: self._unchanged(replay, "the reviewer", tree_before),
            )
        except ReviewFailed as exc:
            raise Refused(exc.reason, "read the error, then run verify again") from None
        settled = review.settle(answer, self.config.definition_of_done, results)
        model = self.config.reviewer.model
        texts = {
            REVIEW: review.record(settled, self.head, model),
            ticket.CHECKS: checks.report(results, self.head),
        }
        self._before_commit()
        self._commit(texts, checks.summary_line(results))
        green = settled.go and not checks.blocking_failures(results)
        line = (
            f"Verified {self.branch}: {checks.summary_line(results).removeprefix('Summary: ')}"
            f" Review {settled.verdict}. Records committed on the branch, nothing pushed."
            f" Next: {PUSH_NEXT if green else FIX_NEXT}."
        )
        return Outcome(EXIT_OK if green else EXIT_STOPPED, line)

    def _unchanged(self, replay: Path, after: str, tree_before: str) -> None:
        """Untrusted code ran: the branch and the replay tree are as they were."""
        moved = git.out(["rev-parse", f"refs/heads/{self.branch}"], self.repo_root) != self.head
        if git.current_branch(replay) or git.head(replay) != self.head or moved:
            raise Refused(f"{after} moved a head", "inspect the branch and the replay tree")
        if git.status(replay) != tree_before:
            raise Refused(f"{after} changed files in the replay tree", "inspect the session")

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
            folder.mkdir(parents=True, exist_ok=True)
            for name, text in texts.items():
                (folder / name).write_text(
                    redact(text, self.secrets), encoding="utf-8", newline="\n"
                )
            message = redact(
                f"Verify {self.branch}: record the checks and the review", self.secrets
            )
            committed = git.commit(
                tree,
                [relative_folder(self.branch)],
                f"{message}\n\n{summary}",
                env=self.untrusted_env,
                tolerate_ignored=True,
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
