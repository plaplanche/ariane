"""`ariane update <n>`: the base branch merged into a delivered ticket's branch, the checks
replayed and one review, then the branch pushed again on go (C9, C10, C11, C23; ADR 0033)."""

from __future__ import annotations

import contextlib
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ariane import checks, context, git, logs, process, replay, review, runs, ticket
from ariane.config import Config
from ariane.delivery import FAILURES, Delivery, PullRequestRefused
from ariane.flow import (
    EXIT_INTERRUPTED,
    EXIT_OK,
    EXIT_STOPPED,
    REMOTE,
    Outcome,
    _TicketRun,
    branch_name,
    worktree_path,
)
from ariane.metrics import METRICS
from ariane.restart import lock_path, locked
from ariane.runtime import AgentRuntime
from ariane.slots import held as held_slot
from ariane.stop import Stop, describe
from ariane.tracker import Tracker, TrackerError

NEEDS_A_HUMAN = "needs a human"
_REVIEW = re.compile(r"review-(\d+)\.md")


class Unresolved(Stop):
    """A failed merge that `git merge --abort` did not undo: the state is left for a human."""


class Refused(Exception):
    """The ticket cannot be updated; nothing was changed."""

    def __init__(self, reason: str, next_action: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.next_action = next_action


@dataclass(frozen=True)
class Heads:
    """Where the update starts: the local branch, the remote branch and the remote base."""

    url: str
    refs: dict[str, str]  # the remote's branches and tags, read once (`git.remote_refs`)
    local: str
    remote: str
    base: str


def update(
    number: int,
    *,
    repo_root: Path,
    config: Config,
    tracker: Tracker,
    runtime: AgentRuntime,
    environ: Mapping[str, str],
) -> Outcome:
    """Merge the remote base branch into `ariane/<number>`, replay, review, push on go."""
    branch = branch_name(number)
    worktree = worktree_path(repo_root, number)
    try:
        issue = tracker.read_issue(number)
    except TrackerError as exc:
        return Outcome(exc.exit_code, f"Did not update #{number}: {exc}. Next: {exc.next_action}.")
    except KeyboardInterrupt:
        return _interrupted(number)
    with contextlib.ExitStack() as held:
        try:
            held.enter_context(locked(lock_path(repo_root, number), number))
            slot = held.enter_context(held_slot())  # to the run's end (ADR 0050)
            heads = _refuse_or_read(repo_root, config.base_branch, tracker, branch, worktree)
            if git.is_ancestor(worktree, heads.base, heads.local):
                logs.emit(
                    "ticket.update.up_to_date",
                    f"ticket #{number}: {REMOTE}/{config.base_branch} is an ancestor of {branch}",
                )
                return Outcome(
                    EXIT_OK,
                    f"Ticket #{number} is up to date with {config.base_branch}. Next: nothing.",
                )
            held.enter_context(runs.registered(runs.folder(repo_root), number, branch))
            witnessed = held.enter_context(runs.watching(runs.folder(repo_root)))
            instructions = git.base_instructions(repo_root, REMOTE, config.base_branch)
            run = _UpdateRun(
                issue, config, tracker, runtime, environ, worktree, branch, heads.url, slot
            )
            run.heads = heads
            # The worktree holds the delivered ticket, not the base: residuals from the base only.
            run.residuals = review.accepted_residuals(repo_root, heads.base)
            run.base_instructions = instructions
            run.witnessed = witnessed
        except Refused as exc:
            line = f"Did not update ticket #{number}: {exc.reason}. Next: {exc.next_action}."
            return Outcome(EXIT_STOPPED, line)
        except (Stop, KeyboardInterrupt, *FAILURES) as exc:
            reason, next_action = describe(exc)
            code = EXIT_INTERRUPTED if isinstance(exc, KeyboardInterrupt) else EXIT_STOPPED
            return Outcome(code, f"Did not update ticket #{number}: {reason}. Next: {next_action}.")
        return run.execute_update()


def _interrupted(number: int) -> Outcome:
    reason, next_action = describe(KeyboardInterrupt())
    return Outcome(
        EXIT_INTERRUPTED, f"Did not update ticket #{number}: {reason}. Next: {next_action}."
    )


def _refuse_or_read(
    repo_root: Path, base_branch: str, tracker: Tracker, branch: str, worktree: Path
) -> Heads:
    """The refusals of ADR 0033, each before any change; else where the update starts."""
    number = int(worktree.name)
    try:
        pull = tracker.pull_request_state(branch)
    except TrackerError as exc:
        raise Refused(f"could not read the pull request of {branch}: {exc}", "retry") from None
    if pull is None:
        raise Refused(f"no pull request from {branch}", f"open the pull request from {branch}")
    if pull.ended:
        how = "merged" if pull.merged else "closed"
        raise Refused(f"the pull request from {branch} is {how}", "nothing to update")
    if not worktree.is_dir():
        raise Refused(
            f"the ticket's working tree {worktree} is missing",
            f"check out {branch} there with `git worktree add {worktree} {branch}`, then retry",
        )
    if dirty := git.status(worktree):
        listing = "; ".join(line.strip() for line in dirty.splitlines())
        raise Refused(
            f"the ticket's working tree {worktree} has uncommitted changes ({listing})",
            "commit or discard them, then retry",
        )
    current = git.state(worktree, ignore_ref=branch).branch
    if current != branch:
        raise Refused(
            f"the ticket's working tree {worktree} is on {current or 'a detached head'},"
            f" not {branch}",
            f"check out {branch} there, then retry",
        )
    url = git.push_url(repo_root, REMOTE)
    refs = git.remote_refs(repo_root, url)
    remote = refs.get(f"refs/heads/{branch}", "")
    if not remote:
        raise Refused(f"branch {branch} is not on {REMOTE}", f"run ariane start {number}")
    local = git.head(worktree)
    if not _only_records_beyond(worktree, remote, local, number):
        raise Refused(
            f"the local branch {branch} diverged from {REMOTE}/{branch}",
            f"make {branch} match {REMOTE}/{branch} (the update pushes a fast-forward), then retry",
        )
    # Up to date: decided from the remote's base read above, before any fetch writes to git.
    listed = refs.get(f"refs/heads/{base_branch}", "")
    known = git.git(["cat-file", "-e", f"{listed}^{{commit}}"], worktree, check=False).ok
    if listed and known and git.is_ancestor(worktree, listed, local):
        return Heads(url, refs, local, remote, listed)
    git.fetch(repo_root, REMOTE, base_branch)
    base = git.out(["rev-parse", f"refs/remotes/{REMOTE}/{base_branch}"], repo_root)
    return Heads(url, refs, local, remote, base)


def _only_records_beyond(worktree: Path, remote: str, local: str, number: int) -> bool:
    """Whether `local` is the `remote` head, or a descendant of it whose extra commits each
    change only `work/<number>/` (the records committed after the delivery's push, ADR 0027):
    every commit's own paths, a merge's against each parent, so a change reverted is seen."""
    if local == remote:
        return True
    known = git.git(["cat-file", "-e", f"{remote}^{{commit}}"], worktree, check=False).ok
    if not known or not git.is_ancestor(worktree, remote, local):
        return False
    own = ticket.relative_folder(number) + "/"
    log = ["log", "--no-ext-diff", "--no-textconv", "--no-renames", "--diff-merges=separate"]
    log += ["--no-show-signature"]
    listing = git.out([*log, "--format=", "--name-only", f"{remote}..{local}", "--"], worktree)
    return all(p.startswith(own) for p in listing.splitlines() if p)


def next_review(names: list[str]) -> int:
    """The number of the next review file: one more than the highest `review-<k>.md`, else 0."""
    found = [int(m[1]) for name in names if (m := _REVIEW.fullmatch(name))]
    return max(found) + 1 if found else 0


class _UpdateRun(_TicketRun):
    """A delivered ticket's run, continued: its folder and metrics are read back, the branch is
    pushed already (a stop never names `--restart`)."""

    restartable = False
    heads: Heads

    @property
    def incoming_from(self) -> str:
        """The ticket's head before the merge: the checks are selected from what the merge brings
        from the base too, not only from the ticket's own diff (ADR 0056)."""
        return self.heads.local

    merge_began = False

    def execute_update(self) -> Outcome:
        try:
            self.pushed = True
            self.folder.load()
            self.metrics.resume(self.folder.read(METRICS))
            self.processes_before = set(process.descendants(exited=True))
            self.guard_since = runs.now()
            guard = self.state().snapshot
            merged = self._merge(guard)
            return self._replay_review_push(merged, guard)
        except Unresolved as exc:
            return self._left_unresolved(exc)
        except (Stop, KeyboardInterrupt, *FAILURES) as exc:
            if self.merge_began and self._merge_pending():  # Ctrl-C or an error mid-merge
                base = f"{REMOTE}/{self.config.base_branch}"
                return self._left_unresolved(
                    Unresolved(
                        f"merging {base} was interrupted and is neither finished nor undone",
                        f"finish or undo the merge by hand in {self.worktree} (`git status`);"
                        " Ariane wrote and pushed nothing",
                        str(exc),
                    )
                )
            return self._stopped(exc)

    def _merge_pending(self) -> bool:
        """Whether a merge is left half done in the ticket's tree (its `MERGE_HEAD`, or paths
        not merged, or git cannot tell): then no record is written, since a record commit's
        `git reset` would drop the merge state needed to finish or abort it."""
        try:
            pending = git.git(
                ["rev-parse", "-q", "--verify", "MERGE_HEAD"], self.worktree, check=False
            )
            unmerged = git.git(
                ["diff", "--name-only", "--diff-filter=U"], self.worktree, check=False
            )
        except (KeyboardInterrupt, *FAILURES):
            return True
        return pending.ok or not unmerged.ok or bool(unmerged.output.strip())

    def _stopped(self, exc: BaseException) -> Outcome:
        """The stop of `flow`; once the merge began, a stop or an error needs a human (the
        merge may be kept on the local branch), Ctrl-C stays `stopped`."""
        plain = not isinstance(exc, Stop) or exc.status == "stopped"
        if self.merge_began and plain and not isinstance(exc, KeyboardInterrupt):
            reason, next_action = describe(exc)
            detail = exc.detail if isinstance(exc, Stop) else str(exc)
            exc = Stop(reason, next_action, detail, status=NEEDS_A_HUMAN)
        return super()._stopped(exc)

    def _left_unresolved(self, exc: Unresolved) -> Outcome:
        """`git merge --abort` did not restore the tree: nothing is written or committed (a
        record commit would reset the unresolved merge and hide it), the state is kept."""
        logs.emit("run.stopped", f"ticket #{self.number}: {exc.reason}")
        process.kill_survivors(self.processes_before)
        process.take_killed()
        return Outcome(
            EXIT_STOPPED,
            f"Stopped ticket #{self.number} ({NEEDS_A_HUMAN}): {exc.reason}. Next:"
            f" {exc.next_action}.",
            exc.detail,
        )

    def verify(
        self,
        after: str,
        start_commit: str,
        guard: dict[str, str],
        refs_before: dict[str, str],
        expected_head: str | None = None,
    ) -> None:
        """The guard of `flow`, the history kept from the head the update started at."""
        super().verify(after, self.heads.local, guard, refs_before, expected_head)

    def _merge(self, guard: dict[str, str]) -> str:
        """`git merge --no-ff --no-edit <remote>/<base>` with the untrusted environment; no hook
        runs (every git command Ariane runs has `core.hooksPath` set to the null device); a
        conflict is aborted and stops the ticket, naming the paths."""
        base = f"{REMOTE}/{self.config.base_branch}"
        env = {**self.untrusted_env, **git._identity(os.environ), "LC_ALL": "C"}
        self.merge_began = True
        self.metrics.updates += 1
        done = git.git(["merge", "--no-ff", "--no-edit", base], self.worktree, env=env, check=False)
        if not done.ok:
            conflicts = self._abort(base, done.output, env)  # before any record is written
        self.folder.log(
            "ticket.update.started",
            "Update started",
            f"Merging `{base}` (at `{self.heads.base}`) into `{self.branch}` (at"
            f" `{self.heads.local}`, `{self.branch}` on {REMOTE} at `{self.heads.remote}`), in"
            f" `{self.worktree}`, slot {self.slot} (`{context.SLOT_VARIABLE}`).",
        )
        if not done.ok:
            self.verify("the merge", "", guard, self.heads.refs, expected_head=self.heads.local)
            if conflicts:
                raise Stop(
                    f"merging {base} conflicts in {', '.join(conflicts)}",
                    f"merge {base} into {self.branch} by hand in {self.worktree}, then run"
                    f" `ariane verify {self.branch}` and push it",
                    "\n".join(f"- `{p}`" for p in conflicts),
                    status=NEEDS_A_HUMAN,
                )
            raise Stop(
                f"git merge of {base} failed",
                "read the error, then retry",
                ticket.fenced(done.output),
                status=NEEDS_A_HUMAN,
            )
        merged = git.head(self.worktree)
        self.verify("the merge", "", guard, self.heads.refs, expected_head=merged)
        parents = git.out(["rev-parse", f"{merged}^1", f"{merged}^2"], self.worktree).split()
        if parents != [self.heads.local, self.heads.base]:
            raise Stop(
                f"the merge commit's parents are not {self.branch} and {base}",
                "inspect the branch; Ariane pushed nothing",
                status=NEEDS_A_HUMAN,
            )
        self.metrics.step("base merged")
        self.folder.log("ticket.update.merged", "Base branch merged", f"Merge commit `{merged}`.")
        return merged

    def _abort(self, base: str, output: str, env: dict[str, str]) -> list[str]:
        """The conflicting paths of a failed merge, read before `git merge --abort`; raises
        `Unresolved` unless the abort restored the head, the tree and the index."""
        listing = git.out(["diff", "--name-only", "--diff-filter=U"], self.worktree)
        conflicts = [p for p in listing.splitlines() if p]
        aborted = git.git(["merge", "--abort"], self.worktree, env=env, check=False)
        pending = git.git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], self.worktree, check=False)
        left = git.status(self.worktree)
        if (
            aborted.ok
            and not pending.ok
            and not left
            and git.head(self.worktree) == self.heads.local
        ):
            return conflicts
        named = f" (conflicts in {', '.join(conflicts)})" if conflicts else ""
        raise Unresolved(
            f"merging {base} failed{named} and `git merge --abort` did not restore {self.branch}",
            f"finish or undo the merge by hand in {self.worktree} (`git status`); Ariane wrote"
            " and pushed nothing",
            ticket.fenced(output + aborted.output + left),
        )

    def _replay_review_push(self, merged: str, guard: dict[str, str]) -> Outcome:
        base, refs = self.heads.base, self.heads.refs
        self.changed = [
            p
            for p in git.changed_between(self.worktree, base, merged)
            if p and not p.startswith(ticket.WORK_DIR + "/")
        ]
        self._flag_untouched_docs(self.changed)
        self.folder.set_status("updating", f"checks replayed on merge commit {merged}", "wait")
        results = replay.replay(self, merged, base, guard, refs)
        self.folder.write(ticket.CHECKS, checks.report(results, merged, self.changed))
        self.folder.log(
            "ticket.checks.replayed",
            "Checks replayed by Ariane",
            checks.summary_table(results) + "\n\n" + checks.summary_line(results),
        )
        self.metrics.step("checks replayed")
        keep = f"the merge is kept on the local branch {self.branch}; Ariane pushed nothing"
        if failed := checks.blocking_failures(results):
            raise Stop(
                f"blocking checks failed after the merge: {', '.join(r.name for r in failed)}",
                f"read work/{self.number}/checks.md in {self.worktree}; {keep}",
                status=NEEDS_A_HUMAN,
            )
        k = next_review(self.folder.names())
        settled = replay.review_round(self, merged, base, guard, refs, results, k)
        if not settled.go:
            raise Stop(
                f"the review of the update is {settled.verdict}",
                f"read work/{self.number}/{ticket.review_file(k)} in {self.worktree}; {keep}",
                status=NEEDS_A_HUMAN,
            )
        self.metrics.delivered_red(0)
        self.metrics.finish("delivered")
        try:
            pushed = self._delivery(merged, k, guard).push_update(results, self.heads.remote)
        except PullRequestRefused as exc:
            raise Stop(exc.reason, exc.next_action, status=NEEDS_A_HUMAN) from None
        return Outcome(
            EXIT_OK,
            f"Updated {self.branch} with {REMOTE}/{self.config.base_branch}: merge commit"
            f" {merged[:12]}, checks replayed green, review go, pushed {pushed[:12]}. Next:"
            " review and merge its pull request.",
        )

    def _delivery(self, merged: str, k: int, guard: dict[str, str]) -> Delivery:
        """The push of the update: the remote branch must not have moved since it began."""

        def last_guard() -> None:
            now = git.remote_refs(self.worktree, self.url).get(f"refs/heads/{self.branch}", "")
            if now != self.heads.remote:
                raise Stop(
                    f"{self.branch} moved on {REMOTE} during the update (now {now or 'deleted'})",
                    f"see who pushed it; the merge is kept on the local branch {self.branch},"
                    " Ariane pushed nothing",
                    status=NEEDS_A_HUMAN,
                )
            self.verify("the delivery", "", guard, self.heads.refs)

        return Delivery(
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
            merged,
            None,
            k,
            last_guard,
            self.truncated,
            lambda: setattr(self, "pushed", True),
        )
