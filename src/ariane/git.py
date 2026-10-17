"""Git operations Ariane performs itself: working trees, commits, guards, delivery."""

from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
from collections.abc import Mapping, Sequence
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
    # No `ext::` transport: a URL must never run a command.
    *("-c", "protocol.ext.allow=never"),
]
# Every diff Ariane runs: no external diff driver or textconv filter from the configuration.
_PLAIN_DIFF = ["diff", "--no-ext-diff", "--no-textconv"]
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
# Variables that can carry a credential; never given to an agent, to code it wrote, or to a git
# command of Ariane's other than the push (C21, ADR 0017).
SECRET_NAME = re.compile(r"TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API_?KEY|PRIVATE_?KEY")
CREDENTIAL_CHANNELS = ("SSH_AUTH_SOCK", "SSH_ASKPASS", "GIT_ASKPASS", "SUDO_ASKPASS")
_GENERATED_LISTINGS = frozenset({"info/refs", "info/packs"})


class GitError(Exception):
    """A git command failed."""


def token_free_environment(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """`base` (default: Ariane's environment) without any variable the credential filter withholds.

    The tracker token is not in Ariane's environment once the CLI has read it; this also drops
    anything else that looks like a credential, so only `push` ever carries one.
    """
    source = os.environ if base is None else base
    return {
        name: value
        for name, value in source.items()
        if name.upper() not in CREDENTIAL_CHANNELS and not SECRET_NAME.search(name.upper())
    }


def git(
    args: list[str], cwd: Path, *, env: Mapping[str, str] | None = None, check: bool = True
) -> process.Completed:
    logs.emit("git.command", "git " + " ".join(args))
    if env is None:
        env = token_free_environment()
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


def worktree_of(cwd: Path, branch: str) -> Path | None:
    """The working tree where `branch` is checked out, if any."""
    current: Path | None = None
    for line in out(["worktree", "list", "--porcelain"], cwd).splitlines():
        if line.startswith("worktree "):
            current = Path(line.removeprefix("worktree "))
        elif line == f"branch refs/heads/{branch}":
            return current
    return None


def merge_base(cwd: Path, first: str, second: str) -> str:
    return out(["merge-base", first, second], cwd)


def commit_messages(cwd: Path, since: str, until: str) -> str:
    """The messages of the commits in `since..until`, oldest first."""
    return out(["log", "--reverse", "--format=%B", f"{since}..{until}"], cwd)


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


# Lower case: names are compared case-folded, as case-insensitive file systems find them.
INSTRUCTION_FILES = ("claude.md", "claude.local.md", "agents.md")
INSTRUCTION_DIRS = (".claude",)


def add_reviewer_worktree(cwd: Path, path: Path, commit: str) -> None:
    """A detached worktree of `commit` without the files an agent would load as configuration:
    every instruction file and `.claude/` directory, at any depth (ADR 0031)."""
    add_detached_worktree(cwd, path, commit)
    try:
        root = path.resolve()
        for here, dirs, files in os.walk(path):
            if Path(here) == path / ".git":
                continue
            dirs[:] = [d for d in dirs if d != ".git"]
            for name in files:
                link = Path(here) / name
                if name.casefold() in INSTRUCTION_FILES or _leaves_tree(link, root):
                    link.unlink()
            for name in list(dirs):
                target = Path(here) / name
                if name.casefold() not in INSTRUCTION_DIRS and not _leaves_tree(target, root):
                    continue
                dirs.remove(name)
                if target.is_symlink():
                    target.unlink()
                else:
                    shutil.rmtree(target)
    except BaseException:
        remove_worktree(cwd, path)
        raise


def _leaves_tree(link: Path, root: Path) -> bool:
    """A symlink whose target is outside `root`: reading through it could load files from there."""
    return link.is_symlink() and not link.resolve().is_relative_to(root)


def base_instructions(cwd: Path, remote: str, branch: str) -> str:
    """The `CLAUDE.md` of the last fetched `remote/branch`, or "" when it has none."""
    if not path_exists_on_branch(cwd, remote, branch, "CLAUDE.md"):
        return ""
    return show_on_branch(cwd, remote, branch, "CLAUDE.md")


def push_rewrites(cwd: Path, url: str) -> list[str]:
    """`url.*.insteadof` and `url.*.pushinsteadof` settings that apply to `url`.

    A rewrite applies when its prefix (the value) is a prefix of `url`, git's own rule. Only the
    local, worktree and command scopes are listed; other prefixes are ignored.
    """
    listing = git(["config", "--list", "--show-scope"], cwd).stdout
    rewrites = []
    for line in listing.splitlines():
        scope, _, setting = line.partition("\t")
        key, _, prefix = setting.partition("=")
        rewriting = key.lower().startswith("url.") and key.lower().endswith(
            (".insteadof", ".pushinsteadof")
        )
        if scope in ("local", "worktree", "command") and rewriting and url.startswith(prefix):
            rewrites.append(setting)
    return rewrites


def remove_worktree(cwd: Path, path: Path) -> None:
    git(["worktree", "remove", "--force", str(path)], cwd)


def config_snapshot(
    worktree: Path, *, ignore_ref: str, watch_refs: Sequence[str] = ()
) -> dict[str, str]:
    """Everything that makes git run code or reroute a push, by part.

    Parts: each file of the shared configuration, hooks and info folders and of this working
    tree's own configuration (as a digest), every configuration scope git reads (global
    included), the local branches and tags except branch `ignore_ref` (the ticket's own), and
    the refs in `watch_refs` (the remote-tracking ref of the base branch).
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
    for ref in watch_refs:
        found = git(["rev-parse", "--verify", "--quiet", ref], worktree, check=False)
        snapshot[f"ref {ref}"] = found.stdout.strip() if found.ok else ""
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
    committed = out([*_PLAIN_DIFF, "--name-only", since, "--"], cwd).splitlines()
    return sorted({*committed, *untracked(cwd)} - {""})


def diff(cwd: Path, since: str, until: str, exclude: str) -> str:
    """The diff from `since` to `until`, without the paths under `exclude`."""
    return out([*_PLAIN_DIFF, since, until, "--", ".", f":(exclude){exclude}"], cwd)


def status(cwd: Path) -> str:
    """What git reports as changed or untracked (ignored files left out)."""
    return out(["status", "--porcelain", "--untracked-files=all"], cwd)


def changed_between(cwd: Path, since: str, until: str) -> list[str]:
    """Paths that differ between commits `since` and `until`."""
    return out([*_PLAIN_DIFF, "--name-only", since, until, "--"], cwd).splitlines()


def committed_paths(cwd: Path, since: str, pathspec: str) -> list[str]:
    """Paths under `pathspec` changed by commits since `since`."""
    listing = out([*_PLAIN_DIFF, "--name-only", since, "HEAD", "--", pathspec], cwd)
    return [line for line in listing.splitlines() if line]


def commit(
    cwd: Path,
    pathspec: list[str],
    message: str,
    *,
    env: Mapping[str, str],
    tolerate_ignored: bool = False,
    unstage: Sequence[str] = (),
) -> bool:
    """Commit the changes under `pathspec` only; return False when it holds none.

    An ignored path makes `git add` fail: that raises `GitError`, unless `tolerate_ignored`, which
    returns False instead. The index is reset to HEAD first: whatever an agent or a check staged
    does not ride along. Each path in `unstage` is dropped from the index before the add, so that
    it is committed as the regular file now in the working tree.
    """
    git(["reset", "--quiet"], cwd, env=env)
    for path in unstage:
        # A link committed earlier is not kept as a link when checked out as a plain file.
        git(["rm", "--cached", "--quiet", "--ignore-unmatch", "--", path], cwd, env=env)
    # English messages, so that "ignored" can be recognised whatever the user's locale.
    added = git(["add", "--all", "--", *pathspec], cwd, env={**env, "LC_ALL": "C"}, check=False)
    if not added.ok:
        if tolerate_ignored and "ignored" in added.output:
            return False
        raise GitError(redact(f"git add failed:\n{added.output.strip()}"))
    if git([*_PLAIN_DIFF, "--cached", "--quiet"], cwd, env=env, check=False).ok:
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


def fast_forwarded(cwd: Path, url: str, branch: str, old: str, new: str) -> bool:
    """Whether the remote `branch` moved from `old` to `new` by a fast-forward (fetches `new`)."""
    if git(["cat-file", "-e", f"{old}^{{commit}}"], cwd, check=False).ok is False:
        return False
    # Fetched from the URL, not the remote: the base branch's remote-tracking ref is part of the
    # guard, and a fetch from a named remote would update it.
    fetched = git(["fetch", "--quiet", url, f"refs/heads/{branch}"], cwd, check=False)
    if not fetched.ok:
        return False
    return is_ancestor(cwd, old, new)


def remote_changes(
    cwd: Path, url: str, remote: str, branch: str, base_branch: str, refs_before: dict[str, str]
) -> list[str]:
    """Watched refs of `url` that differ from `refs_before` (C11, ADR 0017).

    Watched: the ticket's branch, the base branch (a fast-forward, a merge, is tolerated) and
    every tag. Other people's branches are ignored.
    """
    refs = remote_refs(cwd, url)
    base = f"refs/heads/{base_branch}"
    own = f"refs/heads/{branch}"
    changed = sorted(
        r
        for r in {*refs, *refs_before}
        if (r in (own, base) or r.startswith("refs/tags/")) and refs.get(r) != refs_before.get(r)
    )
    if (
        base in changed
        and base in refs
        and base in refs_before
        and fast_forwarded(cwd, url, base_branch, refs_before[base], refs[base])
    ):
        changed.remove(base)
    return changed
