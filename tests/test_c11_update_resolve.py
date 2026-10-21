"""`ariane update <n>`: a conflict, or a check the merge broke, goes to one implementer session,
then the replay and the review, within the fix rounds of C10 (C10, C11; ADR 0033)."""

from __future__ import annotations

import json

import pytest
from test_c11_update import OPEN, move_base, pushes  # noqa: F401 (fixture)
from test_fix_rounds import NO_GO, implementers, reviewers

from ariane import flow, git, update
from ariane.config import CheckConfig, Config
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import PY, Action, FakeRuntime, Project, edit_app, make_config, sh
from test_flow import environ, start, worktree

NOT_BROKEN = CheckConfig(
    "nothing broken",
    (
        PY,
        "-c",
        "import os, sys; b = os.path.exists('broken.txt');"
        " print('found broken.txt, left by the base' if b else 'fine'); sys.exit(1 if b else 0)",
    ),
    True,
    1.0,
)
UPDATE_BLOCK = '<untrusted-ticket kind="update">'


def config() -> Config:
    return make_config(checks=(*make_config().checks, NOT_BROKEN))


def delivered(project: Project, tracker: InMemoryTracker, pushes: list[str]) -> str:  # noqa: F811
    """Ticket #7 delivered, its pull request open, its push not counted; its local head."""
    assert start(project, tracker, FakeRuntime(), config()).exit_code == 0
    tracker.pull_states["ariane/7"] = OPEN
    pushes.clear()
    return git.head(worktree(project))


def run_update(project: Project, tracker: InMemoryTracker, runtime: FakeRuntime) -> flow.Outcome:
    return update.update(
        7,
        repo_root=project.root,
        config=config(),
        tracker=tracker,
        runtime=runtime,
        environ=environ(),
    )


def on_update(task: Action, fix: Action = edit_app) -> Action:
    """`task` in the update session (its prompt holds the update block), `fix` in a fix round."""

    def action(session: Session) -> None:
        (task if UPDATE_BLOCK in session.prompt else fix)(session)

    return action


def resolve_app(session: Session) -> None:
    (session.cwd / "app.txt").write_text("version 2\nand version 3\n", encoding="utf-8")
    sh(["git", "add", "app.txt"], session.cwd)


def merge_pending(project: Project) -> bool:
    tree = worktree(project)
    return git.git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], tree, check=False).ok


def test_c11_update_resolve_a_conflict_commits_the_merge_replays_reviews_and_pushes(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],  # noqa: F811
) -> None:
    local = delivered(project, tracker, pushes)
    remote = project.remote_branches()["ariane/7"]
    base = move_base(project, {"app.txt": "version 3\n"})
    runtime = FakeRuntime(action=on_update(resolve_app))
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 0, outcome.line
    pushed = project.remote_branches()["ariane/7"]
    assert pushes == [pushed]
    tree = worktree(project)
    assert git.is_ancestor(tree, remote, pushed)
    merge, *parents = sh(
        ["git", "log", "--merges", "--format=%H %P", f"{remote}..{pushed}"], tree
    ).split()
    assert parents == [local, base]
    assert sh(["git", "rev-parse", f"{merge}^1", f"{merge}^2"], tree).split() == [local, base]
    assert project.show("ariane/7", "app.txt") == "version 2\nand version 3"
    [session] = implementers(runtime)
    assert UPDATE_BLOCK in session.prompt and "This is an update of ticket #7" in session.prompt
    assert "Merge `origin/main` into this branch: resolve the conflicts below" in session.prompt
    assert "- `app.txt`" in session.prompt.partition(UPDATE_BLOCK)[2]
    assert len(reviewers(runtime)) == 1
    journal = project.show("ariane/7", "work/7/journal.md")
    assert "Update session's task" in journal and "Merge committed" in journal
    recorded = journal.partition("Update session started")[2]
    assert "This is an update of ticket #7" in recorded and "Update session's task" in recorded
    assert not merge_pending(project) and not git.status(tree)


@pytest.mark.parametrize(
    "left", ["an unmerged path", "a conflict marker", "a marker staged behind a clean copy"]
)
def test_c11_update_resolve_a_session_leaving_a_conflict_needs_a_human(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],  # noqa: F811
    left: str,
) -> None:
    local = delivered(project, tracker, pushes)
    remote = project.remote_branches()["ariane/7"]
    move_base(project, {"app.txt": "version 3\n"})

    def half_done(session: Session) -> None:
        if left == "an unmerged path":  # resolved in the file, never marked resolved
            (session.cwd / "app.txt").write_text("version 2\nversion 3\n", encoding="utf-8")
            return
        text = "version 2\n<<<<<<< ours\nkept\n=======\nversion 3\n>>>>>>> theirs\n"
        (session.cwd / "app.txt").write_text(text, encoding="utf-8")
        sh(["git", "add", "app.txt"], session.cwd)
        if left == "a marker staged behind a clean copy":  # `git add --all` skips the entry
            sh(["git", "update-index", "--skip-worktree", "app.txt"], session.cwd)
            (session.cwd / "app.txt").write_text("version 2\nversion 3\n", encoding="utf-8")

    runtime = FakeRuntime(action=on_update(half_done))
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1, outcome.line
    assert "needs a human" in outcome.line
    assert "the update session left conflicts in app.txt" in outcome.line
    assert "ariane verify ariane/7" in outcome.line
    assert pushes == [] and project.remote_branches()["ariane/7"] == remote
    assert len(implementers(runtime)) == 1 and reviewers(runtime) == []
    tree = worktree(project)
    assert git.head(tree) == local and merge_pending(project)  # the state is kept, uncommitted
    status = (tree / "work/7/status.md").read_text(encoding="utf-8")
    assert "Last action: needs a human" in status
    data = json.loads((tree / "work/7/metrics.json").read_text(encoding="utf-8"))
    assert (data["outcome"], data["category"]) == ("needs a human", "merge")


def test_c11_update_resolve_a_check_the_merge_broke_fixed_by_the_session_is_pushed(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],  # noqa: F811
) -> None:
    delivered(project, tracker, pushes)
    move_base(project, {"broken.txt": "the base broke it\n"})

    def unbreak(session: Session) -> None:
        (session.cwd / "broken.txt").unlink()

    runtime = FakeRuntime(action=on_update(unbreak))
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 0, outcome.line
    [session] = implementers(runtime)
    task = session.prompt.partition(UPDATE_BLOCK)[2]
    assert "These checks fail after merging `origin/main`: fix them." in task
    assert "nothing broken" in task and "found broken.txt, left by the base" in task
    pushed = project.remote_branches()["ariane/7"]
    assert pushes == [pushed]
    tree = worktree(project)
    messages = sh(["git", "log", "--format=%s", f"{pushed}~5..{pushed}"], tree).splitlines()
    assert "#7: fix after merging main" in messages
    assert sh(["git", "log", "--merges", "--format=%H", "-1", pushed], tree)
    assert "broken.txt" not in sh(["git", "ls-tree", "--name-only", pushed], tree).split()
    assert len(reviewers(runtime)) == 1
    assert "**go**" in project.show("ariane/7", "work/7/review-1.md")


def test_c11_update_resolve_a_review_still_no_go_after_the_rounds_pushes_nothing(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],  # noqa: F811
) -> None:
    delivered(project, tracker, pushes)
    remote = project.remote_branches()["ariane/7"]
    move_base(project, {"app.txt": "version 3\n"})
    runtime = FakeRuntime(action=on_update(resolve_app), answers=[NO_GO])
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1, outcome.line
    assert "the review of the update is no-go" in outcome.line
    assert pushes == [] and project.remote_branches()["ariane/7"] == remote
    assert len(implementers(runtime)) == 2 and len(reviewers(runtime)) == 2
    fix = implementers(runtime)[1]
    assert "This is fix round 2" in fix.prompt and "Wrong value" in fix.prompt
    assert "This is an update of ticket #7" in fix.prompt and UPDATE_BLOCK not in fix.prompt
    tree = worktree(project)
    assert {"review-1.md", "review-2.md"} <= {p.name for p in (tree / "work/7").iterdir()}
    assert "Last action: needs a human" in (tree / "work/7/status.md").read_text("utf-8")
    assert not git.status(tree)


@pytest.mark.parametrize("case", ["conflict", "red check"])
def test_c11_update_resolve_runs_at_most_the_update_session_and_one_fix_round(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],  # noqa: F811
    case: str,
) -> None:
    """Checks that stay red: the update session is the first round, one fix round follows, then
    the update stops `needs a human` without a third session or a review."""
    delivered(project, tracker, pushes)
    remote = project.remote_branches()["ariane/7"]
    files = {"app.txt": "version 3\n"} if case == "conflict" else {}
    move_base(project, {**files, "broken.txt": "the base broke it\n"})

    def touch(session: Session) -> None:  # a change, never the fix
        rounds = len(list(session.cwd.glob("note-*.txt")))
        (session.cwd / f"note-{rounds}.txt").write_text("tried\n", encoding="utf-8")

    def task(session: Session) -> None:
        if case == "conflict":
            resolve_app(session)
        touch(session)

    runtime = FakeRuntime(action=on_update(task, touch))
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1, outcome.line
    assert "blocking checks failed after the merge: nothing broken" in outcome.line
    assert len(implementers(runtime)) == 2 and reviewers(runtime) == []
    assert pushes == [] and project.remote_branches()["ariane/7"] == remote
    data = json.loads((worktree(project) / "work/7/metrics.json").read_text(encoding="utf-8"))
    assert (data["outcome"], data["category"]) == ("needs a human", "checks")


def test_c11_update_resolve_a_session_that_ends_the_merge_is_a_guard_stop(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],  # noqa: F811
) -> None:
    local = delivered(project, tracker, pushes)
    move_base(project, {"app.txt": "version 3\n"})

    def abort(session: Session) -> None:
        sh(["git", "merge", "--abort"], session.cwd)

    runtime = FakeRuntime(action=on_update(abort))
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1, outcome.line
    assert "the update session ended the merge of origin/main" in outcome.line
    assert pushes == [] and not merge_pending(project)
    tree = worktree(project)
    assert git.is_ancestor(tree, local, git.head(tree)) and not git.status(tree)
    data = json.loads((tree / "work/7/metrics.json").read_text(encoding="utf-8"))
    assert (data["outcome"], data["category"]) == ("needs a human", "guard")
