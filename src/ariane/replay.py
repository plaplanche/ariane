"""One round of the replay and review of a ticket (C9, C10): the checks in a clean working tree,
then the read-only reviewer on a separate tree."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ariane import cache, checks, context, git, process, review, slots, ticket
from ariane.config import CheckConfig
from ariane.delivery import FAILURES
from ariane.restart import command
from ariane.review_session import ReviewFailed, ReviewSession
from ariane.stop import Stop

if TYPE_CHECKING:
    from ariane.flow import _TicketRun


@dataclass(frozen=True)
class ReplayTree:
    """One check's tree: where it was, how long its setup took, the slot it ran in, and what its
    dependency caches did."""

    check: str
    path: Path
    setup_s: float
    slot: int | None = None  # None: the run's own slot, checks replayed one by one
    caches: str = ""  # `cache.lines`: each cache hit or built; "" without `[[project.cache]]`


def replay_each(
    all_checks: Sequence[CheckConfig],
    tree_for: Callable[[int], Path],
    *,
    create: Callable[[Path], None],
    setup: Callable[[CheckConfig, Path, Mapping[str, str] | None], str],
    verify: Callable[[Path], None],
    remove: Callable[[Path], None],
    env: Mapping[str, str] | None,
    trees: list[ReplayTree],
    slots: Sequence[int] = (),
) -> list[checks.CheckResult]:
    """C9: each check in its own fresh tree: create, set up, run that check only, verify, then
    remove the tree, also on a stop or Ctrl-C. `trees` fills as the trees are made; `setup`
    returns what the tree's dependency caches did (`cache.lines`, ADR 0054).

    With several `slots`, as many worker threads replay the checks at the same time, each giving
    its slot as `ARIANE_SLOT` to its setup and check (ADR 0052); the results keep the declared
    order. A stop in one worker, or Ctrl-C, stops the others, kills their process trees and
    removes every tree. `flow` and `verify` both replay with this function."""
    pending = list(enumerate(all_checks, 1))
    results: dict[int, checks.CheckResult] = {}
    serial = threading.Lock()  # creating, verifying, removing a tree: one worker at a time
    stopping = threading.Event()
    serial_stop = threading.Lock()
    cause: list[BaseException] = []  # what stopped the replay first
    workers: list[threading.Thread] = []

    def stop_all(exc: BaseException) -> None:
        with serial_stop:
            if not stopping.is_set():
                cause.append(exc)
                stopping.set()
        process.cancel({t.ident for t in workers if t.ident is not None})

    def one(k: int, check: CheckConfig, env_k: Mapping[str, str] | None, slot: int | None) -> None:
        with serial, process.shielded():  # a tree is never left half made
            tree = tree_for(k)
            create(tree)
        try:
            started = time.monotonic()
            used = setup(check, tree, env_k)
            trees.append(ReplayTree(check.name, tree, time.monotonic() - started, slot, used))
            results[k] = checks.run_check(check, tree, env_k)
            verify(tree)
        except BaseException as exc:
            stop_all(exc)  # before this tree is removed: the others stop at once
            raise
        finally:
            with serial, process.shielded():
                remove(tree)

    def work(slot: int | None) -> None:
        env_k = env if slot is None else _with_slot(env, slot)
        while not stopping.is_set():
            with serial:
                if not pending:
                    return
                k, check = pending.pop(0)
            try:
                one(k, check, env_k, slot)
            except BaseException as exc:
                stop_all(exc)
                if slot is None:  # one by one, in the calling thread
                    raise
                return

    def worker(slot: int, done: threading.Event) -> None:
        try:
            work(slot)
        finally:
            done.set()  # after its tree is removed: what the caller waits for

    if len(slots) <= 1:
        work(None)
        return [results[k] for k in sorted(results)]
    finished = [threading.Event() for _ in slots]
    workers += [
        threading.Thread(target=worker, args=(slot, done), daemon=True)
        for slot, done in zip(slots, finished, strict=True)
    ]
    started: list[threading.Event] = []
    try:
        for thread, done in zip(workers, finished, strict=True):
            started.append(done)  # before start(): a Ctrl-C inside it still waits for it
            try:
                thread.start()
            except Exception:
                done.set()  # never ran
                raise
        _wait(started)
    except BaseException as exc:  # Ctrl-C reaches the calling thread only; or a start failed
        stop_all(exc)  # the workers already started stop, and are waited for before the slots go
        _wait(started, interruptible=False)
    finally:
        process.resume({t.ident for t in workers if t.ident is not None})
        names = [c.name for c in all_checks]
        trees.sort(key=lambda t: names.index(t.check))
    if cause:
        raise cause[0]
    return [results[k] for k in sorted(results)]


def _wait(finished: Sequence[threading.Event], *, interruptible: bool = True) -> None:
    """Wait until every worker has set its `finished` event, after removing its tree; in short
    waits so Ctrl-C reaches the calling thread on Windows too. Not `Thread.join`: on Python 3.11,
    Ctrl-C during a join can mark a thread stopped while it still runs. Not `interruptible`, a
    second Ctrl-C is ignored while the stopped workers remove their trees."""
    for done in finished:
        while not done.is_set():
            try:
                done.wait(0.1)
            except KeyboardInterrupt:
                if interruptible:
                    raise


def _with_slot(env: Mapping[str, str] | None, slot: int) -> dict[str, str]:
    return {**(os.environ if env is None else env), context.SLOT_VARIABLE: str(slot)}


def parallel_note(workers: Sequence[int], wanted: int) -> str:
    """How many checks ran at once and in which slots; fewer than `wanted` when fewer were free."""
    note = (
        f"Checks replayed {len(workers)} at a time, in slots {', '.join(map(str, workers))}"
        f" (`{context.SLOT_VARIABLE}`, ADR 0052)."
    )
    if len(workers) < wanted:
        note += (
            f" `project.parallel_checks` asked for {wanted}; only {len(workers)} run slot(s)"
            " were free."
        )
    return note


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
            raise Stop(f"the replay working tree already exists at {tree}", _leftover(run))
        return tree

    def set_up(check: CheckConfig, tree: Path, env: Mapping[str, str] | None) -> str:
        command = check.setup if check.setup is not None else run.config.setup
        used, error = set_up_tree(run, tree, command, guard, env, fill=True)
        if error is not None:
            raise Stop(
                f"{error.reason} (in the working tree of check {check.name!r})",
                error.next_action,
                error.detail,
                status=error.status,
            )
        return cache.lines(used)

    def verify_tree(tree: Path) -> None:
        if git.detached_head(tree) != checked:
            raise Stop("the checks moved the replay working tree's head", "inspect it")
        # The remote is listed after each check: a later check could undo what one pushed.
        run.verify("the checks", start_commit, guard, refs_before, expected_head=checked)

    all_checks = run.all_checks()
    wanted = min(run.config.parallel_checks, len(all_checks))
    try:
        with slots.several(wanted - 1) as more:  # each worker its own slot (ADR 0052)
            workers = [run.slot, *more]
            if wanted > 1:
                note = parallel_note(workers, wanted)
                run.folder.log("ticket.checks.parallel", "Checks in parallel", note)
            return replay_each(
                all_checks,
                tree_for,
                create=lambda tree: git.add_detached_worktree(run.worktree, tree, checked),
                setup=set_up,
                verify=verify_tree,
                remove=lambda tree: remove(run, tree),
                env=run.untrusted_env,
                trees=trees,
                slots=workers,
            )
    finally:
        if trees:
            lines = "\n".join(
                f"- {t.check}: `{t.path}` ({_slot(t)}setup {t.setup_s:.1f} s)" for t in trees
            )
            run.folder.log(
                "ticket.checks.worktree",
                "Checks working trees",
                f"Each check was replayed in its own clean working tree at `{checked}`, not in"
                f" `{run.worktree}`:\n\n{lines}",
            )
            if run.config.caches:
                used = "\n".join(f"- {t.check}: {t.caches}" for t in trees)
                run.folder.log("ticket.checks.cache", "Dependency caches", used)


def set_up_ticket_tree(run: _TicketRun, guard: dict[str, str]) -> tuple[str, Stop | None]:
    """The ticket's own tree at the start of the ticket: old cache entries pruned, then the caches
    copied from the store or built, never stored (the agent works there), then `project.setup`.
    Returns the journal's note on the caches ("" without any) and the setup's stop, or None."""
    pruned = cache.prune(_store(run), run.config.caches)
    used, error = set_up_tree(run, run.worktree, run.config.setup, guard, fill=False)
    note = f"\n\nDependency caches: {cache.lines(used)}." if used else ""
    if pruned:
        note += f"\n\nOld cache entries removed: {', '.join(f'`{p}`' for p in pruned)}."
    return note, error


def _store(run: _TicketRun) -> Path:
    """`cache.store_path` of the repository: `<repo>.ariane/cache`, next to `worktrees/`."""
    return run.worktree.parent.parent / cache.FOLDER


def set_up_tree(
    run: _TicketRun,
    tree: Path,
    command: tuple[str, ...] | None,
    guard: dict[str, str],
    env: Mapping[str, str] | None = None,
    *,
    fill: bool,
) -> tuple[list[cache.Used], Stop | None]:
    """The declared dependency caches (copied from the store, else built by their own setup and,
    when `fill`, stored: ADR 0054), then `command` for whatever they do not cover; each setup
    guarded by `run.setup`. Returns what the caches did and the first setup's stop, or None."""

    def build(setup: tuple[str, ...]) -> None:
        error = run.setup(tree, setup, guard, env)
        if error is not None:
            raise error

    try:
        used = cache.prepare(run.config.caches, tree, _store(run), build, fill=fill)
    except Stop as exc:
        return [], exc
    return used, run.setup(tree, command, guard, env)


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
        raise Stop(f"the reviewer working tree already exists at {tree}", _leftover(run))
    git.add_reviewer_worktree(run.worktree, tree, checked)
    try:
        changes = git.changes(run.worktree, start_commit, checked, ticket.WORK_DIR)
        diff, name_status = changes.diff, changes.name_status
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
            small_env=run.agent_envs["reviewer.small"],
            changed_lines=changes.changed_lines,
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


def _slot(tree: ReplayTree) -> str:
    return "" if tree.slot is None else f"slot {tree.slot}, "


def _leftover(run: _TicketRun) -> str:
    """The next action for a tree a killed run left (ADR 0047): a shadow clone has no restart."""
    return f"run {command(run.number)}" if run.restartable else "remove it, then retry"


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
    if git.detached_head(replay) != checked:
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
