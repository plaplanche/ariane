"""Git operations Ariane performs itself: working trees, commits, guards, delivery."""

from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ariane import logs, pi, process
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
_URL_REWRITES = (".insteadof", ".pushinsteadof")
# Markers of a push refused for authentication, in git's output (lowercase).
_AUTH_REFUSALS = (
    *("authentication failed", "could not read username", "invalid username or password"),
    *("error: 401", "error: 403", "returned error: 401", "returned error: 403"),
    "permission denied",
)
# Variables that can carry a credential; never given to an agent, to code it wrote, or to a git
# command of Ariane's other than the push (C21, ADR 0017).
# `PAT` and `_AUTH` are whole name parts, so that `PATH` and `GIT_AUTHOR_NAME` stay (ADR 0024).
SECRET_NAME = re.compile(
    r"TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API_?KEY|PRIVATE_?KEY|(?:^|_)PAT(?:_|$)|_KEY$"
    r"|DSN|DATABASE_URL|_AUTH(?:_|$)|KUBECONFIG|DOCKER_AUTH_CONFIG"
)
CREDENTIAL_CHANNELS = ("SSH_AUTH_SOCK", "SSH_ASKPASS", "GIT_ASKPASS", "SUDO_ASKPASS")
_IDENTITY_VARIABLES = frozenset(
    f"GIT_{who}_{what}" for who in ("AUTHOR", "COMMITTER") for what in ("NAME", "EMAIL", "DATE")
) | {"EMAIL"}
# Listings `git update-server-info` regenerates for the dumb HTTP transport: not part of the guard.
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
    args: list[str],
    cwd: Path,
    *,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    input_text: str | None = None,
) -> process.Completed:
    logs.emit("git.command", "git " + " ".join(args))
    if env is None:
        env = token_free_environment()
    completed = process.run(
        ["git", *_SAFE_OPTIONS, *args],
        cwd=cwd,
        timeout_s=_TIMEOUT_S,
        env=env,
        input_text=input_text,
    )
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
    git(["worktree", "add", "--quiet", "--no-track", "-b", branch, str(path), start], cwd)


def add_detached_worktree(cwd: Path, path: Path, commit: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    git(["worktree", "add", "--quiet", "--detach", str(path), commit], cwd)


# Lower case: names are compared case-folded, as case-insensitive file systems find them.
INSTRUCTION_FILES = ("claude.md", "claude.local.md", "agents.md", "agents.override.md")
INSTRUCTION_DIRS = (".claude", ".codex", ".agents", ".pi")


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


ANCESTOR_INSTRUCTIONS = ("CLAUDE.md", "CLAUDE.local.md")
PI_FILES = ("settings.json", "models.json", "AGENTS.md", "SYSTEM.md", "APPEND_SYSTEM.md")


def instruction_snapshot(
    dirs: Sequence[Path], runtime: str, env: Mapping[str, str]
) -> dict[str, str]:
    """The instruction files a reviewer runtime can load from outside the review tree, by part
    (ADR 0031): `CLAUDE.md` and `CLAUDE.local.md` in each of `dirs` and their ancestors, the
    user-level Claude file, and the global instructions and configuration of opencode, Codex or pi.
    `env` is the reviewer's environment. An absent file is a part too: creating one is a change."""
    paths: list[Path] = []
    for folder in dirs:
        for where in (folder, folder.resolve()):
            for ancestor in (where, *where.parents):
                paths += [ancestor / name for name in ANCESTOR_INSTRUCTIONS]
    home = Path(env.get("HOME") or env.get("USERPROFILE") or Path.home())
    paths.append(Path(env.get("CLAUDE_CONFIG_DIR") or home / ".claude") / "CLAUDE.md")
    if runtime == "opencode":
        config = Path(env.get("XDG_CONFIG_HOME") or home / ".config") / "opencode"
        names = ("AGENTS.md", "opencode.json", "opencode.jsonc", "config.json")
        paths += [config / name for name in names]
        if env.get("OPENCODE_CONFIG"):
            paths.append(Path(env["OPENCODE_CONFIG"]))
    elif runtime == "codex":
        codex = Path(env.get("CODEX_HOME") or home / ".codex")
        paths += [codex / name for name in ("AGENTS.md", "AGENTS.override.md", "config.toml")]
    elif runtime == "pi":
        paths += [pi.agent_dir(env, home) / name for name in PI_FILES]
    return {f"instructions {path.as_posix()}": _digest(path) for path in dict.fromkeys(paths)}


def _digest(path: Path) -> str:
    try:
        link = f"symlink:{os.readlink(path)} " if path.is_symlink() else ""
        if path.is_file():
            return link + hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        return link + ("not a file" if path.exists() else "absent")
    except OSError as exc:
        return f"unreadable ({exc.strerror})"


def base_instructions(cwd: Path, remote: str, branch: str) -> str:
    """The `CLAUDE.md` of the last fetched `remote/branch`, or "" when it has none."""
    if not path_exists_on_branch(cwd, remote, branch, "CLAUDE.md"):
        return ""
    return show_on_branch(cwd, remote, branch, "CLAUDE.md")


def push_rewrites(cwd: Path, url: str, env: Mapping[str, str] | None = None) -> list[str]:
    """`url.*.insteadof` and `url.*.pushinsteadof` settings, in any scope, that apply to `url`.

    A rewrite applies when its prefix (the value) is a prefix of `url`, git's own rule; other
    prefixes are ignored. `env` is the environment the push uses (default: Ariane's).
    """
    env = token_free_environment(env)
    listing = git(["config", "--list", "--null"], cwd, env=env).stdout
    rewrites = []
    for entry in listing.split("\0"):
        key, _, prefix = entry.partition("\n")
        kind = key.lower()
        if kind.startswith("url.") and kind.endswith(_URL_REWRITES) and url.startswith(prefix):
            rewrites.append(f"{key}={prefix}")
    return rewrites


def remove_worktree(cwd: Path, path: Path) -> None:
    git(["worktree", "remove", "--force", str(path)], cwd)


@dataclass(frozen=True)
class GitState:
    """`state`'s snapshot, and the branch checked out and its commit ("" when detached)."""

    snapshot: dict[str, str]
    branch: str
    head: str


def config_snapshot(
    worktree: Path, *, ignore_ref: str, watch_refs: Sequence[str] = ()
) -> dict[str, str]:
    """Everything that makes git run code or reroute a push, by part (`state`)."""
    return state(worktree, ignore_ref=ignore_ref, watch_refs=watch_refs).snapshot


def state(worktree: Path, *, ignore_ref: str, watch_refs: Sequence[str] = ()) -> GitState:
    """Everything that makes git run code or reroute a push, by part, read by three git processes.

    Parts: each file of the shared configuration, hooks and info folders and of this working
    tree's own configuration (as a digest), the shared `config`'s text (`keys <path>`, the very
    bytes of its digest: `runs.foreign_changes` lists both texts with `config_keys` when they
    differ, to compare that file by key), every setting of every configuration scope git reads
    (its value is its positions among the settings of the same key: reordering is a change),
    the local branches and tags except `ignore_ref` (the ticket's own), and the full ref names
    in `watch_refs`. A difference between two snapshots taken around untrusted code means that
    code edited git itself; `snapshot_changes` names what changed."""
    dirs = out(["rev-parse", "--path-format=absolute", "--git-common-dir", "--git-dir"], worktree)
    common, private = (Path(line) for line in dirs.splitlines())
    files = [common / "config", private / "config.worktree"]
    for folder in (common / "hooks", common / "info"):
        if folder.is_dir():
            found = sorted(p for p in folder.rglob("*") if p.is_file() or p.is_symlink())
            files += [
                p for p in found if p.relative_to(common).as_posix() not in _GENERATED_LISTINGS
            ]
    snapshot = {}
    shared = common / "config"
    for path in files:
        if path.is_symlink():
            content = b"symlink:" + os.readlink(path).encode("utf-8")
        elif path.is_file():
            content = path.read_bytes()
        else:
            continue
        snapshot[f"file {path.as_posix()}"] = hashlib.sha256(content).hexdigest()[:16]
        if path == shared:  # one read: the keys always match the digest, whoever writes
            snapshot[f"keys {shared.as_posix()}"] = content.decode("utf-8", errors="replace")
    scopes = out(["config", "--list", "--show-origin", "--show-scope"], worktree)
    positions: dict[str, list[str]] = {}
    seen: Counter[str] = Counter()
    for line in scopes.splitlines():
        name = line.split("\t", 2)[-1].partition("=")[0]
        positions.setdefault(f"setting {line}", []).append(str(seen[name]))
        seen[name] += 1
    snapshot |= {part: ",".join(at) for part, at in positions.items()}
    patterns = ["refs/heads", "refs/tags", *watch_refs]  # one process for the refs and HEAD
    listing = out(
        ["for-each-ref", "--format=%(refname) %(objectname) %(HEAD)", *patterns], worktree
    )
    own = f"refs/heads/{ignore_ref}"
    refs: dict[str, str] = {}
    branch = ""
    for line in listing.splitlines():
        ref, sha, *current = line.split()  # `*` last when HEAD is this ref
        refs[ref] = sha
        if current == ["*"] and ref.startswith("refs/heads/"):
            branch = ref.removeprefix("refs/heads/")
        if ref != own and ref.startswith(("refs/heads/", "refs/tags/")):
            snapshot[f"ref {ref}"] = sha
    for ref in watch_refs:
        snapshot[f"ref {ref}"] = refs.get(ref, "")
    return GitState(snapshot, branch, refs.get(f"refs/heads/{branch}", "") if branch else "")


def config_keys(cwd: Path, text: str) -> str:
    """`git config --list --null` of a configuration file's `text`, read from standard input."""
    listing = git(["config", "--file", "-", "--list", "--null"], cwd, check=False, input_text=text)
    return listing.stdout if listing.ok else "unreadable"


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
    pairs = [("credential.helper", "")]
    pairs += [(f"remote.{name}.pushurl", BLOCKED_PUSH_URL) for name in remote_names]
    return _with_config(base, pairs)


def head(cwd: Path) -> str:
    return out(["rev-parse", "HEAD"], cwd)


def detached_head(cwd: Path) -> str:
    """The commit of a detached HEAD, or "" when HEAD is a branch, read by one git process."""
    sha, _, name = out(["rev-parse", "HEAD", "--symbolic-full-name", "HEAD"], cwd).partition("\n")
    return sha if name == "HEAD" else ""


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


@dataclass(frozen=True)
class Changes:
    """What changed between two commits, as the reviewer is shown it."""

    diff: str  # `git diff`
    name_status: str  # `git diff --name-status`
    changed_lines: int  # added plus deleted lines; a binary file counts 0 (ADR 0046)


def changes(cwd: Path, since: str, until: str, exclude: str) -> Changes:
    """The changes from `since` to `until`, without the paths under `exclude`, read by one git
    process (ADR 0053): `--raw` and `--numstat` lines, a blank line, then the patch."""
    pathspec = ["--", ".", f":(exclude){exclude}"]
    listing = out([*_PLAIN_DIFF, "--raw", "--numstat", "-p", since, until, *pathspec], cwd)
    head, _, patch = listing.partition("\n\n")
    raw = [line for line in head.split("\n") if line.startswith(":")]  # line feeds only, not U+2028
    # A raw line is ":<mode> <mode> <object> <object> <status>\t<paths>"; --name-status prints
    # what follows the fourth space.
    name_status = "\n".join(line.split(" ", 4)[4] for line in raw)
    counts = (line.split("\t", 2)[:2] for line in head.split("\n") if line[:1] not in ":")
    lines = sum(int(n) for pair in counts for n in pair if n.isdigit())
    return Changes(patch, name_status, lines)


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
    # No check that the index holds a change first: only a refused commit pays for it.
    args = ["commit", "--quiet", "-m", message]
    done = git(args, cwd, env={**env, **_identity(os.environ)}, check=False)
    if done.ok:
        return True
    if git([*_PLAIN_DIFF, "--cached", "--quiet"], cwd, env=env, check=False).ok:
        return False
    raise GitError(redact(f"git commit failed:\n{done.output.strip()}"))


def _identity(environ: Mapping[str, str]) -> dict[str, str]:
    """Ariane's git identity variables: its commits carry them, untrusted code does not get
    them (the environment of agents and checks is an allow list, ADR 0024)."""
    return {k: v for k, v in environ.items() if k.upper() in _IDENTITY_VARIABLES}


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
    watched = [r for r in {*refs, *refs_before} if r in (own, base) or r.startswith("refs/tags/")]
    changed = sorted(r for r in watched if refs.get(r) != refs_before.get(r))
    old, new = refs_before.get(base), refs.get(base)
    if base in changed and old and new and fast_forwarded(cwd, url, base_branch, old, new):
        changed.remove(base)
    return changed
