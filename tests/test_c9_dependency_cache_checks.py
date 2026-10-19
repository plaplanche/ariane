"""C9, ADR 0054: a copied cache is checked before any other setup runs, and a cache setup that
changes a tracked file publishes nothing (hand takeover of #209, `ariane verify` review)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from test_c9_dependency_cache import (
    DEPS,
    PY,
    _builder_in,
    _tree,
    builder,
    builds,
    cached,
    entries,
    store,
)

from ariane import cache, verify
from ariane.cache import CacheConfig
from ariane.config import Config
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, sh
from test_flow import environ, start

OTHER = "ignored-by-git/other"


def test_c9_dependency_cache_a_copied_cache_is_checked_before_the_next_setup(
    tmp_path: Path,
) -> None:
    """With a hit on the first cache and a miss on the second, the hit is checked before the
    second cache's setup runs: that setup could otherwise hide what the copy left."""
    log = tmp_path / "builds.txt"
    first = CacheConfig(DEPS, (".gitignore",), builder(log))
    warm = _tree(tmp_path / "warm")
    store_ = tmp_path / "store"
    cache.prepare([first], warm, store_, _builder_in(warm), fill=True)
    second = CacheConfig(OTHER, ("app.txt",), (PY, "-c", "pass"))
    tree = _tree(tmp_path / "tree")
    (tree / "app.txt").write_text("x\n", encoding="utf-8")
    calls: list[str] = []

    def build(command: tuple[str, ...]) -> None:
        calls.append("build")

    def validate() -> None:
        calls.append("validate")
        raise RuntimeError("the copy left a file git does not ignore")

    with pytest.raises(RuntimeError):
        cache.prepare([first, second], tree, store_, build, fill=True, validate=validate)
    assert calls == ["validate"]  # the second cache's setup never ran


TOUCH_TRACKED = (
    "import subprocess;"
    " detached = subprocess.run(['git', 'symbolic-ref', '-q', 'HEAD']).returncode;"
    " detached and open('app.txt', 'a').write('changed by a cache setup\\n')"
)


def _touching(log: Path) -> Config:
    """A cache setup that builds `DEPS` and, in a replay tree, changes the tracked `app.txt`."""
    touching = (PY, "-c", f"exec({TOUCH_TRACKED!r}); exec({builder(log)[2]!r})")
    deps = CacheConfig(DEPS, (".gitignore",), touching)
    return dataclasses.replace(cached(log), caches=(deps,))


def test_c9_dependency_cache_a_setup_changing_a_tracked_file_publishes_nothing(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    outcome = start(project, tracker, FakeRuntime(), _touching(tmp_path / "builds.txt"))
    assert outcome.exit_code != 0
    assert "changed files that git tracks" in outcome.line
    assert not store(project).exists() or entries(project) == []


def test_c9_dependency_cache_verify_refuses_a_setup_changing_a_tracked_file_before_storing(
    project: Project, tmp_path: Path
) -> None:
    sh(["git", "branch", "hand/touching"], project.root)
    outcome = verify.verify(
        "hand/touching",
        repo_root=project.root,
        config=_touching(tmp_path / "builds.txt"),
        runtime=FakeRuntime(),
        environ=environ(),
    )
    assert outcome.exit_code != 0
    assert "changed files that git tracks" in outcome.line
    assert not store(project).exists() or entries(project) == []


def test_c9_dependency_cache_an_unreadable_key_file_never_hits_an_entry_built_without_it(
    tmp_path: Path,
) -> None:
    """An entry built while a key file was missing is never chosen for a tree where that file is
    there but cannot be read (here a folder in its place): its content is unknown."""
    log = tmp_path / "builds.txt"
    deps = CacheConfig(DEPS, ("deps.lock",), builder(log))
    store_ = tmp_path / "store"
    first = _tree(tmp_path / "first")  # no deps.lock: built and stored under the missing key
    assert [u.hit for u in cache.prepare([deps], first, store_, _builder_in(first), fill=True)] == [
        False
    ]
    stored = sorted(p.name for p in store_.iterdir() if p.name != cache.LOCK)
    tree = _tree(tmp_path / "tree")
    (tree / "deps.lock").mkdir()  # there, but reading it fails
    assert cache.key_of(tree, deps) == ""
    [used] = cache.prepare([deps], tree, store_, _builder_in(tree), fill=True)
    assert not used.hit
    assert used.note == "not stored (a key file cannot be read)"
    assert builds(log) == 2
    assert sorted(p.name for p in store_.iterdir() if p.name != cache.LOCK) == stored
