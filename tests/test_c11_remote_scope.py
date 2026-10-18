"""C11, C21: the remote check watches the ticket's branch, the base branch and tags only."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ariane import git, verify
from ariane.flow import Outcome
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, commit_on_branch, edit_app, make_config, sh
from test_flow import environ, start

BRANCH = "hand/fix"


def acting(project: Project, push: Callable[[Session], None]) -> FakeRuntime:
    def action(session: Session) -> None:
        edit_app(session)
        push(session)

    return FakeRuntime(action=action)


def _push(project: Project, *args: str) -> Callable[[Session], None]:
    def push(session: Session) -> None:
        # A reviewer runs from an empty folder and reads its tree through `add_dirs` (ADR 0031).
        tree = session.add_dirs[0] if session.add_dirs else session.cwd
        sh(["git", "push", "--quiet", *args], tree)

    return push


def _advance_base(project: Project, *, rewrite: bool) -> Callable[[Session], None]:
    def push(session: Session) -> None:
        other = project.root.parent / "other-clone"
        sh(["git", "clone", "--quiet", str(project.remote), str(other)], project.root.parent)
        if rewrite:
            sh(["git", "reset", "--quiet", "--hard", "HEAD"], other)
            (other / "x.txt").write_text("x\n", encoding="utf-8")
            sh(["git", "add", "x.txt"], other)
            sh(["git", "commit", "--quiet", "--amend", "-m", "rewritten"], other)
            sh(["git", "push", "--quiet", "--force", "origin", "HEAD:main"], other)
        else:
            (other / "x.txt").write_text("x\n", encoding="utf-8")
            sh(["git", "add", "x.txt"], other)
            sh(["git", "commit", "--quiet", "-m", "merge"], other)
            sh(["git", "push", "--quiet", "origin", "HEAD:main"], other)

    return push


def test_c11_remote_scope_another_branch_does_not_stop_the_ticket(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = acting(project, _push(project, str(project.remote), "HEAD:refs/heads/colleague"))
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 0, outcome.line
    assert "colleague" in project.remote_branches()


def test_c11_remote_scope_a_push_to_the_ticket_branch_stops_it(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = acting(project, _push(project, str(project.remote), "HEAD:refs/heads/ariane/7"))
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "the remote changed during the agent session (refs/heads/ariane/7)" in outcome.line


def test_c11_remote_scope_a_new_tag_stops_it(project: Project, tracker: InMemoryTracker) -> None:
    runtime = acting(project, _push(project, str(project.remote), "HEAD:refs/tags/v1"))
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "(refs/tags/v1)" in outcome.line


def test_c11_remote_scope_a_non_fast_forward_of_the_base_branch_stops_it(
    project: Project, tracker: InMemoryTracker
) -> None:
    outcome = start(project, tracker, acting(project, _advance_base(project, rewrite=True)))
    assert outcome.exit_code == 1
    assert "(refs/heads/main)" in outcome.line


def test_c11_remote_scope_a_fast_forward_of_the_base_branch_does_not_stop_it(
    project: Project, tracker: InMemoryTracker
) -> None:
    outcome = start(project, tracker, acting(project, _advance_base(project, rewrite=False)))
    assert outcome.exit_code == 0, outcome.line


def _verify(project: Project, runtime: FakeRuntime) -> Outcome:
    return verify.verify(
        BRANCH,
        repo_root=project.root,
        config=make_config(),
        runtime=runtime,
        environ=environ(),
    )


@pytest.fixture
def hand_branch(project: Project) -> None:
    commit_on_branch(
        project.root, BRANCH, "Bump the version by hand", {"app.txt": "version 2\n"}, parent="main"
    )


def _reviewer_pushing(project: Project, *args: str) -> FakeRuntime:
    return FakeRuntime(review_actions=[_push(project, str(project.remote), *args)])


@pytest.mark.usefixtures("hand_branch")
def test_c11_remote_scope_verify_ignores_another_branch(project: Project) -> None:
    outcome = _verify(project, _reviewer_pushing(project, "HEAD:refs/heads/colleague"))
    assert outcome.exit_code == 0, outcome.line


@pytest.mark.usefixtures("hand_branch")
def test_c11_remote_scope_verify_stops_on_its_branch_and_on_a_tag(project: Project) -> None:
    on_branch = _verify(project, _reviewer_pushing(project, f"HEAD:refs/heads/{BRANCH}"))
    assert on_branch.exit_code == 1 and f"(refs/heads/{BRANCH})" in on_branch.line
    on_tag = _verify(project, _reviewer_pushing(project, "HEAD:refs/tags/v1"))
    assert on_tag.exit_code == 1 and "(refs/tags/v1)" in on_tag.line


@pytest.mark.usefixtures("hand_branch")
def test_c11_remote_scope_verify_tolerates_a_fast_forward_of_the_base_branch(
    project: Project,
) -> None:
    def advance(session: Session) -> None:
        _advance_base(project, rewrite=False)(session)

    outcome = _verify(project, FakeRuntime(review_actions=[advance]))
    assert outcome.exit_code == 0, outcome.line
    assert git.remote_refs(project.root, str(project.remote))["refs/heads/main"]
