"""`ariane start <n> --restart`: the ticket lock, and starting a stopped or interrupted ticket
over while keeping its previous branch (C5, C19, C23, ADR 0047)."""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

from ariane import git, ticket
from ariane.metrics import METRICS
from ariane.stop import Stop

REMOTE = "origin"
LOCKS = "locks"
KEPT_PREFIX = "ariane-restarted"
_STAMP = "%Y%m%dT%H%M%SZ"


def lock_path(repo_root: Path, number: int) -> Path:
    """`<repo>.ariane/locks/<n>.lock`, next to the tickets' working trees."""
    return repo_root.parent / f"{repo_root.name}.ariane" / LOCKS / f"{number}.lock"


def command(number: int) -> str:
    return f"`ariane start {number} --restart`"


def with_restart(action: str, number: int) -> str:
    """`action`, then how to start a ticket that was not pushed over (C23)."""
    if command(number) in action:
        return action
    for again in (", then start the ticket again", ", then start again"):
        action = action.removesuffix(again)
    return f"{action}; to start over, run {command(number)}"


def _try_lock(file: IO[bytes]) -> bool:
    if sys.platform == "win32":
        import msvcrt

        file.seek(0)
        try:
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


@contextlib.contextmanager
def locked(path: Path, number: int) -> Iterator[None]:
    """Hold the ticket's lock for the block; the system frees it when the process dies, so a
    killed run never leaves it held. Held by another process: `Stop`, without waiting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as file:  # closing the file releases the lock
        if not _try_lock(file):
            raise Stop(
                f"ticket #{number} is running in another Ariane process",
                "wait for it to end, or stop it",
            )
        yield


@dataclass(frozen=True)
class Restarted:
    """What `--restart` cleared before the new run: kept, never deleted, apart from the trees."""

    removed: tuple[Path, ...]
    kept_branch: str  # "" when there was no local branch
    kept_head: str
    saved: str  # the commit holding the uncommitted work of the ticket's tree, "" when none
    last_action: str  # "" when the kept branch has no readable status
    stopped_at: str | None  # the previous run's last step, None when unreadable

    def journal(self, number: int) -> str:
        trees = "\n".join(f"- `{p}`" for p in self.removed) or "- none"
        if self.kept_branch:
            branch = f"Previous branch kept as `{self.kept_branch}` at `{self.kept_head}`."
        else:
            branch = "No previous local branch."
        if self.saved:
            branch += (
                f" The uncommitted work of the ticket's working tree is saved in commit"
                f" `{self.saved}`, the kept branch's head."
            )
        status = f"work/{number}/{ticket.STATUS}"
        last = self.last_action or f"unknown (no readable `{status}` on the kept branch)"
        return (
            f"Started over a previous run of ticket #{number}.\n\nWorking trees removed:\n"
            f"{trees}\n\n{branch}\n\nPrevious run's last action: {last}."
        )

    def metrics(self) -> dict[str, str]:
        found = {"branch": self.kept_branch}
        return found | ({"stopped_at": self.stopped_at} if self.stopped_at else {})


def kept_name(number: int) -> str:
    """`ariane-restarted/<n>-<UTC time as YYYYMMDDTHHMMSSZ>`, where a restart keeps the branch."""
    return f"{KEPT_PREFIX}/{number}-{datetime.now(UTC).strftime(_STAMP)}"


def is_kept_name(name: str, number: int, started: str) -> bool:
    """Whether `name` is the kept name a restart of ticket `number` started at `started` chose:
    `ariane-restarted/<number>-<stamp>`, the stamp at most a minute before `started` (it is
    chosen just before the run registers) and never after it. The registry is a file an agent
    can write, so the guard exempts only such a name, never any other branch (ADR 0047)."""
    found = re.fullmatch(rf"{KEPT_PREFIX}/{number}-(\d{{8}}T\d{{6}}Z)", name)
    if found is None:
        return False
    try:
        stamp = datetime.strptime(found[1], _STAMP).replace(tzinfo=UTC)
        start = datetime.fromisoformat(started.replace("Z", "+00:00"))
        lag = (start - stamp).total_seconds()
    except (ValueError, TypeError):
        return False
    return 0 <= lag < 60


def prepare(
    repo_root: Path, base_branch: str, branch: str, worktree: Path, kept: str
) -> tuple[str, dict[str, str], str, Restarted | None]:
    """Refuse a ticket already pushed, clear a previous run when restarting (`kept` is then
    the name for its branch, `kept_name`, registered by the caller first) or refuse its
    leftovers, then create the ticket's branch and working tree (C11).

    Also returns the base branch's instructions, read once from the fetched ref: the reviewers
    use these, whatever an agent does to the ref later (C11, ADR 0028)."""
    number = int(worktree.name)
    url = git.push_url(repo_root, REMOTE)
    git.fetch(repo_root, REMOTE, base_branch)
    instructions = git.base_instructions(repo_root, REMOTE, base_branch)
    refs = git.remote_refs(repo_root, url)
    if f"refs/heads/{branch}" in refs:  # a pushed ticket is never restarted
        raise Stop(
            f"branch {branch} already exists on {REMOTE}",
            "close its pull request and delete the branch, then start again",
        )
    restarted = clear(repo_root, worktree, number, branch, kept) if kept else None
    if left := leftovers(worktree, number):
        raise Stop(f"its working tree already exists at {left[0]}", f"run {command(number)}")
    if git.local_branch_exists(repo_root, branch):
        raise Stop(f"branch {branch} already exists locally", f"run {command(number)}")
    git.add_worktree(repo_root, worktree, branch, f"{REMOTE}/{base_branch}")
    return url, refs, instructions, restarted


def leftovers(worktree: Path, number: int) -> list[Path]:
    """The ticket's working trees that exist: `<n>`, `<n>-review` and every `<n>-replay*`."""
    named = [worktree, worktree.with_name(f"{number}-review")]
    replays = sorted(worktree.parent.glob(f"{number}-replay*")) if worktree.parent.is_dir() else []
    return [p for p in [*named, *replays] if p.exists()]


def clear(repo_root: Path, worktree: Path, number: int, branch: str, kept: str) -> Restarted | None:
    """Save the uncommitted work of the ticket's tree, keep its local branch as `kept` with the
    saved work on top, then remove the ticket's working trees and its old branch name; None when
    there was nothing to clear (a plain start). `kept` is written as a new ref before anything is
    removed, so the saved work stays reachable whenever the restart dies: if saving or that
    write fails (`kept` already exists), the restart stops with every tree in place."""
    removed = leftovers(worktree, number)
    has_branch = git.local_branch_exists(repo_root, branch)
    if not removed and not has_branch:
        return None
    git.git(["worktree", "prune"], repo_root)  # a tree whose folder is gone is not registered
    registered = _worktree_paths(repo_root)
    if _unknown_with_files(worktree, registered):  # its files cannot be saved from git's view
        raise Stop(
            f"its working tree {worktree} is not registered with git and holds files",
            f"save what you need from it and delete it, then run {command(number)}",
        )
    previous = git.out(["rev-parse", f"refs/heads/{branch}"], repo_root) if has_branch else ""
    saved = _save(worktree, previous) if worktree.resolve() in registered else ""
    if saved or previous:  # created, never overwritten: an existing `kept` stops the restart
        git.git(["update-ref", f"refs/heads/{kept}", saved or previous, ""], repo_root)
    for tree in removed:
        _remove_tree(repo_root, tree, registered)
    git.git(["worktree", "prune"], repo_root)
    if has_branch:
        git.git(["branch", "-D", branch], repo_root)  # its config goes with it
    if not has_branch and not saved:
        return Restarted(tuple(removed), "", "", "", "", None)
    folder = ticket.relative_folder(number)
    records = previous or saved  # Ariane's records, not the files an agent left uncommitted
    return Restarted(
        tuple(removed),
        kept,
        saved or previous,
        saved,
        _last_action(_show(repo_root, records, f"{folder}/{ticket.STATUS}")),
        _stopped_at(_show(repo_root, records, f"{folder}/{METRICS}")),
    )


def _save(tree: Path, branch_head: str) -> str:
    """A commit of everything in `tree` that is not ignored, tracked or not, on top of
    `branch_head` (and of the tree's own HEAD when it differs, so both stay reachable); when the
    tree's index differs from both its HEAD and its files, the staged content is a commit of its
    own just below, so neither version is lost. "" when the tree and its index hold nothing
    beyond its HEAD and that HEAD is on the branch. Built in temporary indexes: the tree, its
    index and its refs are untouched."""
    tree_head = git.out(["rev-parse", "HEAD"], tree)
    head_tree = git.out(["rev-parse", f"{tree_head}^{{tree}}"], tree)
    index = Path(git.out(["rev-parse", "--path-format=absolute", "--git-path", "index"], tree))
    with tempfile.TemporaryDirectory(prefix="ariane-restart-") as scratch:
        env = {**git.token_free_environment(), "GIT_INDEX_FILE": str(Path(scratch) / "index")}
        if index.is_file():
            shutil.copyfile(index, env["GIT_INDEX_FILE"])
            staged = git.out(["write-tree"], tree, env=env)  # fails on a conflicted index
        else:
            staged = head_tree
        git.git(["read-tree", tree_head], tree, env=env)
        git.git(["add", "--all"], tree, env=env)
        snapshot = git.out(["write-tree"], tree, env=env)
    clean = snapshot == head_tree and staged == head_tree
    if clean and branch_head and git.is_ancestor(tree, tree_head, branch_head):
        return ""
    parents = list(dict.fromkeys(h for h in (branch_head, tree_head) if h))
    identity = git._identity(os.environ)  # Ariane's own, as on its other commits
    commit_env = {**git.token_free_environment(), **identity}

    def commit(tree_id: str, on: list[str], message: str) -> str:
        args = ["commit-tree", tree_id, *(a for h in on for a in ("-p", h)), "-m", message]
        return git.out(args, tree, env=commit_env)

    if staged not in (head_tree, snapshot):
        staged_message = "Work left staged in the working tree when the run stopped"
        parents = [commit(staged, parents, f"{staged_message} (ariane --restart)")]
    message = "Work left uncommitted in the working tree when the run stopped (ariane --restart)"
    return commit(snapshot, parents, message)


def _unknown_with_files(tree: Path, registered: set[Path]) -> bool:
    """Whether the ticket's tree is a folder git does not know that is not empty: a restart
    neither saves nor deletes it (ADR 0047)."""
    if tree.is_symlink() or not tree.is_dir() or tree.resolve() in registered:
        return False
    return any(tree.iterdir())


def _worktree_paths(repo_root: Path) -> set[Path]:
    """The resolved paths of the repository's registered working trees."""
    lines = git.out(["worktree", "list", "--porcelain"], repo_root).splitlines()
    return {Path(n.removeprefix("worktree ")).resolve() for n in lines if n.startswith("worktree ")}


def _remove_tree(repo_root: Path, tree: Path, registered: set[Path]) -> None:
    """Remove a working tree of the repository with git; a folder at the ticket's tree path
    that git does not know (a killed run left it before registering it, or after its entry
    went) is Ariane's own and removed as a folder, a link in its place unlinked, never followed."""
    if tree.resolve() in registered:
        git.remove_worktree(repo_root, tree)
    elif tree.is_dir() and not tree.is_symlink():
        if sys.version_info >= (3, 12):
            shutil.rmtree(tree, onexc=_writable_then_retry)
        else:
            shutil.rmtree(tree, onerror=_writable_then_retry)
    else:
        tree.unlink()


def _writable_then_retry(function: Callable[[str], object], path: str, _: object) -> None:
    """On Windows git's read-only object files refuse deletion: clear the flag and retry."""
    os.chmod(path, stat.S_IWRITE)
    function(path)


def _show(repo_root: Path, commit: str, path: str) -> str:
    done = git.git(["show", f"{commit}:{path}"], repo_root, check=False)
    return done.stdout if done.ok else ""


def _last_action(text: str) -> str:
    fields = ticket.parse_status(text) if text else {}
    action = fields.get("Last action", "")
    if not action:
        return ""
    detail = f" ({fields['Detail']})" if fields.get("Detail") else ""
    at = f", at {fields['At']}" if fields.get("At") else ""
    return f"{action}{detail}{at}"


def _stopped_at(text: str) -> str | None:
    """The time of the last step of a `metrics.json`, or None when it cannot be read."""
    try:
        steps = json.loads(text)["steps"]
        at = steps[-1]["at"]
        datetime.fromisoformat(at.replace("Z", "+00:00"))
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return None
    return at if isinstance(at, str) else None
