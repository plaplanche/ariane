"""C11 (ADR 0055): another run's fetch of a base branch that advanced by a merge moves the base's
tracking ref; the guard tolerates that fast-forward, witnessed by the remote, and nothing else.
The ticket keeps the base it started from."""

from __future__ import annotations

from pathlib import Path

import pytest

from ariane import git
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, commit_on_branch, copy_template, edit_app, sh
from test_flow import start

TRACKING = "refs/remotes/origin/main"


def _merge_on_remote(project: Project, name: str = "merged.txt") -> str:
    """A pull request merged on the remote's base branch (a fast-forward); its commit."""
    commit_on_branch(project.remote, "main", f"Merge {name}", {name: "merged\n"})
    return sh(["git", "rev-parse", "refs/heads/main"], project.remote).strip()


def _fetch_base(project: Project) -> None:
    """What the next `ariane start` does to the repository before it prepares its ticket."""
    sh(["git", "fetch", "--quiet", "origin", f"+refs/heads/main:{TRACKING}"], project.root)


def _then_edit(move: object) -> FakeRuntime:
    def session(s: Session) -> None:
        move(s)  # type: ignore[operator]
        edit_app(s)

    return FakeRuntime(action=session)


def _recording_changes(monkeypatch: pytest.MonkeyPatch) -> list[git.Changes]:
    """The reviewer's diffs, as `replay.review_round` reads them."""
    seen: list[git.Changes] = []
    original = git.changes

    def changes(*args: object, **kwargs: object) -> git.Changes:
        read = original(*args, **kwargs)  # type: ignore[arg-type]
        seen.append(read)
        return read

    monkeypatch.setattr(git, "changes", changes)
    return seen


def _delivered(project: Project, base: str) -> list[str]:
    """The subjects of the commits the ticket's branch adds on the remote to `base`."""
    listing = sh(["git", "log", "--format=%s", f"{base}..refs/heads/ariane/7"], project.remote)
    return listing.splitlines()


def test_c11_tracking_ref_a_fetch_after_a_merge_does_not_stop_the_ticket(
    project: Project, tracker: InMemoryTracker
) -> None:
    start_base = project.remote_branches()["main"]

    def merge_then_fetch(session: Session) -> None:
        _merge_on_remote(project)
        _fetch_base(project)

    outcome = start(project, tracker, _then_edit(merge_then_fetch))
    assert outcome.exit_code == 0, outcome.line
    pushed = project.remote_branches()["ariane/7"]
    assert sh(["git", "merge-base", pushed, "main"], project.remote).strip() == start_base
    assert "merged.txt" not in sh(["git", "ls-tree", "--name-only", pushed], project.remote)
    assert tracker.opened and tracker.opened[0]["base"] == "main"


def test_c11_tracking_ref_two_fetches_in_one_ticket_do_not_stop_it(
    project: Project, tracker: InMemoryTracker
) -> None:
    """The guard takes the tolerated commit: the second fetch is measured from it."""

    def merge_then_fetch(name: str) -> object:
        def move(session: Session) -> None:
            _merge_on_remote(project, name)
            _fetch_base(project)

        return move

    runtime = _then_edit(merge_then_fetch("first.txt"))
    runtime.review_actions = [merge_then_fetch("second.txt")]  # type: ignore[list-item]
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 0, outcome.line


def test_c11_tracking_ref_a_merge_not_fetched_after_a_tolerated_move_does_not_stop_it(
    project: Project, tracker: InMemoryTracker
) -> None:
    """The tracking ref stays on the commit the guard took while the remote advances again."""

    def merge_then_fetch(session: Session) -> None:
        _merge_on_remote(project, "first.txt")
        _fetch_base(project)

    def merge(session: Session) -> None:
        _merge_on_remote(project, "second.txt")

    runtime = _then_edit(merge_then_fetch)
    runtime.review_actions = [merge]
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 0, outcome.line


def _backwards(project: Project) -> str:
    return sh(["git", "rev-parse", f"{TRACKING}~1"], project.root).strip()


def _sibling(project: Project) -> str:
    commit_on_branch(project.root, "sibling", "Sibling", {"x.txt": "x\n"}, parent=f"{TRACKING}~1")
    sha = sh(["git", "rev-parse", "refs/heads/sibling"], project.root).strip()
    sh(["git", "update-ref", "-d", "refs/heads/sibling"], project.root)
    return sha


def _not_the_remote_base(project: Project) -> str:
    """A descendant of the tracking ref that the remote does not have."""
    commit_on_branch(project.root, "local", "Local only", {"x.txt": "x\n"}, parent=TRACKING)
    sha = sh(["git", "rev-parse", "refs/heads/local"], project.root).strip()
    sh(["git", "update-ref", "-d", "refs/heads/local"], project.root)
    return sha


def _behind_the_remote_base(project: Project) -> str:
    """A commit the remote's base had, but no longer points to: it advanced once more."""
    first = _merge_on_remote(project, "first.txt")
    _merge_on_remote(project, "second.txt")
    sh(["git", "fetch", "--quiet", str(project.remote), "refs/heads/main"], project.root)
    return first


@pytest.mark.parametrize(
    "target",
    [_backwards, _sibling, _not_the_remote_base, _behind_the_remote_base, None],
    ids=["backwards", "sibling", "not-the-remote-base", "behind-the-remote-base", "deleted"],
)
def test_c11_tracking_ref_any_other_move_still_stops_the_ticket(
    project: Project, tracker: InMemoryTracker, target: object
) -> None:
    _merge_on_remote(project, "before.txt")  # the tracking ref has a parent to go back to
    _fetch_base(project)

    def move(session: Session) -> None:
        if target is None:
            sh(["git", "update-ref", "-d", TRACKING], project.root)
        else:
            sha = target(project)  # type: ignore[operator]
            sh(["git", "update-ref", TRACKING, sha], project.root)

    outcome = start(project, tracker, _then_edit(move))
    assert outcome.exit_code == 1, outcome.line
    assert "changed git configuration, hooks or local branches" in outcome.line
    assert f"changed: ref {TRACKING}" in outcome.detail
    assert "ariane/7" not in project.remote_branches() and tracker.opened == []


def test_c11_tracking_ref_review_diff_and_delivered_range_are_the_same_with_and_without_the_move(
    project: Project,
    tracker: InMemoryTracker,
    project_template: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    moved_base = project.remote_branches()["main"]

    def merge_then_fetch(session: Session) -> None:
        _merge_on_remote(project)
        _fetch_base(project)

    diffs = _recording_changes(monkeypatch)
    assert start(project, tracker, _then_edit(merge_then_fetch)).exit_code == 0
    moved_diffs = diffs[:]
    diffs.clear()
    still = copy_template(project_template, tmp_path / "still")
    still_base = still.remote_branches()["main"]
    other = InMemoryTracker()
    other.add_issue(7, "Bump the app version", "Set app.txt to version 2.")
    assert start(still, other, FakeRuntime()).exit_code == 0
    still_diffs = diffs
    assert moved_diffs and still_diffs
    assert [(c.diff, c.name_status) for c in moved_diffs] == [
        (c.diff, c.name_status) for c in still_diffs
    ]
    assert "merged.txt" not in moved_diffs[0].name_status
    assert _delivered(project, moved_base) == _delivered(still, still_base)
