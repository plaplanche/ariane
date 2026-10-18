"""One round of the replay and review of a ticket (C9, C10): the checks in a clean working tree,
then the read-only reviewer on a separate tree."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ariane import checks, git, review, ticket
from ariane.config import CheckConfig
from ariane.delivery import FAILURES
from ariane.review_session import ReviewFailed, ReviewSession
from ariane.stop import Stop

if TYPE_CHECKING:
    from ariane.flow import _TicketRun


@dataclass(frozen=True)
class ReplayTree:
    """One check's tree: where it was, and how long its setup took."""

    check: str
    path: Path
    setup_s: float


def replay_each(
    all_checks: Sequence[CheckConfig],
    tree_for: Callable[[int], Path],
    *,
    create: Callable[[Path], None],
    setup: Callable[[CheckConfig, Path], None],
    verify: Callable[[Path], None],
    remove: Callable[[Path], None],
    env: Mapping[str, str] | None,
    trees: list[ReplayTree],
) -> list[checks.CheckResult]:
    """C9: each check, in order, in its own fresh tree: create, set up, run that check only,
    verify, then remove the tree, also on a stop or Ctrl-C. `trees` fills as the trees are made.

    `flow` and `verify` both replay with this function."""
    results = []
    for k, check in enumerate(all_checks, 1):
        tree = tree_for(k)
        create(tree)
        try:
            started = time.monotonic()
            setup(check, tree)
            trees.append(ReplayTree(check.name, tree, time.monotonic() - started))
            results.append(checks.run_check(check, tree, env))
            verify(tree)
        finally:
            remove(tree)
    return results


def replay(
    run: _TicketRun,
    checked: str,
    start_commit: str,
    guard: dict[str, str],
    refs_before: dict[str, str],
) -> list[checks.CheckResult]:
    """C9: run every check in its own clean working tree at the delivered commit."""
    trees: list[ReplayTree] = []

    def tree_for(k: int) -> Path:
        tree = run.worktree.with_name(f"{run.number}-replay-{k}")
        if tree.exists():
            raise Stop(f"the replay working tree already exists at {tree}", "remove it, then retry")
        return tree

    def set_up(check: CheckConfig, tree: Path) -> None:
        command = check.setup if check.setup is not None else run.config.setup
        error = run.setup(tree, command, guard)
        if error is not None:
            raise Stop(
                f"{error.reason} (in the working tree of check {check.name!r})",
                error.next_action,
                error.detail,
                status=error.status,
            )

    def verify_tree(tree: Path) -> None:
        if git.current_branch(tree) or git.head(tree) != checked:
            raise Stop("the checks moved the replay working tree's head", "inspect it")
        run.verify("the checks", start_commit, guard, refs_before, expected_head=checked)

    try:
        return replay_each(
            run.all_checks(),
            tree_for,
            create=lambda tree: git.add_detached_worktree(run.worktree, tree, checked),
            setup=set_up,
            verify=verify_tree,
            remove=lambda tree: remove(run, tree),
            env=run.untrusted_env,
            trees=trees,
        )
    finally:
        if trees:
            lines = "\n".join(f"- {t.check}: `{t.path}` (setup {t.setup_s:.1f} s)" for t in trees)
            run.folder.log(
                "ticket.checks.worktree",
                "Checks working trees",
                f"Each check was replayed in its own clean working tree at `{checked}`, not in"
                f" `{run.worktree}`:\n\n{lines}",
            )


def review_round(
    run: _TicketRun,
    checked: str,
    start_commit: str,
    guard: dict[str, str],
    refs_before: dict[str, str],
    results: list[checks.CheckResult],
    round_: int,
) -> review.Settled:
    """C10, C26: review `round_` in the replay tree; the record is `review-<round>.md`."""
    tree = run.worktree.with_name(f"{run.number}-review")
    if tree.exists():
        raise Stop(f"the reviewer working tree already exists at {tree}", "remove it, then retry")
    git.add_reviewer_worktree(run.worktree, tree, checked)
    try:
        diff = git.diff(run.worktree, start_commit, checked, ticket.WORK_DIR)
        name_status = git.name_status(run.worktree, start_commit, checked, ticket.WORK_DIR)
        run.truncated = record_truncation(run.folder, diff)
        tree_before = git.status(tree)

        def after_session() -> None:
            run.verify("the reviewer", start_commit, guard, refs_before, expected_head=checked)
            _verify_replay(tree, checked, tree_before)

        sessions = ReviewSession(
            run.runtime,
            run.config.reviewer,
            run.folder,
            run.issue,
            run.agent_envs["reviewer"],
            run.all_checks(),
            run.config.definition_of_done,
            run.base_instructions,
            metrics=run.metrics,
            round=round_,
            changed_lines=git.changed_lines(run.worktree, start_commit, checked, ticket.WORK_DIR),
        )
        try:
            answer = sessions.run(
                tree,
                checked,
                diff,
                results,
                run.not_updated,
                run.changed,
                after_session,
                name_status,
            )
        except ReviewFailed as exc:
            raise Stop(exc.reason, exc.next_action, exc.detail, status="needs a human") from None
        settled = review.settle(answer, run.config.definition_of_done, results)
        run.metrics.reviewed(settled.go)
        model = sessions.reviewer.model
        run.folder.write(ticket.review_file(round_), review.record(settled, checked, model, round_))
        verdict = f"Review {round_}: {settled.verdict}"
        run.folder.log("ticket.review.verdict", verdict, review.findings_table(settled))
        return settled
    finally:
        remove(run, tree)


def truncation_note(diff: str) -> str:
    """Where the reviewer's diff was cut and the files to read in the tree, or "" (ADR 0031)."""
    missing = review.truncated_paths(diff)
    if not missing:
        return ""
    return (
        f"The diff ({len(diff):,} characters) was cut at {review.MAX_DIFF_CHARS:,}; the"
        " reviewer was given every changed path and told to read these in the tree:\n"
        + "\n".join(f"- `{p}`" for p in missing)
    )


def record_truncation(folder: ticket.TicketFolder, diff: str) -> list[str]:
    """Journal the files whose hunks the reviewer's diff lacks when it is cut (ADR 0031)."""
    note = truncation_note(diff)
    if note:
        folder.log("ticket.review.diff_truncated", "Reviewer diff truncated", note)
    return review.truncated_paths(diff)


def _verify_replay(replay: Path, checked: str, tree_before: str) -> None:
    """The reviewer reads only: the replay tree has the same head and no edited file."""
    if git.current_branch(replay) or git.head(replay) != checked:
        raise Stop("the reviewer moved the replay working tree's head", "inspect it")
    if git.status(replay) != tree_before:
        raise Stop(
            "the reviewer changed files in the working tree",
            "inspect the review session; Ariane pushed nothing",
            status="needs a human",
        )


def remove(run: _TicketRun, replay: Path) -> None:
    try:
        git.remove_worktree(run.worktree, replay)
    except FAILURES as exc:
        run.folder.log(
            "ticket.warning.replay_not_removed",
            "Warning: replay working tree not removed",
            f"`{replay}`: {exc}",
        )
