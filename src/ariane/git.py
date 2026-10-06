"""Git operations Ariane performs itself: working trees, commits, guards, delivery."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from pathlib import Path

from ariane import process

# The push URL an agent's git sees: any plain `git push` from its environment fails.
BLOCKED_PUSH_URL = "ariane-blocked://agents-never-push"
_TIMEOUT_S = 300
# Ariane's own git commands never run hooks or a filesystem monitor: after an agent session,
# both could be code the agent planted (C21: the guard comes from Ariane, not the working tree).
_SAFE_OPTIONS = ["-c", f"core.hooksPath={os.devnull}", "-c", "core.fsmonitor=false"]
_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/@\s]+@")


class GitError(Exception):
    """A git command failed."""


def redact(text: str) -> str:
    """Hide credentials embedded in URLs (`https://user:token@host`)."""
    return _USERINFO.sub(r"\1***@", text)


def git(
    args: list[str], cwd: Path, *, env: Mapping[str, str] | None = None, check: bool = True
) -> process.Completed:
    completed = process.run(["git", *_SAFE_OPTIONS, *args], cwd=cwd, timeout_s=_TIMEOUT_S, env=env)
    if check and not completed.ok:
        raise GitError(redact(f"git {' '.join(args)} failed:\n{completed.output.strip()}"))
    return completed


def out(args: list[str], cwd: Path, *, env: Mapping[str, str] | None = None) -> str:
    return git(args, cwd, env=env).stdout.strip()


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


def remote_refs(cwd: Path, url: str) -> dict[str, str]:
    """Every branch and tag on the remote, as `refs/...` to commit, read with `git ls-remote`."""
    refs = {}
    for line in out(["ls-remote", "--heads", "--tags", url], cwd).splitlines():
        sha, _, ref = line.partition("\t")
        if ref:
            refs[ref] = sha
    return refs


def add_worktree(cwd: Path, path: Path, branch: str, start: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    git(["worktree", "add", "--quiet", "-b", branch, str(path), start], cwd)


def config_fingerprint(worktree: Path, *, ignore_ref: str) -> str:
    """A digest of everything in the repository that makes git run code or reroute a push.

    Covers the shared configuration, hooks and info files, this working tree's own
    configuration, and the local branches and tags except branch `ignore_ref` (the ticket's
    own). Ariane compares it before and after untrusted code runs: a change means that code
    edited git itself.
    """
    common = Path(out(["rev-parse", "--path-format=absolute", "--git-common-dir"], worktree))
    private = Path(out(["rev-parse", "--path-format=absolute", "--git-dir"], worktree))
    digest = hashlib.sha256()
    files = [common / "config", private / "config.worktree"]
    for folder in (common / "hooks", common / "info"):
        if folder.is_dir():
            files += sorted(p for p in folder.rglob("*") if p.is_file() or p.is_symlink())
    for path in files:
        digest.update(str(path).encode("utf-8") + b"\0")
        if path.is_symlink():
            digest.update(b"symlink:" + os.readlink(path).encode("utf-8"))
        elif path.is_file():
            digest.update(path.read_bytes())
        digest.update(b"\0")
    refs = out(
        ["for-each-ref", "--format=%(refname) %(objectname)", "refs/heads", "refs/tags"], worktree
    )
    own = f"refs/heads/{ignore_ref} "
    kept = [line for line in refs.splitlines() if not line.startswith(own)]
    digest.update("\n".join(kept).encode("utf-8"))
    return digest.hexdigest()


def blocked_push_env(base: Mapping[str, str], remote_names: list[str]) -> dict[str, str]:
    """An environment whose git cannot push: invalid push URLs, no credential helper or prompt.

    It is set through `GIT_CONFIG_*` variables, so no configuration file changes.
    """
    env = dict(base)
    try:
        count = max(0, int(env.get("GIT_CONFIG_COUNT", "0") or "0"))
    except ValueError:
        count = 0
    pairs = [("credential.helper", "")]
    pairs += [(f"remote.{name}.pushurl", BLOCKED_PUSH_URL) for name in remote_names]
    for key, value in pairs:
        env[f"GIT_CONFIG_KEY_{count}"] = key
        env[f"GIT_CONFIG_VALUE_{count}"] = value
        count += 1
    env["GIT_CONFIG_COUNT"] = str(count)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def head(cwd: Path) -> str:
    return out(["rev-parse", "HEAD"], cwd)


def current_branch(cwd: Path) -> str:
    completed = git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd, check=False)
    return completed.stdout.strip() if completed.ok else ""


def is_ancestor(cwd: Path, ancestor: str, descendant: str) -> bool:
    return git(["merge-base", "--is-ancestor", ancestor, descendant], cwd, check=False).ok


def untracked(cwd: Path) -> list[str]:
    """Files git neither tracks nor ignores."""
    listing = out(["ls-files", "--others", "--exclude-standard"], cwd)
    return [line for line in listing.splitlines() if line]


def changed_paths(cwd: Path, since: str) -> list[str]:
    """Paths that differ from commit `since`: committed, staged, unstaged or untracked."""
    committed = out(["diff", "--name-only", since, "--"], cwd).splitlines()
    return sorted({*committed, *untracked(cwd)} - {""})


def commit(cwd: Path, pathspec: list[str], message: str, *, env: Mapping[str, str]) -> bool:
    """Stage and commit `pathspec`; return False when it holds no change."""
    git(["add", "--all", "--", *pathspec], cwd, env=env)
    if git(["diff", "--cached", "--quiet"], cwd, env=env, check=False).ok:
        return False
    git(["commit", "--quiet", "-m", message], cwd, env=env)
    return True


def push(cwd: Path, url: str, sha: str, branch: str) -> None:
    """Push exactly commit `sha` to `branch`, whatever the local branch points at now."""
    git(["push", "--quiet", url, f"{sha}:refs/heads/{branch}"], cwd)
