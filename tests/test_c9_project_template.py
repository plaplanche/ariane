"""The `project` fixture copies a template built once per worker (C9, ADR 0049)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import Project, commit_on_branch, copy_template, sh


def _head(project: Project) -> str:
    return sh(["git", "rev-parse", "HEAD"], project.root)


def _commit_and_push(project: Project, text: str) -> str:
    (project.root / "app.txt").write_text(text, encoding="utf-8")
    sh(["git", "commit", "--quiet", "-am", text.strip()], project.root)
    sh(["git", "push", "--quiet", "origin", "main"], project.root)
    return _head(project)


def test_c9_project_template_two_copies_are_separate_repositories(
    project_template: Path, tmp_path: Path
) -> None:
    # Two tests get two copies of the same template, as these two do.
    first = copy_template(project_template, tmp_path / "first")
    second = copy_template(project_template, tmp_path / "second")
    start = _head(first)
    assert _head(second) == start
    assert first.remote_branches() == second.remote_branches() == {"main": start}

    pushed = _commit_and_push(first, "version 2\n")
    assert first.remote_branches() == {"main": pushed}
    assert second.remote_branches() == {"main": start}
    assert _head(second) == start
    assert (second.root / "app.txt").read_text(encoding="utf-8") == "version 1\n"
    sh(["git", "cat-file", "-e", f"{pushed}^{{commit}}"], first.root)
    for repo in (second.root, second.remote):
        found = subprocess.run(["git", "cat-file", "-e", pushed], cwd=repo, check=False)
        assert found.returncode != 0, repo

    sh(["git", "commit", "--quiet", "--allow-empty", "-m", "only here"], second.root)
    assert sh(["git", "log", "-1", "--format=%s"], first.root) == "version 2"
    assert sh(["git", "status", "--porcelain"], first.root) == ""


def test_c9_project_template_origin_is_each_projects_own_remote(
    project: Project, project_template: Path
) -> None:
    template_remote = ["git", "--git-dir", str(project_template / "origin.git")]
    template_main = sh([*template_remote, "rev-parse", "main"], project_template)
    assert sh(["git", "remote", "get-url", "origin"], project.root) == str(project.remote)
    assert sh(["git", "remote", "get-url", "--push", "origin"], project.root) == str(project.remote)
    pushed = _commit_and_push(project, "version 2\n")
    assert project.remote_branches() == {"main": pushed}
    assert project.show("main", "app.txt") == "version 2"
    assert sh([*template_remote, "rev-parse", "main"], project_template) == template_main
    sh(["git", "fetch", "--quiet", "origin"], project.root)
    assert sh(["git", "rev-parse", "origin/main"], project.root) == pushed


def test_c9_project_template_gives_what_the_fixture_always_gave(project: Project) -> None:
    assert project.root.is_absolute() and project.root == project.root.resolve()
    assert project.remote.name == "origin.git" and project.remote.parent == project.root.parent
    assert sh(["git", "branch", "--show-current"], project.root) == "main"
    assert sh(["git", "log", "--format=%s %an <%ae>"], project.root) == (
        "initial Ariane Test <ariane-test@example.invalid>"
    )
    assert sh(["git", "status", "--porcelain", "--ignored"], project.root) == ""
    assert sh(["git", "ls-files"], project.root).splitlines() == [".gitignore", "app.txt"]
    assert (project.root / "app.txt").read_text(encoding="utf-8") == "version 1\n"
    assert project.remote_branches() == {"main": sh(["git", "rev-parse", "HEAD"], project.root)}


@pytest.mark.skipif(sys.platform == "win32", reason="quotes are not allowed in Windows names")
def test_c9_project_template_origin_keeps_quotes_and_backslashes(
    project_template: Path, tmp_path: Path
) -> None:
    copied = copy_template(project_template, tmp_path / 'a "quoted" back\\slash')
    assert sh(["git", "remote", "get-url", "origin"], copied.root) == str(copied.remote)
    pushed = _commit_and_push(copied, "version 2\n")
    assert copied.remote_branches() == {"main": pushed}


def test_c9_project_template_commit_on_branch_adds_one_commit_without_a_checkout(
    project: Project,
) -> None:
    start = sh(["git", "rev-parse", "HEAD"], project.root)
    commit_on_branch(project.root, "hand/fix", "By hand", {"app.txt": "version 2\n"}, parent="main")
    commit_on_branch(project.root, "hand/fix", "Again", {"docs/new.md": "new\n"})
    assert sh(["git", "rev-parse", "hand/fix~2"], project.root) == start
    assert sh(["git", "log", "--format=%s %an", "main..hand/fix"], project.root).splitlines() == [
        "Again Ariane Test",
        "By hand Ariane Test",
    ]
    assert sh(["git", "show", "hand/fix:app.txt"], project.root) == "version 2"
    assert sh(["git", "show", "hand/fix:docs/new.md"], project.root) == "new"
    assert sh(["git", "branch", "--show-current"], project.root) == "main"
    assert sh(["git", "status", "--porcelain"], project.root) == ""
