"""The implementer session of `ariane update`: a merge conflict, or checks the merge broke, as
its task, within the fix rounds of C10 (C10, C11; ADR 0033)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from ariane import checks, git, ticket
from ariane.runtime import SessionResult, StopReason
from ariane.stop import GUARD, MERGE, Stop

if TYPE_CHECKING:
    from ariane.update import _UpdateRun

MARKERS = (b"<<<<<<< ", b">>>>>>> ")  # the conflict marker lines a resolution must not leave


class Unresolved(Stop):
    """A merge neither finished nor undone (an abort that did not restore the tree, conflicts
    the update session left): the state is left for a human, nothing is committed."""


def unmerged(worktree: Path) -> list[str]:
    """The paths git holds as not merged (`git ls-files -u`)."""
    listing = git.out(["ls-files", "-u", "-z"], worktree).split("\0")
    return sorted({entry.partition("\t")[2] for entry in listing if "\t" in entry})


def with_markers(worktree: Path, paths: Sequence[str]) -> list[str]:
    """The `paths` whose file holds a conflict marker line (`<<<<<<< ` or `>>>>>>> `)."""
    found = []
    for path in paths:
        file = worktree / path
        if not file.is_file() or file.is_symlink():
            continue
        if any(line.startswith(MARKERS) for line in file.read_bytes().splitlines()):
            found.append(path)
    return found


def staged_with_markers(worktree: Path, paths: Sequence[str]) -> list[str]:
    """The `paths` whose staged blob (what the commit takes, whatever the working copy holds)
    holds a conflict marker line; a path not in the index has nothing to commit."""
    found = []
    for path in paths:
        blob = git.git(["cat-file", "blob", f":0:{path}"], worktree, check=False)
        markers = tuple(m.decode() for m in MARKERS)
        if blob.ok and any(line.startswith(markers) for line in blob.stdout.splitlines()):
            found.append(path)
    return found


def _left(worktree: Path, paths: Sequence[str]) -> list[str]:
    """The conflicts left: paths unmerged, or with a marker line in the working copy or index."""
    files = with_markers(worktree, paths)
    return sorted({*unmerged(worktree), *files, *staged_with_markers(worktree, paths)})


def _refuse_left(left: Sequence[str], nothing: str) -> None:
    if left:
        detail = "\n".join(f"- `{p}`" for p in left)
        reason = f"the update session left conflicts in {', '.join(left)}"
        raise Unresolved(reason, nothing, detail, category=MERGE)


def conflict_task(base: str, conflicts: Sequence[str]) -> str:
    """The update session's task for a merge that conflicts."""
    listing = "\n".join(f"- `{p}`" for p in conflicts)
    return (
        f"Merge `{base}` into this branch: resolve the conflicts below, keeping both sides'"
        f" intent; mark each path resolved with `git add`; do not commit.\n\n{listing}"
    )


def checks_task(base: str, failed: Sequence[checks.CheckResult]) -> str:
    """The update session's task for blocking checks red after a clean merge: each check's name
    and output, as `checks.md` shows it."""
    parts = [f"These checks fail after merging `{base}`: fix them."]
    for r in failed:
        parts += ["", f"Check `{r.name}` ({r.detail}):", ticket.fenced(checks.shown_output(r))]
    return "\n".join(parts)


def session(
    run: _UpdateRun, task: str, guard: dict[str, str], expected_head: str | None
) -> SessionResult:
    """The update's one implementer session, its `task` journaled first
    (`ticket.update.implementer`), then the guard of `flow`."""
    run.folder.log(
        "ticket.update.implementer",
        "Update session's task",
        "Task given to the implementer session (data from git and the checks):\n\n"
        + ticket.fenced(task),
    )
    run.folder.set_status("updating", "update session running", "wait")
    ignored_before = git.ignored(run.worktree)
    result = run._implement(task=task)
    run.verify("the update session", "", guard, run.heads.refs, expected_head)
    run._warn_ignored(ignored_before)
    return result


def resolve_conflicts(
    run: _UpdateRun, base: str, conflicts: Sequence[str], guard: dict[str, str], env: dict[str, str]
) -> None:
    """The merge left in progress, one implementer session resolves the conflicts, then Ariane
    commits the merge with `git commit --no-edit` (both parents kept). A path left unmerged or
    with a conflict marker line, or records staged by the session, stop the update with the
    merge state kept (`Unresolved`); a merge the session ended stops it as a guard violation."""
    tree = run.worktree
    records = ["ls-files", "-s", "--", ticket.WORK_DIR]
    staged = git.out(records, tree)
    run.resolving = True
    result = session(run, conflict_task(base, conflicts), guard, run.heads.local)
    keep = f"finish or undo the merge by hand in {tree} (`git status`)"
    pending = git.git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], tree, check=False)
    if not pending.ok or pending.stdout.strip() != run.heads.base:
        run.metrics.guard_violation()
        raise Stop(f"the update session ended the merge of {base}", keep, category=GUARD)
    nothing = (
        f"finish the merge by hand in {tree} (`git status`), then run `ariane verify"
        f" {run.branch}` and push it; Ariane committed and pushed nothing"
    )
    _refuse_left(_left(tree, conflicts), nothing)
    if git.out(records, tree) != staged:
        run.metrics.guard_violation()
        raise Unresolved("the update session staged changes to ticket records", nothing)
    git.git(["add", "--all", "--", ".", f":(exclude){ticket.WORK_DIR}"], tree, env=env)
    _refuse_left(_left(tree, conflicts), nothing)  # the commit takes the index: checked staged
    git.git(["commit", "--quiet", "--no-edit"], tree, env=env)
    listing = "\n".join(f"- `{p}`" for p in conflicts)
    run.folder.log("ticket.work.committed", "Merge committed", f"Conflicts resolved:\n{listing}")
    if result.stop_reason is not StopReason.FINISHED:
        raise Stop(
            f"the update session stopped: {result.stop_text()}",
            f"read work/{run.number}/journal.md; the merge it resolved is kept on the branch",
            category=result.stop_category(),
        )
