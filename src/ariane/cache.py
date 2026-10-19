"""Dependency caches of the replay (C9, ADR 0054): folders stored by the content of their key
files and copied into a fresh tree instead of being rebuilt by their setup."""

from __future__ import annotations

import contextlib
import functools
import hashlib
import json
import os
import shutil
import stat
import sys
import time
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

FOLDER = "cache"  # `<repo>.ariane/cache/<key>/`
DEFAULT_KEEP = 5
ENTRY = "entry.json"  # written last, inside the temporary entry: what makes an entry complete
DATA = "data"
PARTIAL = ".partial-"  # a temporary entry's name: `<key>.partial-<random>`
LOCK = ".lock"  # `<store>/.lock`: held to restore, publish and prune (`_locked`)
PARTIAL_AGE_S = 24 * 3600  # a temporary entry older than this was left by a killed run
_FICLONE = 0x40049409  # Linux ioctl: clone a file's extents (Btrfs, XFS, ...)
_WRITE = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH


class CacheConfigError(ValueError):
    """A `[[project.cache]]` table is invalid; the message names the key."""


@dataclass(frozen=True)
class CacheConfig:
    """`[[project.cache]]`: the folder `path`, the `key` files that identify it, the `setup`
    command that builds that folder alone, and how many entries of that path to `keep`."""

    path: str
    key: tuple[str, ...]
    setup: tuple[str, ...]
    keep: int = DEFAULT_KEEP


@dataclass(frozen=True)
class Used:
    """What one cache did in one tree: copied from the store (`hit`), or built by its setup."""

    path: str
    key: str
    hit: bool
    note: str = ""  # a build not stored, and why

    def text(self) -> str:
        done = "hit" if self.hit else "built" + (f", {self.note}" if self.note else ", stored")
        return f"`{self.path}` {done} (key `{self.key[:12]}`)"


def store_path(repo_root: Path) -> Path:
    """`<repo>.ariane/cache`, next to the tickets' working trees."""
    return repo_root.parent / f"{repo_root.name}.ariane" / FOLDER


def parse(raw: Any) -> tuple[CacheConfig, ...]:
    """The `[[project.cache]]` tables; a CacheConfigError names the faulty key."""
    if not isinstance(raw, list) or not all(isinstance(v, dict) for v in raw):
        raise CacheConfigError("project.cache: expected a list of tables ([[project.cache]])")
    caches: list[CacheConfig] = []
    for index, item in enumerate(raw):
        where = f"project.cache[{index}]"
        for name in item:
            if name not in ("path", "key", "setup", "keep"):
                raise CacheConfigError(f"{where}.{name}: unknown key")
        path = _relative(item.get("path"), f"{where}.path")
        if any(_overlap(path, c.path) for c in caches):
            raise CacheConfigError(f"{where}.path: overlaps another cache's path")
        key = item.get("key")
        if not isinstance(key, list) or not key:
            raise CacheConfigError(f"{where}.key: expected a non-empty list of file paths")
        keys = tuple(_relative(k, f"{where}.key") for k in key)
        setup = item.get("setup")
        if (
            not isinstance(setup, list)
            or not setup
            or not all(isinstance(a, str) and a for a in setup)
        ):
            raise CacheConfigError(
                f"{where}.setup: expected a non-empty list of strings"
                " (an argument list, never a shell string)"
            )
        keep = item.get("keep", DEFAULT_KEEP)
        if isinstance(keep, bool) or not isinstance(keep, int) or keep <= 0:
            raise CacheConfigError(f"{where}.keep: expected a positive integer")
        caches.append(CacheConfig(path, keys, tuple(setup), keep))
    return tuple(caches)


def _relative(value: Any, where: str) -> str:
    """A folder or file inside the tree, written with `/`: not absolute, no `..`, not `.git`."""
    if not isinstance(value, str) or not value.strip():
        raise CacheConfigError(f"{where}: expected a non-empty path relative to the tree")
    parts = PurePosixPath(value.replace("\\", "/")).parts
    if (
        not parts
        or value.startswith(("/", "\\"))
        or ":" in parts[0]
        or any(p in ("..", ".git") for p in parts)
        or parts == (".",)
    ):
        raise CacheConfigError(f"{where}: {value!r} is not a path inside the tree")
    return "/".join(p for p in parts if p != ".")


def _overlap(a: str, b: str) -> bool:
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def key_of(tree: Path, cache: CacheConfig) -> str:
    """SHA-256 of the `setup` command and of each key file's name and content in `tree` (a
    missing key file counts as missing, not as empty)."""
    digest = hashlib.sha256(b"ariane-cache-1\0")
    digest.update(json.dumps(list(cache.setup)).encode() + b"\0")
    for name in cache.key:
        digest.update(name.encode() + b"\0")
        try:
            content = (tree / name).read_bytes()
        except OSError:
            digest.update(b"missing\0")
            continue
        digest.update(f"{len(content)}\0".encode() + content)
    return digest.hexdigest()


def prepare(
    caches: Sequence[CacheConfig],
    tree: Path,
    store: Path,
    build: Callable[[tuple[str, ...]], None],
    *,
    fill: bool,
    validate: Callable[[], None] = lambda: None,
) -> list[Used]:
    """Each cache in `tree`: copied from a complete entry of `store`, else built by `build(setup)`
    (which raises on failure) and, when `fill` (a replay tree, never the agent's), stored. A path
    that crosses a symbolic link, or a folder the commit already has there, is never written by
    the cache: its setup builds it and nothing is stored. `validate` (which raises to stop) checks
    the tree after each build, before anything is stored, and after each folder copied from the
    store, before any other setup runs: a copy skips its setup, not the setup's checks."""
    used: list[Used] = []
    for cache in caches:
        key = key_of(tree, cache)
        target = tree / cache.path
        entry = store / key
        failed: str | None = None  # the entry that could not be copied, replaced if rebuilt
        blocked = _crossing(tree, cache.path)
        if not blocked and os.path.lexists(target):
            blocked = "the commit already has that path"
        if not blocked:
            hit, failed = _restore(store, entry, cache, key, tree)
            if hit:
                used.append(Used(cache.path, key, hit=True))
                validate()  # before another cache's setup runs, which could hide what it left
                continue
        build(cache.setup)
        validate()
        note = ""
        if not fill:
            note = "not stored (the agent's tree never fills the store)"
        elif key_of(tree, cache) != key:
            note = "not stored (its setup changed the key files)"
        elif blocked or (blocked := _crossing(tree, cache.path)):
            note = f"not stored ({blocked})"
        elif not target.is_dir() or target.is_symlink():
            note = "not stored (its setup made no folder there)"
        else:
            note = _store(target, store, entry, cache, key, failed)
        used.append(Used(cache.path, key, hit=False, note=note))
    return used


def _crossing(tree: Path, path: str) -> str:
    """Why `path` cannot be written safely in `tree`: a folder on the way that is a symbolic link
    or not a folder (the write would land elsewhere); "" when every existing one is a folder."""
    here = tree
    for part in path.split("/")[:-1]:
        here = here / part
        if here.is_symlink() or (os.path.lexists(here) and not here.is_dir()):
            return f"`{here.relative_to(tree).as_posix()}` is a link or a file"
    return ""


@contextlib.contextmanager
def _locked(store: Path) -> Iterator[None]:
    """Hold `store/.lock` for the block: restoring an entry, publishing or replacing one and
    pruning never interleave, so an entry is never removed while another tree reads or has just
    published it. The system frees the lock when its process dies."""
    store.mkdir(parents=True, exist_ok=True)
    with (store / LOCK).open("a+b") as file:
        if sys.platform == "win32":
            import msvcrt

            file.seek(0)
            while True:
                try:
                    msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.01)
            try:
                yield
            finally:
                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)


def _read_entry(entry: Path, cache: CacheConfig, key: str) -> str | None:
    """The `id` of a complete entry for this cache and key, or None when it is not one."""
    try:
        meta = json.loads((entry / ENTRY).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        isinstance(meta, dict)
        and meta.get("path") == cache.path
        and meta.get("key") == key
        and (entry / DATA).is_dir()
    ):
        return str(meta.get("id", ""))
    return None


def _restore(
    store: Path, entry: Path, cache: CacheConfig, key: str, tree: Path
) -> tuple[bool, str | None]:
    """Copy the entry's folder to a hidden folder next to `cache.path`, then rename it there: the
    tree sees the whole folder or nothing. An entry that is incomplete or cannot be read is not
    trusted, even partly: what was written is removed and the caller builds the folder. Returns
    whether it was copied, and the `id` of a complete entry whose folder could not be copied."""
    parts = cache.path.split("/")
    made: list[Path] = []  # the parent folders this restore created, removed if it fails
    staging: Path | None = None
    if not entry.is_dir():
        return False, None  # no entry: the store is not even created (nor its lock)
    with _locked(store):
        found = _read_entry(entry, cache, key)
        if found is None:
            return False, None
        try:
            parent = tree
            for part in parts[:-1]:
                parent = parent / part
                if not parent.exists():
                    os.mkdir(parent)
                    made.append(parent)
            staging = parent / f".{parts[-1]}{PARTIAL}{uuid.uuid4().hex}"
            _copy(entry / DATA, staging, writable=True)
            os.rename(staging, tree / cache.path)
        except OSError:
            if staging is not None:
                remove_tree(staging)
            for folder in reversed(made):
                with contextlib.suppress(OSError):
                    os.rmdir(folder)
            return False, found
        with contextlib.suppress(OSError):
            os.utime(entry / ENTRY)  # its last use: what `prune` keeps
    return True, None


def _store(
    target: Path, store: Path, entry: Path, cache: CacheConfig, key: str, failed: str | None
) -> str:
    """Copy `target` to a temporary entry, make it read-only, write its `entry.json`, then, under
    the store's lock, move aside an entry of that key that is unreadable or is `failed` (the one
    whose folder this tree could not copy) and rename the temporary entry to `entry`: a reader
    sees a complete entry or none, and an entry another tree published meanwhile is kept.
    Returns "" or why it was not stored."""
    temporary = store / f"{key}{PARTIAL}{uuid.uuid4().hex}"
    aside = store / f"{key}{PARTIAL}{uuid.uuid4().hex}"
    try:
        store.mkdir(parents=True, exist_ok=True)
        temporary.mkdir()
        _copy(target, temporary / DATA, writable=False)
        meta = {"path": cache.path, "key": key, "setup": list(cache.setup), "id": uuid.uuid4().hex}
        (temporary / ENTRY).write_text(json.dumps(meta), encoding="utf-8")
        with _locked(store):
            found = _read_entry(entry, cache, key)
            if found is not None and found != failed:
                remove_tree(temporary)
                return "stored by another tree at the same time"
            if os.path.lexists(entry):
                os.rename(entry, aside)  # never trusted again; removed below, or by `prune`
            os.rename(temporary, entry)
    except OSError as exc:
        remove_tree(temporary)
        return f"not stored ({exc})"
    finally:
        remove_tree(aside)
    return ""


def _copy(source: Path, target: Path, *, writable: bool, clones: list[bool] | None = None) -> None:
    """Copy a folder file by file, as copy-on-write clones where the file system supports them,
    else as plain copies; never hard links, so a write into one copy leaves the other unchanged.
    Symbolic links stay links. `writable` False makes the copy read-only. `clones` holds whether
    cloning still works: after a first refusal the rest of the folder is copied plainly."""
    clones = [True] if clones is None else clones
    target.mkdir(parents=True, exist_ok=True)
    with os.scandir(source) as entries:
        for item in entries:
            to = target / item.name
            if item.is_symlink():
                os.symlink(os.readlink(item.path), to, target_is_directory=item.is_dir())
            elif item.is_dir(follow_symlinks=False):
                _copy(Path(item.path), to, writable=writable, clones=clones)
            else:
                if not (clones[0] and _clone(item.path, to)):
                    clones[0] = False
                    shutil.copyfile(item.path, to)
                mode = stat.S_IMODE(item.stat(follow_symlinks=False).st_mode)
                os.chmod(to, mode | stat.S_IWUSR if writable else mode & ~_WRITE)
    if not writable:
        os.chmod(target, stat.S_IMODE(target.stat().st_mode) & ~_WRITE)


def _clone(source: str, target: Path) -> bool:
    """A copy-on-write clone of a file: `FICLONE` on Linux (Btrfs, XFS...), `clonefile` on macOS
    (APFS); False when the file system or the platform cannot clone, and nothing is left."""
    if sys.platform == "linux":
        import fcntl

        try:
            with open(source, "rb") as src, open(target, "wb") as dst:
                fcntl.ioctl(dst.fileno(), _FICLONE, src.fileno())
            return True
        except OSError:
            target.unlink(missing_ok=True)
            return False
    if sys.platform == "darwin":
        clonefile = _clonefile()
        return clonefile is not None and clonefile(os.fsencode(source), os.fsencode(target), 0) == 0
    return False


@functools.cache
def _clonefile() -> Any:
    """macOS `clonefile(2)` from the C library, or None when it cannot be loaded."""
    import ctypes

    try:
        return ctypes.CDLL(None, use_errno=True).clonefile
    except (OSError, AttributeError):
        return None


def remove_tree(path: Path) -> None:
    """Remove a folder, read-only files and folders included; nothing when it does not exist."""
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    if not path.exists():
        return
    for root, dirs, files in os.walk(path):
        for name in [*dirs, *files]:
            item = Path(root) / name
            if not item.is_symlink():
                with contextlib.suppress(OSError):
                    os.chmod(item, stat.S_IMODE(item.stat().st_mode) | stat.S_IWUSR)
    with contextlib.suppress(OSError):
        os.chmod(path, stat.S_IMODE(path.stat().st_mode) | stat.S_IWUSR)
    shutil.rmtree(path, ignore_errors=True)


def prune(store: Path, caches: Sequence[CacheConfig], now: float | None = None) -> list[str]:
    """At the start of a ticket: keep the `keep` most recently used entries of each path (5 for a
    path no longer declared), remove the others, the unreadable ones and the temporary entries a
    killed run left. Returns the names removed."""
    if not store.is_dir():
        return []
    with _locked(store):
        return _prune(store, caches, time.time() if now is None else now)


def _prune(store: Path, caches: Sequence[CacheConfig], now: float) -> list[str]:
    keep = {c.path: c.keep for c in caches}
    by_path: dict[str, list[tuple[float, Path]]] = {}
    removed: list[str] = []
    for entry in sorted(store.iterdir()):
        if entry.name == LOCK:
            continue
        if PARTIAL in entry.name:
            if _age(entry, now) > PARTIAL_AGE_S:
                remove_tree(entry)
                removed.append(entry.name)
            continue
        try:
            meta = json.loads((entry / ENTRY).read_text(encoding="utf-8"))
            path, used_at = str(meta["path"]), (entry / ENTRY).stat().st_mtime
        except (OSError, ValueError, KeyError, TypeError):
            remove_tree(entry)
            removed.append(entry.name)
            continue
        by_path.setdefault(path, []).append((used_at, entry))
    for path, entries in by_path.items():
        entries.sort(key=lambda e: e[0], reverse=True)
        for _, entry in entries[keep.get(path, DEFAULT_KEEP) :]:
            remove_tree(entry)
            removed.append(entry.name)
    return removed


def _age(path: Path, now: float) -> float:
    try:
        return now - path.stat().st_mtime
    except OSError:
        return 0.0


def lines(used: Sequence[Used]) -> str:
    """One check's caches for the journal: `path` hit, or built (stored or why not)."""
    return ", ".join(u.text() for u in used)
