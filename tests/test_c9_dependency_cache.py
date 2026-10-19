"""C9: dependency folders kept by the content of their key files and copied into the replay trees
instead of being rebuilt (ADR 0054)."""

from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
import stat
import sys
import threading
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from test_config import VALID, with_change
from test_docs_reference import ROOT, errors

from ariane import cache, config, verify
from ariane.cache import CacheConfig
from ariane.config import CheckConfig, Config
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, commit_on_branch, edit_app, make_config, sh
from test_flow import environ, journal, start

PY = sys.executable
DEPS = "ignored-by-git/deps"
NEEDS = f"import sys; sys.exit(0 if open('{DEPS}/lib.txt').read() == 'built' else 1)"
SCRIBBLE = f"open('{DEPS}/lib.txt', 'w').write('changed by a check')"


def builder(log: Path) -> tuple[str, ...]:
    """A cache setup that builds `DEPS` and records each run in `log`."""
    code = (
        "import os, pathlib; p = pathlib.Path(" + repr(DEPS) + "); p.mkdir(parents=True);"
        " (p / 'lib.txt').write_text('built'); (p / 'bin').mkdir();"
        " (p / 'bin' / 'tool').write_text('#!/bin/sh'); os.chmod(p / 'bin' / 'tool', 0o755);"
        f" open({str(log)!r}, 'a').write('build\\n')"
    )
    return (PY, "-c", code)


def builds(log: Path) -> int:
    return len(log.read_text(encoding="utf-8").splitlines()) if log.exists() else 0


def cached(log: Path, *checks: CheckConfig, keep: int = 5) -> Config:
    checks = checks or (
        CheckConfig("first", (PY, "-c", NEEDS), True, 1),
        CheckConfig("second", (PY, "-c", NEEDS), True, 1),
    )
    deps = CacheConfig(DEPS, (".gitignore",), builder(log), keep)
    return dataclasses.replace(make_config(checks=checks), caches=(deps,))


def store(project: Project) -> Path:
    return cache.store_path(project.root)


def entries(project: Project) -> list[Path]:
    return sorted(
        p for p in store(project).iterdir() if cache.PARTIAL not in p.name and p.name != cache.LOCK
    )


def edit_key(session: Session) -> None:
    edit_app(session)
    with open(session.cwd / ".gitignore", "a", encoding="utf-8") as ignore:
        ignore.write("# a new dependency\n")


def test_c9_dependency_cache_second_replay_copies_and_a_changed_key_builds_again(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    log = tmp_path / "builds.txt"
    tracker.add_issue(8, "Bump it again", "Set app.txt to version 2.")
    tracker.add_issue(9, "New dependency", "Set app.txt to version 2.")
    first = start(project, tracker, FakeRuntime(), cached(log))
    assert first.exit_code == 0, first.line
    # The agent's tree builds without storing; the first check's tree builds and stores; the
    # second check's tree copies it.
    assert builds(log) == 2
    assert len(entries(project)) == 1
    assert start(project, tracker, FakeRuntime(), cached(log), number=8).exit_code == 0
    assert builds(log) == 2  # same key: every tree copied the stored folder
    changed = start(project, tracker, FakeRuntime(action=edit_key), cached(log), number=9)
    assert changed.exit_code == 0, changed.line
    assert builds(log) == 3  # the replayed commit has a new key file: built once, then copied
    assert len(entries(project)) == 2


def test_c9_dependency_cache_a_write_into_the_copy_leaves_the_store_unchanged(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    log = tmp_path / "builds.txt"
    scribbles = (
        CheckConfig("first", (PY, "-c", NEEDS), True, 1),
        CheckConfig("scribbles", (PY, "-c", SCRIBBLE), True, 1),
        CheckConfig("third", (PY, "-c", NEEDS), True, 1),
    )
    outcome = start(project, tracker, FakeRuntime(), cached(log, *scribbles))
    assert outcome.exit_code == 0, outcome.line  # "third" still saw the stored folder
    [entry] = entries(project)
    stored = entry / cache.DATA / "lib.txt"
    assert stored.read_text(encoding="utf-8") == "built"
    if os.name != "nt":
        assert not stored.stat().st_mode & stat.S_IWUSR  # the store is read-only


def test_c9_dependency_cache_copies_are_never_links(tmp_path: Path) -> None:
    store_ = tmp_path / "store"
    log = tmp_path / "builds.txt"
    deps = CacheConfig(DEPS, (".gitignore",), builder(log))
    trees = [tmp_path / "a", tmp_path / "b"]
    for tree in trees:
        tree.mkdir()
        (tree / ".gitignore").write_text("ignored-by-git/\n", encoding="utf-8")
    run = _builder_in(trees[0])
    assert [u.hit for u in cache.prepare([deps], trees[0], store_, run, fill=True)] == [False]
    used = cache.prepare([deps], trees[1], store_, _builder_in(trees[1]), fill=True)
    assert [u.hit for u in used] == [True]
    copied = trees[1] / DEPS / "lib.txt"
    [entry] = [p for p in store_.iterdir() if p.name != cache.LOCK]
    assert copied.stat().st_nlink == 1
    assert not os.path.samefile(copied, entry / cache.DATA / "lib.txt")
    copied.write_text("changed", encoding="utf-8")  # the copy is writable
    assert (entry / cache.DATA / "lib.txt").read_text(encoding="utf-8") == "built"
    if os.name != "nt":
        assert os.access(trees[1] / DEPS / "bin" / "tool", os.X_OK)  # modes are kept
    assert builds(log) == 1


def _builder_in(tree: Path) -> Callable[[tuple[str, ...]], None]:
    def build(command: tuple[str, ...]) -> None:
        sh(list(command), tree)

    return build


@pytest.mark.parametrize("damage", ["partial", "no entry file", "unreadable entry file"])
def test_c9_dependency_cache_a_partial_entry_is_ignored_and_rebuilt(
    tmp_path: Path, damage: str
) -> None:
    store_ = tmp_path / "store"
    log = tmp_path / "builds.txt"
    deps = CacheConfig(DEPS, (".gitignore",), builder(log))
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / ".gitignore").write_text("ignored-by-git/\n", encoding="utf-8")
    key = cache.key_of(tree, deps)
    name = f"{key}{cache.PARTIAL}killed" if damage == "partial" else key
    left = store_ / name / cache.DATA
    left.mkdir(parents=True)
    (left / "lib.txt").write_text("half", encoding="utf-8")
    if damage != "no entry file":
        text = "{not json" if damage == "unreadable entry file" else ""
        meta = {"path": DEPS, "key": key, "setup": list(deps.setup)}
        (store_ / name / cache.ENTRY).write_text(text or json.dumps(meta), encoding="utf-8")
    [used] = cache.prepare([deps], tree, store_, _builder_in(tree), fill=True)
    assert not used.hit and used.note == ""
    assert builds(log) == 1
    assert (tree / DEPS / "lib.txt").read_text(encoding="utf-8") == "built"
    assert (store_ / key / cache.DATA / "lib.txt").read_text(encoding="utf-8") == "built"


def test_c9_dependency_cache_the_journal_names_hits_and_builds_per_check(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    outcome = start(project, tracker, FakeRuntime(), cached(tmp_path / "builds.txt"))
    assert outcome.exit_code == 0, outcome.line
    text = journal(project)
    assert "Dependency caches: `ignored-by-git/deps` built, not stored (the agent's tree" in text
    section = text.split("Dependency caches\n", 1)[1]
    assert re.search(
        r"- first: `ignored-by-git/deps` built, stored \(key `[0-9a-f]{12}`\)", section
    )
    assert re.search(r"- second: `ignored-by-git/deps` hit \(key `[0-9a-f]{12}`\)", section)


def test_c9_dependency_cache_without_caches_nothing_changes(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert config.parse(VALID).caches == ()
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == 0, outcome.line
    assert not store(project).exists()
    assert "Dependency caches" not in journal(project)


def test_c9_dependency_cache_the_agents_tree_never_fills_the_store(tmp_path: Path) -> None:
    log = tmp_path / "builds.txt"
    deps = CacheConfig(DEPS, (".gitignore",), builder(log))
    tree = tmp_path / "tree"
    tree.mkdir()
    [used] = cache.prepare([deps], tree, tmp_path / "store", _builder_in(tree), fill=False)
    assert not used.hit and "never fills the store" in used.note
    assert not (tmp_path / "store").exists()
    assert (tree / DEPS / "lib.txt").exists()


def test_c9_dependency_cache_a_failing_cache_setup_stops_and_names_the_check(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    deps = CacheConfig(
        DEPS,
        ("app.txt",),
        (
            PY,
            "-c",
            "import pathlib, sys; sys.exit(0 if '1' in pathlib.Path('app.txt').read_text() else 4)",
        ),
    )
    config_ = dataclasses.replace(make_config(), caches=(deps,))
    outcome = start(project, tracker, FakeRuntime(), config_)
    assert outcome.exit_code == 1
    assert "failed (exit 4) (in the working tree of check" in outcome.line
    assert not store(project).exists()


def test_c9_dependency_cache_old_entries_are_pruned_at_the_start_of_a_ticket(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    for digit, used_at in (("0", 1), ("1", 2)):
        old = store(project) / (digit * 64)
        (old / cache.DATA).mkdir(parents=True)
        meta = {"path": DEPS, "key": digit * 64}
        (old / cache.ENTRY).write_text(json.dumps(meta), encoding="utf-8")
        os.utime(old / cache.ENTRY, (used_at, used_at))
    outcome = start(project, tracker, FakeRuntime(), cached(tmp_path / "builds.txt", keep=1))
    assert outcome.exit_code == 0, outcome.line
    assert not (store(project) / ("0" * 64)).exists()
    assert (store(project) / ("1" * 64)).exists()  # pruned at the start, not after
    assert "Old cache entries removed: `" + "0" * 64 + "`." in journal(project)
    assert len(entries(project)) == 2


def test_c9_dependency_cache_prune_keeps_the_most_recent_per_path(tmp_path: Path) -> None:
    def entry(name: str, path: str, used_at: float) -> None:
        (tmp_path / name / cache.DATA).mkdir(parents=True)
        (tmp_path / name / cache.DATA / "f").write_text("x", encoding="utf-8")
        os.chmod(tmp_path / name / cache.DATA / "f", 0o444)
        meta = tmp_path / name / cache.ENTRY
        meta.write_text(json.dumps({"path": path, "key": name}), encoding="utf-8")
        os.utime(meta, (used_at, used_at))

    for k in range(7):
        entry(f"a{k}", "node_modules", 1000 + k)
    entry("b0", ".venv", 1000)
    (tmp_path / "broken").mkdir()
    (tmp_path / f"x{cache.PARTIAL}old").mkdir()
    os.utime(tmp_path / f"x{cache.PARTIAL}old", (1, 1))
    (tmp_path / f"y{cache.PARTIAL}new").mkdir()
    caches = [CacheConfig("node_modules", ("package-lock.json",), ("npm", "ci"), keep=3)]
    removed = cache.prune(tmp_path, caches, now=10**6)
    assert sorted(removed) == ["a0", "a1", "a2", "a3", "broken", f"x{cache.PARTIAL}old"]
    left = sorted(p.name for p in tmp_path.iterdir())
    assert left == [cache.LOCK, "a4", "a5", "a6", "b0", f"y{cache.PARTIAL}new"]


def test_c9_dependency_cache_verify_uses_the_store_and_records_it(
    project: Project, tmp_path: Path
) -> None:
    log = tmp_path / "builds.txt"
    sh(["git", "branch", "hand/deps"], project.root)
    for _ in range(2):
        outcome = verify.verify(
            "hand/deps",
            repo_root=project.root,
            config=cached(log),
            runtime=FakeRuntime(),
            environ=environ(),
        )
        assert outcome.exit_code == 0, outcome.line
    assert builds(log) == 1
    review = sh(
        ["git", "show", f"hand/deps:{verify.relative_folder('hand/deps')}/review.md"],
        project.root,
    )
    assert "## Dependency caches" in review
    assert "- second: `ignored-by-git/deps` hit" in review


def test_c9_dependency_cache_config_table_is_parsed() -> None:
    raw = [
        {
            "path": "worker/node_modules",
            "key": ["worker/package-lock.json"],
            "setup": ["npm", "ci", "--prefix", "worker"],
        }
    ]
    parsed = config.parse(with_change("project.cache", raw))
    assert parsed.caches == (
        CacheConfig(
            "worker/node_modules",
            ("worker/package-lock.json",),
            ("npm", "ci", "--prefix", "worker"),
            5,
        ),
    )


@pytest.mark.parametrize(
    ("item", "message"),
    [
        ({"path": "../up", "key": ["k"], "setup": ["s"]}, r"project\.cache\[0\]\.path: '\.\./up'"),
        ({"path": "/abs", "key": ["k"], "setup": ["s"]}, r"project\.cache\[0\]\.path"),
        ({"path": ".git/x", "key": ["k"], "setup": ["s"]}, r"project\.cache\[0\]\.path"),
        ({"path": "d", "key": [], "setup": ["s"]}, r"project\.cache\[0\]\.key"),
        ({"path": "d", "key": ["k"], "setup": "npm ci"}, r"project\.cache\[0\]\.setup"),
        ({"path": "d", "key": ["k"], "setup": ["s"], "keep": 0}, r"project\.cache\[0\]\.keep"),
        ({"path": "d", "key": ["k"], "setup": ["s"], "colour": 1}, r"cache\[0\]\.colour: unknown"),
    ],
)
def test_c9_dependency_cache_config_errors_name_the_key(
    item: dict[str, object], message: str
) -> None:
    with pytest.raises(config.ConfigError, match=message):
        config.parse(with_change("project.cache", [item]))


def test_c9_dependency_cache_config_overlapping_paths_are_refused() -> None:
    raw = [
        {"path": "node_modules", "key": ["k"], "setup": ["s"]},
        {"path": "node_modules/.cache", "key": ["k"], "setup": ["s"]},
    ]
    with pytest.raises(config.ConfigError, match=r"cache\[1\]\.path: overlaps"):
        config.parse(with_change("project.cache", raw))


def test_c9_dependency_cache_example_tables_validate() -> None:
    text = (ROOT / "docs" / "ariane.example.toml").read_text(encoding="utf-8")
    pattern = r"^# (\[\[project\.cache\]\]|(path|key|setup|keep) = .*)$"
    data = tomllib.loads(re.sub(pattern, r"\1", text, flags=re.MULTILINE))
    assert errors(data, config.SCHEMA) == []
    paths = [c.path for c in config.parse(data).caches]
    assert paths == ["worker/node_modules", ".venv"]


def _warm(tmp_path: Path, log: Path) -> tuple[CacheConfig, Path]:
    """A store holding the `DEPS` entry of a first tree, and the cache that filled it."""
    deps = CacheConfig(DEPS, (".gitignore",), builder(log))
    first = _tree(tmp_path / "first")
    store_ = tmp_path / "store"
    assert [u.hit for u in cache.prepare([deps], first, store_, _builder_in(first), fill=True)] == [
        False
    ]
    return deps, store_


def _tree(path: Path) -> Path:
    path.mkdir()
    (path / ".gitignore").write_text("ignored-by-git/\n", encoding="utf-8")
    return path


@pytest.mark.skipif(os.name == "nt", reason="symbolic links need a privilege on Windows")
@pytest.mark.parametrize("link", ["ignored-by-git", DEPS])
def test_c9_dependency_cache_a_link_on_the_destination_is_never_followed(
    tmp_path: Path, link: str
) -> None:
    log = tmp_path / "builds.txt"
    deps, store_ = _warm(tmp_path, log)
    [entry] = list(p for p in store_.iterdir() if p.name != cache.LOCK)
    os.utime(entry / cache.ENTRY, (1, 1))
    outside = tmp_path / "outside"
    outside.mkdir()
    tree = _tree(tmp_path / "next")  # a later commit with the same key files and a link
    (tree / link).parent.mkdir(parents=True, exist_ok=True)
    os.symlink(outside, tree / link, target_is_directory=True)
    built: list[tuple[str, ...]] = []
    [used] = cache.prepare([deps], tree, store_, built.append, fill=True)
    assert not used.hit and used.note.startswith("not stored (")
    assert built == [deps.setup]  # the setup runs as without a cache, the store writes nothing
    assert list(outside.iterdir()) == []
    assert (entry / cache.ENTRY).stat().st_mtime == 1  # not even its last use was written
    assert [p.name for p in store_.iterdir() if p.name != cache.LOCK] == [entry.name]


def test_c9_dependency_cache_a_folder_the_commit_has_is_never_merged(tmp_path: Path) -> None:
    log = tmp_path / "builds.txt"
    deps, store_ = _warm(tmp_path, log)
    tree = _tree(tmp_path / "next")
    (tree / DEPS).mkdir(parents=True)
    (tree / DEPS / "marker").write_text("tracked", encoding="utf-8")
    built: list[tuple[str, ...]] = []
    [used] = cache.prepare([deps], tree, store_, built.append, fill=True)
    assert not used.hit and "already has that path" in used.note
    assert built == [deps.setup]
    assert sorted(p.name for p in (tree / DEPS).iterdir()) == ["marker"]


def test_c9_dependency_cache_a_copy_failing_half_way_leaves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "builds.txt"
    deps, store_ = _warm(tmp_path, log)
    tree = _tree(tmp_path / "next")
    (tree / "ignored-by-git").mkdir()
    (tree / "ignored-by-git" / "other.txt").write_text("kept", encoding="utf-8")
    copied: list[str] = []
    plain = shutil.copyfile

    def copy_once(source: str, target: Path) -> None:
        if copied:
            raise OSError("unreadable")
        copied.append(source)
        plain(source, target)

    monkeypatch.setattr(cache, "_clone", lambda source, target: False)
    monkeypatch.setattr(shutil, "copyfile", copy_once)
    seen: list[list[str]] = []

    def build(setup: tuple[str, ...]) -> None:
        seen.append(sorted(p.name for p in (tree / "ignored-by-git").iterdir()))

    [used] = cache.prepare([deps], tree, store_, build, fill=False)
    assert copied and not used.hit
    assert seen == [["other.txt"]]  # one file was copied, then removed before the setup ran


def test_c9_dependency_cache_a_tree_never_removes_an_entry_another_just_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "builds.txt"
    deps = CacheConfig(DEPS, (".gitignore",), builder(log))
    store_ = tmp_path / "store"
    a, b = _tree(tmp_path / "a"), _tree(tmp_path / "b")
    key = cache.key_of(a, deps)
    (store_ / key / cache.DATA).mkdir(parents=True)  # an unreadable entry: no entry.json
    original = cache._copy
    published: list[int] = []

    def copy(source: Path, target: Path, **kwargs: Any) -> None:
        original(source, target, **kwargs)
        if not kwargs["writable"] and not published and source.is_relative_to(a):
            # A has copied its build and not yet published: B replaces the entry meanwhile.
            [used] = cache.prepare([deps], b, store_, _builder_in(b), fill=True)
            assert not used.hit and used.note == ""
            published.append((store_ / key / cache.ENTRY).stat().st_ino)

    monkeypatch.setattr(cache, "_copy", copy)
    [used] = cache.prepare([deps], a, store_, _builder_in(a), fill=True)
    assert used.note == "stored by another tree at the same time"
    assert published == [(store_ / key / cache.ENTRY).stat().st_ino]  # B's entry, intact
    assert (store_ / key / cache.DATA / "lib.txt").read_text(encoding="utf-8") == "built"
    assert [p.name for p in store_.iterdir() if p.name != cache.LOCK] == [key]


def test_c9_dependency_cache_prune_waits_for_a_tree_using_the_store(tmp_path: Path) -> None:
    (tmp_path / "broken").mkdir()  # removed by prune, but only once the store is free
    done = threading.Event()

    def prune() -> None:
        cache.prune(tmp_path, [])
        done.set()

    with cache._locked(tmp_path):
        worker = threading.Thread(target=prune)
        worker.start()
        assert not done.wait(0.3)
        assert (tmp_path / "broken").exists()
    worker.join(10)
    assert done.is_set() and not (tmp_path / "broken").exists()


def test_c9_dependency_cache_without_caches_the_store_is_left_alone(
    project: Project, tracker: InMemoryTracker
) -> None:
    broken = store(project) / "broken"  # what prune would remove
    broken.mkdir(parents=True)
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == 0, outcome.line
    assert broken.exists()
    assert "Old cache entries" not in journal(project)


MOVE_HEAD = (
    "import subprocess; run = subprocess.run;"
    " detached = run(['git', 'symbolic-ref', '-q', 'HEAD']).returncode;"
    " detached and run(['git', 'commit', '-q', '--allow-empty', '-m', 'moved'], check=True)"
)


def _moving(log: Path) -> Config:
    """A cache setup that builds `DEPS` and, in a replay tree, moves its detached head."""
    moving = (PY, "-c", f"exec({MOVE_HEAD!r}); exec({builder(log)[2]!r})")
    deps = CacheConfig(DEPS, (".gitignore",), moving)
    return dataclasses.replace(cached(log), caches=(deps,))


def test_c9_dependency_cache_a_setup_moving_the_head_publishes_nothing(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    outcome = start(project, tracker, FakeRuntime(), _moving(tmp_path / "builds.txt"))
    assert outcome.exit_code != 0
    assert "moved the replay working tree's head" in outcome.line
    assert not store(project).exists() or entries(project) == []


def test_c9_dependency_cache_verify_refuses_a_setup_moving_the_head_before_storing(
    project: Project, tmp_path: Path
) -> None:
    sh(["git", "branch", "hand/moved"], project.root)
    outcome = verify.verify(
        "hand/moved",
        repo_root=project.root,
        config=_moving(tmp_path / "builds.txt"),
        runtime=FakeRuntime(),
        environ=environ(),
    )
    assert outcome.exit_code != 0
    assert "a cache setup moved a head" in outcome.line
    assert not store(project).exists() or entries(project) == []


def _warm_ticket(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> tuple[Config, Path, Path]:
    """A first ticket that fills the store, with a check that records each run in `ran`."""
    log, ran = tmp_path / "builds.txt", tmp_path / "ran.txt"
    marks = f"open({str(ran)!r}, 'a').write('ran\\n')"
    check = CheckConfig("check", (PY, "-c", marks), True, 1)
    deps = CacheConfig(DEPS, ("deps.lock",), builder(log))  # a key file the commits keep
    config_ = dataclasses.replace(cached(log, check), caches=(deps,))
    assert start(project, tracker, FakeRuntime(), config_).exit_code == 0
    assert builds(log) == 2 and ran.read_text(encoding="utf-8") == "ran\n"
    tracker.add_issue(8, "Unignore", "Set app.txt to version 2.")
    return config_, log, ran


def test_c9_dependency_cache_a_hit_no_longer_ignored_by_git_stops_before_the_check(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    config_, log, ran = _warm_ticket(project, tracker, tmp_path)

    def unignore(session: Session) -> None:
        edit_app(session)
        (session.cwd / ".gitignore").write_text("other/\n", encoding="utf-8")
        shutil.rmtree(session.cwd / DEPS)  # nothing of it is committed

    outcome = start(project, tracker, FakeRuntime(action=unignore), config_, number=8)
    assert outcome.exit_code != 0
    assert "files that git does not ignore" in outcome.line, outcome.line
    assert builds(log) == 2  # the replay copied the folder, then refused it
    assert ran.read_text(encoding="utf-8") == "ran\n"  # the check never ran on it
    assert entries(project) and all(p.exists() for p in entries(project))


def test_c9_dependency_cache_a_hit_no_longer_ignored_by_git_stops_before_the_agent(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    config_, log, _ = _warm_ticket(project, tracker, tmp_path)
    commit_on_branch(project.remote, "main", "unignore", {".gitignore": "other/\n"})
    runtime = FakeRuntime()
    outcome = start(project, tracker, runtime, config_, number=8)
    assert outcome.exit_code != 0
    assert "files that git does not ignore" in outcome.line, outcome.line
    assert builds(log) == 2 and runtime.sessions == []  # copied, refused, no agent started


def test_c9_dependency_cache_an_entry_whose_folder_cannot_be_copied_is_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "builds.txt"
    deps, store_ = _warm(tmp_path, log)
    [entry] = [p for p in store_.iterdir() if p.name != cache.LOCK]
    before = json.loads((entry / cache.ENTRY).read_text(encoding="utf-8"))["id"]
    original = cache._copy

    def copy(source: Path, target: Path, **kwargs: Any) -> None:
        if source.is_relative_to(store_):
            raise OSError("unreadable")
        original(source, target, **kwargs)

    monkeypatch.setattr(cache, "_copy", copy)
    tree = _tree(tmp_path / "next")
    [used] = cache.prepare([deps], tree, store_, _builder_in(tree), fill=True)
    assert not used.hit and used.note == ""  # rebuilt and stored in place of the failed entry
    after = json.loads((entry / cache.ENTRY).read_text(encoding="utf-8"))["id"]
    assert after != before
    assert [p.name for p in store_.iterdir() if p.name != cache.LOCK] == [entry.name]
    monkeypatch.setattr(cache, "_copy", original)
    last = _tree(tmp_path / "last")
    assert [u.hit for u in cache.prepare([deps], last, store_, _builder_in(last), fill=True)] == [
        True
    ]
    assert builds(log) == 2
