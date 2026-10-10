"""Git operations Ariane performs itself: working trees, commits, guards, delivery."""

from __future__ import annotations

import base64
import hashlib
import os
from collections.abc import Mapping
from pathlib import Path

from ariane import logs, process
from ariane.redact import redact

# The push URL an agent's git sees: any plain `git push` from its environment fails.
BLOCKED_PUSH_URL = "ariane-blocked://agents-never-push"
_TIMEOUT_S = 300
# Ariane's own git commands never run hooks or a filesystem monitor: after an agent session,
# both could be code the agent planted (C21: the guard comes from Ariane, not the working tree).
_SAFE_OPTIONS = [
    *("-c", f"core.hooksPath={os.devnull}"),
    *("-c", "core.fsmonitor=false"),
    *("-c", "core.quotepath=off"),  # non-ASCII paths stay readable
    # No background housekeeping: it rewrites files (`info/refs`) in the middle of a ticket.
    *("-c", "gc.auto=0"),
    *("-c", "maintenance.auto=false"),
]
# Listings `git update-server-info` regenerates for the dumb HTTP transport: not part of the guard.
# Markers of a push refused for authentication, in git's output (lowercase).
_AUTH_REFUSALS = (
    "authentication failed",
    "could not read username",
    "invalid username or password",
    "error: 401",
    "error: 403",
    "returned error: 401",
    "returned error: 403",
    "permission denied",
)
_GENERATED_LISTINGS = frozenset({"info/refs", "info/packs"})


class GitError(Exception):
    """A git command failed."""


def git(
    args: list[str], cwd: Path, *, env: Mapping[str, str] | None = None, check: bool = True
) -> process.Completed:
    logs.emit("git.command", "git " + " ".join(args))
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


def path_exists_on_branch(cwd: Path, remote: str, branch: str, path: str) -> bool:
    """Whether `path` is in the last fetched `remote/branch`."""
    ref = f"refs/remotes/{remote}/{branch}:{path}"
    return git(["cat-file", "-e", ref], cwd, check=False).ok


def show_on_branch(cwd: Path, remote: str, branch: str, path: str) -> str:
    return out(["show", f"refs/remotes/{remote}/{branch}:{path}"], cwd)


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


def add_detached_worktree(cwd: Path, path: Path, commit: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    git(["worktree", "add", "--quiet", "--detach", str(path), commit], cwd)


def remove_worktree(cwd: Path, path: Path) -> None:
    git(["worktree", "remove", "--force", str(path)], cwd)


def config_snapshot(worktree: Path, *, ignore_ref: str) -> dict[str, str]:
    """Everything that makes git run code or reroute a push, by part.

    Parts: each file of the shared configuration, hooks and info folders and of this working
    tree's own configuration (as a digest), every configuration scope git reads (global
    included), and the local branches and tags except branch `ignore_ref` (the ticket's own).
    Ariane compares two snapshots taken before and after untrusted code runs: a difference
    means that code edited git itself, and `snapshot_changes` names what changed.
    """
    common = Path(out(["rev-parse", "--path-format=absolute", "--git-common-dir"], worktree))
    private = Path(out(["rev-parse", "--path-format=absolute", "--git-dir"], worktree))
    files = [common / "config", private / "config.worktree"]
    for folder in (common / "hooks", common / "info"):
        if folder.is_dir():
            files += sorted(
                p
                for p in folder.rglob("*")
                if (p.is_file() or p.is_symlink())
                and p.relative_to(common).as_posix() not in _GENERATED_LISTINGS
            )
    snapshot = {}
    for path in files:
        if path.is_symlink():
            content = b"symlink:" + os.readlink(path).encode("utf-8")
        elif path.is_file():
            content = path.read_bytes()
        else:
            continue
        snapshot[f"file {path.as_posix()}"] = hashlib.sha256(content).hexdigest()[:16]
    scopes = out(["config", "--list", "--show-origin", "--show-scope"], worktree)
    for line in scopes.splitlines():
        snapshot[f"setting {line}"] = ""
    refs = out(
        ["for-each-ref", "--format=%(refname) %(objectname)", "refs/heads", "refs/tags"], worktree
    )
    own = f"refs/heads/{ignore_ref} "
    for line in refs.splitlines():
        if not line.startswith(own):
            ref, _, sha = line.partition(" ")
            snapshot[f"ref {ref}"] = sha
    return snapshot


def snapshot_changes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """What differs between two snapshots, one line per added, removed or changed part."""
    lines = []
    for key in sorted({*before, *after}):
        if key not in after:
            lines.append(f"removed: {key}")
        elif key not in before:
            lines.append(f"added: {key}")
        elif before[key] != after[key]:
            lines.append(f"changed: {key}")
    return lines


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


def ignored(cwd: Path) -> set[str]:
    """Files and folders git ignores, as listed by git (a folder counts as one entry)."""
    listing = out(["ls-files", "--others", "--ignored", "--exclude-standard", "--directory"], cwd)
    return {line for line in listing.splitlines() if line}


def changed_paths(cwd: Path, since: str) -> list[str]:
    """Paths that differ from commit `since`: committed, staged, unstaged or untracked."""
    committed = out(["diff", "--name-only", since, "--"], cwd).splitlines()
    return sorted({*committed, *untracked(cwd)} - {""})


def committed_paths(cwd: Path, since: str, pathspec: str) -> list[str]:
    """Paths under `pathspec` changed by commits since `since`."""
    listing = out(["diff", "--name-only", since, "HEAD", "--", pathspec], cwd)
    return [line for line in listing.splitlines() if line]


def commit(cwd: Path, pathspec: list[str], message: str, *, env: Mapping[str, str]) -> bool:
    """Commit the changes under `pathspec` only; return False when it holds none.

    The index is reset to HEAD first: whatever an agent or a check staged does not ride along.
    """
    git(["reset", "--quiet"], cwd, env=env)
    git(["add", "--all", "--", *pathspec], cwd, env=env)
    if git(["diff", "--cached", "--quiet"], cwd, env=env, check=False).ok:
        return False
    git(["commit", "--quiet", "-m", message], cwd, env=env)
    return True


def _with_config(base: Mapping[str, str], pairs: list[tuple[str, str]]) -> dict[str, str]:
    env = dict(base)
    try:
        count = max(0, int(env.get("GIT_CONFIG_COUNT", "0") or "0"))
    except ValueError:
        count = 0
    for key, value in pairs:
        env[f"GIT_CONFIG_KEY_{count}"] = key
        env[f"GIT_CONFIG_VALUE_{count}"] = value
        count += 1
    env["GIT_CONFIG_COUNT"] = str(count)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def push_env(base: Mapping[str, str], token: str) -> dict[str, str]:
    """The environment of Ariane's push: the token as an HTTP header for this push only.

    The machine's credential helpers are disabled; nothing is written to a file or an argument.
    """
    pairs = [("credential.helper", "")]
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode("ascii")
        pairs.append(("http.extraHeader", f"Authorization: Basic {basic}"))
    return _with_config(base, pairs)


def _refused_for_authentication(output: str) -> bool:
    lowered = output.lower()
    return any(marker in lowered for marker in _AUTH_REFUSALS)


def push(
    cwd: Path,
    url: str,
    sha: str,
    branch: str,
    *,
    token: str = "",
    environ: Mapping[str, str] | None = None,
) -> str:
    """Push exactly commit `sha` to `branch`, whatever the local branch points at now.

    With a token, the push carries it as an authorization header. Without one, or when that push
    is refused for authentication, Ariane pushes once more without the header (a cloud sandbox's
    proxy may supply credentials). Returns how the push went, for the journal.
    """
    base = os.environ if environ is None else environ
    args = ["push", "--quiet", url, f"{sha}:refs/heads/{branch}"]
    secrets = [token] if token else []
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode("ascii")
        secrets.append(basic)
        first = git(args, cwd, env=push_env(base, token), check=False)
        if first.ok:
            return "with the tracker token as an authorization header"
        if not _refused_for_authentication(first.output):
            raise GitError(redact(f"git push failed:\n{first.output.strip()}", secrets))
        how = "without a header, after the push with the token header was refused"
    else:
        how = "without a header (no tracker token set)"
    second = git(args, cwd, env=push_env(base, ""), check=False)
    if not second.ok:
        raise GitError(redact(f"git push failed:\n{second.output.strip()}", secrets))
    return how


def fast_forwarded(cwd: Path, remote: str, branch: str, old: str, new: str) -> bool:
    """Whether the remote `branch` moved from `old` to `new` by a fast-forward (fetches `new`)."""
    if git(["cat-file", "-e", f"{old}^{{commit}}"], cwd, check=False).ok is False:
        return False
    fetched = git(
        ["fetch", "--quiet", remote, f"+refs/heads/{branch}:refs/remotes/{remote}/{branch}"],
        cwd,
        check=False,
    )
    if not fetched.ok:
        return False
    return is_ancestor(cwd, old, new)
