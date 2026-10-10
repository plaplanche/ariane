"""C23: `git.commit` and ignored paths."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ariane import git

from conftest import sh


def test_c23_commit_raises_on_an_ignored_path_unless_tolerated(tmp_path: Path) -> None:
    sh(["git", "init", "--quiet"], tmp_path)
    (tmp_path / ".gitignore").write_text("work/\n", encoding="utf-8")
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "a.md").write_text("x", encoding="utf-8")
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path)}
    with pytest.raises(git.GitError):
        git.commit(tmp_path, ["work"], "m", env=env)
    assert git.commit(tmp_path, ["work"], "m", env=env, tolerate_ignored=True) is False
