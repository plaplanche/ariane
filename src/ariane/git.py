"""Git operations Ariane performs itself: working trees, commits, the push guard, delivery."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ariane import process

# The push URL the agent's working tree sees: any plain `git push` from there fails.
BLOCKED_PUSH_URL = "ariane-blocked://agents-never-push"
_TIMEOUT_S = 300


class GitError(Exception):
    """A git command failed."""


def git(
    args: list[str], cwd: Path, *, env: Mapping[str, str] | None = None, check: bool = True
) -> process.Completed:
    completed = process.run(["git", *args], cwd=cwd, timeout_s=_TIMEOUT_S, env=env)
    if check and not completed.ok:
        raise GitError(f"git {' '.join(args)} failed:\n{completed.output.strip()}")
    return completed


def out(args: list[str], cwd: Path) -> str:
    return git(args, cwd).stdout.strip()


def repo_root(cwd: Path) -> Path:
    try:
        return Path(out(["rev-parse", "--show-toplevel"], cwd)).resolve()
    except (GitError, process.CommandNotFoundError) as exc:
        raise GitError(f"not inside a git repository: {cwd}") from exc


def remotes(cwd: Path) -> list[str]:
    return out(["remote"], cwd).split()


def push_url(cwd: Path, remote: str) -> str:
    """The URL Ariane pushes to, read from the main checkout's configuration."""
    configured = git(["config", "--get", f"remote.{remote}.pushurl"], cwd, check=False)
    if configured.ok and configured.stdout.strip():
        return configured.stdout.strip()
    return out(["config", "--get", f"remote.{remote}.url"], cwd)


def fetch(cwd: Path, remote: str, branch: str) -> None:
    git(["fetch", "--quiet", remote, f"+refs/heads/{branch}:refs/remotes/{remote}/{branch}"], cwd)


def local_branch_exists(cwd: Path, branch: str) -> bool:
    return git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], cwd, check=False).ok


def remote_heads(cwd: Path, url: str) -> dict[str, str]:
    """Map of branch name to commit on the remote, read with `git ls-remote`."""
    heads = {}
    for line in out(["ls-remote", "--heads", url], cwd).splitlines():
        sha, _, ref = line.partition("\t")
        heads[ref.removeprefix("refs/heads/")] = sha
    return heads


def add_worktree(cwd: Path, path: Path, branch: str, start: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    git(["worktree", "add", "--quiet", "-b", branch, str(path), start], cwd)


def guard_pushes(worktree: Path) -> None:
    """Make every remote's push URL invalid for this working tree only."""
    git(["config", "extensions.worktreeConfig", "true"], worktree)
    for remote in remotes(worktree):
        git(["config", "--worktree", f"remote.{remote}.pushurl", BLOCKED_PUSH_URL], worktree)


def agent_git_env(base: Mapping[str, str]) -> dict[str, str]:
    """Environment for an agent: no credential prompt, no stored credential helper."""
    env = dict(base)
    count = int(env.get("GIT_CONFIG_COUNT", "0") or "0")
    env[f"GIT_CONFIG_KEY_{count}"] = "credential.helper"
    env[f"GIT_CONFIG_VALUE_{count}"] = ""
    env["GIT_CONFIG_COUNT"] = str(count + 1)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def head(cwd: Path) -> str:
    return out(["rev-parse", "HEAD"], cwd)


def current_branch(cwd: Path) -> str:
    completed = git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd, check=False)
    return completed.stdout.strip() if completed.ok else ""


def is_ancestor(cwd: Path, ancestor: str, descendant: str) -> bool:
    return git(["merge-base", "--is-ancestor", ancestor, descendant], cwd, check=False).ok


def has_commit(cwd: Path, sha: str) -> bool:
    return git(["cat-file", "-e", f"{sha}^{{commit}}"], cwd, check=False).ok


def untracked(cwd: Path) -> list[str]:
    """Files git neither tracks nor ignores."""
    listing = out(["ls-files", "--others", "--exclude-standard"], cwd)
    return [line for line in listing.splitlines() if line]


def changed_paths(cwd: Path, since: str) -> list[str]:
    """Paths that differ from commit `since`: committed, staged, unstaged or untracked."""
    committed = out(["diff", "--name-only", since, "--"], cwd).splitlines()
    return sorted({*committed, *untracked(cwd)} - {""})


def commit_all(cwd: Path, message: str) -> bool:
    """Stage everything and commit; return False when there was nothing to commit."""
    git(["add", "--all"], cwd)
    if git(["diff", "--cached", "--quiet"], cwd, check=False).ok:
        return False
    git(["commit", "--quiet", "-m", message], cwd)
    return True


def commit_paths(cwd: Path, paths: list[str], message: str) -> bool:
    """Commit only `paths`; return False when they hold no change."""
    git(["add", "--all", "--", *paths], cwd)
    if git(["diff", "--cached", "--quiet", "--", *paths], cwd, check=False).ok:
        return False
    git(["commit", "--quiet", "-m", message, "--", *paths], cwd)
    return True


def push(cwd: Path, url: str, branch: str) -> None:
    git(["push", "--quiet", url, f"refs/heads/{branch}:refs/heads/{branch}"], cwd)
