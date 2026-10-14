"""One round of the replay and review of a ticket (C9, C10): the checks in a clean working tree,
then the read-only reviewer on a separate tree."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ariane import checks, git, review, ticket
from ariane.delivery import FAILURES
from ariane.review_session import ReviewFailed, ReviewSession
from ariane.stop import Stop

if TYPE_CHECKING:
    from ariane.flow import _TicketRun


def replay(
    run: _TicketRun,
    checked: str,
    start_commit: str,
    guard: dict[str, str],
    refs_before: dict[str, str],
) -> tuple[Path, list[checks.CheckResult]]:
    """C9: set up and run every check in a clean working tree at the delivered commit.

    The tree is kept for the reviewer; the caller removes it."""
    replay = run.worktree.with_name(f"{run.number}-replay")
    if replay.exists():
        raise Stop(f"the replay working tree already exists at {replay}", "remove it, then retry")
    git.add_detached_worktree(run.worktree, replay, checked)
    try:
        run.folder.log(
            "ticket.checks.worktree",
            "Checks working tree",
            f"Setup and checks run in a clean working tree `{replay}` at `{checked}`,"
            f" not in `{run.worktree}`.",
        )
        setup_error = run.setup(replay)
        if setup_error is not None:
            raise setup_error
        results = checks.run_checks(run.all_checks(), replay, run.untrusted_env)
        if git.current_branch(replay) or git.head(replay) != checked:
            raise Stop("the checks moved the replay working tree's head", "inspect it")
        run.verify("the checks", start_commit, guard, refs_before, expected_head=checked)
    except BaseException:
        remove(run, replay)
        raise
    return replay, results


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
            git.base_instructions(run.worktree, run.remote, run.config.base_branch),
            metrics=run.metrics,
            round=round_,
        )
        try:
            answer = sessions.run(tree, checked, diff, results, run.not_updated, after_session)
        except ReviewFailed as exc:
            raise Stop(exc.reason, exc.next_action, exc.detail, status="needs a human") from None
        settled = review.settle(answer, run.config.definition_of_done, results)
        run.metrics.reviewed(settled.go)
        model = run.config.reviewer.model
        run.folder.write(ticket.review_file(round_), review.record(settled, checked, model, round_))
        verdict = f"Review {round_}: {settled.verdict}"
        run.folder.log("ticket.review.verdict", verdict, review.findings_table(settled))
        return settled
    finally:
        remove(run, tree)


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
