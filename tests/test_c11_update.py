"""`ariane update <n>`: the base branch merged into a delivered ticket's branch, the checks
replayed, one review, then a fast-forward push on go (C11, C23; ADR 0033)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_fix_rounds import NO_GO

from ariane import cli, delivery, flow, git, process, replay, update
from ariane.config import CheckConfig, Config
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker, PullRequestState

from conftest import PY, FakeRuntime, Project, commit_on_branch, make_config, sh
from test_flow import environ, start, worktree

OPEN = PullRequestState("2026-10-20T10:00:00Z", "", False)
NOT_BROKEN = CheckConfig(
    "nothing broken",
    (PY, "-c", "import os, sys; sys.exit(1 if os.path.exists('broken.txt') else 0)"),
    True,
    1.0,
)


def config() -> Config:
    base = make_config()
    return make_config(checks=(*base.checks, NOT_BROKEN))


@pytest.fixture
def pushes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    done: list[str] = []
    real = git.push

    def counting(*args: Any, **kwargs: Any) -> str:
        done.append(str(args[2]))
        return real(*args, **kwargs)

    monkeypatch.setattr(git, "push", counting)
    return done


def delivered(
    project: Project, tracker: InMemoryTracker, pushes: list[str] | None = None
) -> FakeRuntime:
    """Ticket #7 delivered, its pull request open, its push not counted; the runtime of the
    update, fresh."""
    outcome = start(project, tracker, FakeRuntime(), config())
    assert outcome.exit_code == 0, outcome.line
    tracker.pull_states["ariane/7"] = OPEN
    if pushes is not None:
        pushes.clear()
    return FakeRuntime()


def move_base(project: Project, files: dict[str, str]) -> str:
    """A commit on the remote's base branch, made in the bare remote itself."""
    commit_on_branch(project.remote, "main", "base moved", files)
    return project.remote_branches()["main"]


def run_update(project: Project, tracker: InMemoryTracker, runtime: FakeRuntime) -> flow.Outcome:
    return update.update(
        7,
        repo_root=project.root,
        config=config(),
        tracker=tracker,
        runtime=runtime,
        environ=environ(),
    )


def reviewers(runtime: FakeRuntime) -> list[Session]:
    return [s for s in runtime.sessions if s.role == "reviewer"]


def head(project: Project) -> str:
    return git.head(worktree(project))


def test_c11_update_merges_the_moved_base_replays_reviews_and_fast_forwards(
    project: Project, tracker: InMemoryTracker, pushes: list[str]
) -> None:
    runtime = delivered(project, tracker, pushes)
    before = project.remote_branches()["ariane/7"]
    base = move_base(project, {"other.txt": "from the base\n"})
    statuses = len(tracker.statuses)
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 0, outcome.line
    assert "Updated ariane/7 with origin/main" in outcome.line
    pushed = project.remote_branches()["ariane/7"]
    assert pushes == [pushed]
    tree = worktree(project)
    assert git.is_ancestor(tree, before, pushed)  # a fast-forward
    merges = sh(["git", "log", "--merges", "--format=%H %P", f"{before}..{pushed}"], tree)
    merge, *parents = merges.split()
    assert len(parents) == 2 and parents[1] == base
    assert len(reviewers(runtime)) == 1
    assert not [s for s in runtime.sessions if s.role == "implementer"]
    assert len(tracker.opened) == 1  # the delivery's only
    new = tracker.statuses[statuses:]
    assert {s["context"] for s in new} == {"ariane/app has version 2", "ariane/nothing broken"}
    assert {s["sha"] for s in new} == {pushed}
    shown = project.show("ariane/7", "work/7/journal.md")
    assert "Update started" in shown and f"Merge commit `{merge}`" in shown
    assert project.show("ariane/7", "work/7/review-1.md").startswith("# Review 1")
    assert merge in project.show("ariane/7", "work/7/checks.md")
    assert "Update pushed" in (tree / "work/7/journal.md").read_text(encoding="utf-8")
    assert not git.status(tree)


def test_c11_update_of_an_up_to_date_branch_writes_and_pushes_nothing(
    project: Project, tracker: InMemoryTracker, pushes: list[str]
) -> None:
    runtime = delivered(project, tracker, pushes)
    local = head(project)
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 0
    assert outcome.line == "Ticket #7 is up to date with main. Next: nothing."
    assert head(project) == local and not git.status(worktree(project))
    assert pushes == [] and runtime.sessions == []


@pytest.mark.parametrize(
    ("state", "said"),
    [
        (None, "no pull request from ariane/7"),
        (PullRequestState("a", "b", True), "the pull request from ariane/7 is merged"),
        (PullRequestState("a", "b", False), "the pull request from ariane/7 is closed"),
    ],
)
def test_c11_update_refuses_without_an_open_pull_request(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],
    state: PullRequestState | None,
    said: str,
) -> None:
    runtime = delivered(project, tracker, pushes)
    tracker.pull_states.pop("ariane/7")
    if state is not None:
        tracker.pull_states["ariane/7"] = state
    move_base(project, {"other.txt": "x\n"})
    local = head(project)
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert said in outcome.line and "Next: " in outcome.line
    assert head(project) == local and pushes == [] and runtime.sessions == []


def test_c11_update_refuses_a_missing_or_dirty_working_tree(
    project: Project, tracker: InMemoryTracker, pushes: list[str]
) -> None:
    runtime = delivered(project, tracker, pushes)
    move_base(project, {"other.txt": "x\n"})
    tree = worktree(project)
    (tree / "app.txt").write_text("edited by hand\n", encoding="utf-8")
    local = head(project)
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1 and "uncommitted changes" in outcome.line
    assert head(project) == local
    assert (tree / "app.txt").read_text(encoding="utf-8") == "edited by hand\n"
    sh(["git", "worktree", "remove", "--force", str(tree)], project.root)
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1 and "is missing" in outcome.line
    assert pushes == [] and runtime.sessions == []


def test_c11_update_refuses_a_working_tree_on_another_branch(
    project: Project, tracker: InMemoryTracker, pushes: list[str]
) -> None:
    runtime = delivered(project, tracker, pushes)
    move_base(project, {"other.txt": "x\n"})
    sh(["git", "switch", "--quiet", "-c", "elsewhere"], worktree(project))
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1 and "is on elsewhere, not ariane/7" in outcome.line
    assert pushes == [] and runtime.sessions == []


def test_c11_update_refuses_a_local_branch_that_diverged_from_the_remote(
    project: Project, tracker: InMemoryTracker, pushes: list[str]
) -> None:
    runtime = delivered(project, tracker, pushes)
    move_base(project, {"other.txt": "x\n"})
    tree = worktree(project)
    (tree / "app.txt").write_text("version 2\nby hand\n", encoding="utf-8")
    sh(["git", "commit", "--quiet", "-am", "by hand"], tree)
    local = head(project)
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "the local branch ariane/7 diverged from origin/ariane/7" in outcome.line
    assert head(project) == local and pushes == [] and runtime.sessions == []
    assert not sh(["git", "log", "--merges", "--format=%H", "-1"], tree)


def test_c11_update_refuses_extra_commits_that_change_then_revert_code(
    project: Project, tracker: InMemoryTracker, pushes: list[str]
) -> None:
    runtime = delivered(project, tracker, pushes)
    move_base(project, {"other.txt": "x\n"})
    tree = worktree(project)
    (tree / "app.txt").write_text("version 2\nby hand\n", encoding="utf-8")
    sh(["git", "commit", "--quiet", "-am", "by hand"], tree)
    sh(["git", "revert", "--quiet", "--no-edit", "HEAD"], tree)
    local = head(project)
    endpoints = git.changed_between(tree, project.remote_branches()["ariane/7"], local)
    assert endpoints and all(p.startswith("work/7/") for p in endpoints)  # the revert hides it
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "the local branch ariane/7 diverged from origin/ariane/7" in outcome.line
    assert head(project) == local and pushes == [] and runtime.sessions == []


def test_c11_update_conflict_is_aborted_and_needs_a_human(
    project: Project, tracker: InMemoryTracker, pushes: list[str]
) -> None:
    runtime = delivered(project, tracker, pushes)
    move_base(project, {"app.txt": "version 3\n"})
    local = head(project)
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1, outcome.line
    assert "conflicts in app.txt" in outcome.line and "ariane verify ariane/7" in outcome.line
    tree = worktree(project)
    assert not git.git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], tree, check=False).ok
    assert (tree / "app.txt").read_text(encoding="utf-8").startswith("version 2")
    assert git.is_ancestor(tree, local, head(project))
    assert git.changed_between(tree, local, head(project)) == [
        "work/7/journal.md",
        "work/7/metrics.json",
        "work/7/status.md",
    ]
    status = (tree / "work/7/status.md").read_text(encoding="utf-8")
    assert "Last action: needs a human" in status
    assert pushes == [] and runtime.sessions == [] and not git.status(tree)


def test_c11_update_no_go_review_pushes_nothing_and_keeps_the_merge(
    project: Project, tracker: InMemoryTracker, pushes: list[str]
) -> None:
    delivered(project, tracker, pushes)
    runtime = FakeRuntime(answers=[NO_GO])
    remote = project.remote_branches()["ariane/7"]
    move_base(project, {"other.txt": "x\n"})
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1 and "review of the update is no-go" in outcome.line
    assert pushes == [] and project.remote_branches()["ariane/7"] == remote
    tree = worktree(project)
    assert sh(["git", "log", "--merges", "--format=%H", "-1"], tree)
    assert (tree / "work/7/review-1.md").is_file()
    status = (tree / "work/7/status.md").read_text(encoding="utf-8")
    assert "Last action: needs a human" in status and "Stopped" in (
        tree / "work/7/journal.md"
    ).read_text(encoding="utf-8")
    assert not git.status(tree)


def test_c11_update_red_blocking_check_after_the_merge_pushes_nothing(
    project: Project, tracker: InMemoryTracker, pushes: list[str]
) -> None:
    runtime = delivered(project, tracker, pushes)
    remote = project.remote_branches()["ariane/7"]
    move_base(project, {"broken.txt": "the base broke it\n"})
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "blocking checks failed after the merge: nothing broken" in outcome.line
    assert pushes == [] and project.remote_branches()["ariane/7"] == remote
    assert reviewers(runtime) == []
    tree = worktree(project)
    assert "needs a human" in (tree / "work/7/status.md").read_text(encoding="utf-8")


def test_c11_update_remote_branch_moved_during_the_update_pushes_nothing(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = delivered(project, tracker, pushes)
    move_base(project, {"other.txt": "x\n"})
    real = replay.review_round

    def then_someone_pushes(*args: Any, **kwargs: Any) -> Any:
        settled = real(*args, **kwargs)
        commit_on_branch(project.remote, "ariane/7", "pushed by a person", {"p.txt": "p\n"})
        return settled

    monkeypatch.setattr(replay, "review_round", then_someone_pushes)
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "ariane/7 moved on origin during the update" in outcome.line
    assert pushes == []


@pytest.mark.parametrize("moved_to", ["parent", "deleted"])
def test_c11_update_remote_branch_moved_after_the_last_guard_pushes_nothing(
    project: Project,
    tracker: InMemoryTracker,
    monkeypatch: pytest.MonkeyPatch,
    moved_to: str,
) -> None:
    runtime = delivered(project, tracker)
    move_base(project, {"other.txt": "x\n"})
    remote = project.remote_branches()["ariane/7"]
    real = git.push

    def racing(*args: Any, **kwargs: Any) -> str:
        # Someone moves the branch back, or deletes it, between the last read and the push.
        if moved_to == "parent":
            sh(["git", "update-ref", "refs/heads/ariane/7", f"{remote}^"], project.remote)
        else:
            sh(["git", "branch", "-D", "ariane/7"], project.remote)
        return real(*args, **kwargs)

    monkeypatch.setattr(git, "push", racing)
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1, outcome.line
    assert "git push failed" in outcome.line
    if moved_to == "parent":
        assert (
            project.remote_branches()["ariane/7"]
            == sh(["git", "rev-parse", f"{remote}^"], project.remote).strip()
        )
    else:
        assert "ariane/7" not in project.remote_branches()
    tree = worktree(project)
    assert "Stopped" in (tree / "work/7/journal.md").read_text(encoding="utf-8")
    status = (tree / "work/7/status.md").read_text(encoding="utf-8")
    assert "Last action: needs a human" in status


@pytest.mark.parametrize("abort", ["fails", "leaves a file"])
def test_c11_update_conflict_not_undone_by_the_abort_keeps_it_and_writes_nothing(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],
    monkeypatch: pytest.MonkeyPatch,
    abort: str,
) -> None:
    runtime = delivered(project, tracker, pushes)
    move_base(project, {"app.txt": "version 3\n"})
    tree = worktree(project)
    local = head(project)
    records = {n: (tree / "work/7" / n).read_text("utf-8") for n in ("journal.md", "status.md")}
    real = git.git

    def aborting(args: list[str], cwd: Path, **kwargs: Any) -> process.Completed:
        if args != ["merge", "--abort"]:
            return real(args, cwd, **kwargs)
        if abort == "fails":
            return process.Completed(("git", *args), 128, "", "error: abort refused", False, 0.0)
        done = real(args, cwd, **kwargs)
        (cwd / "left.txt").write_text("left by a hook\n", encoding="utf-8")
        return done

    monkeypatch.setattr(git, "git", aborting)
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1, outcome.line
    assert "`git merge --abort` did not restore ariane/7" in outcome.line
    assert "needs a human" in outcome.line and "conflicts in app.txt" in outcome.line
    assert head(project) == local and pushes == [] and runtime.sessions == []
    assert {n: (tree / "work/7" / n).read_text("utf-8") for n in records} == records
    if abort == "fails":  # the unresolved merge is kept, not reset by a record commit
        assert git.git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], tree, check=False).ok
        assert "<<<<<<<" in (tree / "app.txt").read_text(encoding="utf-8")
        assert "app.txt" in git.out(["diff", "--name-only", "--diff-filter=U"], tree)
    else:
        assert (tree / "left.txt").is_file()


def test_c11_update_refused_delivery_is_recorded_as_a_stop(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = delivered(project, tracker, pushes)
    remote = project.remote_branches()["ariane/7"]
    move_base(project, {"other.txt": "x\n"})

    def refused(self: delivery.Delivery) -> None:
        raise delivery.PullRequestRefused("git configuration rewrites URLs", "remove them")

    monkeypatch.setattr(delivery.Delivery, "_last_guard", refused)
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "rewrites URLs" in outcome.line and "Next: remove them" in outcome.line
    assert pushes == [] and project.remote_branches()["ariane/7"] == remote
    tree = worktree(project)
    assert "needs a human" in (tree / "work/7/status.md").read_text(encoding="utf-8")
    assert "Stopped" in (tree / "work/7/journal.md").read_text(encoding="utf-8")


def test_c11_update_metrics_hold_the_delivery_and_the_update(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = delivered(project, tracker)
    tree = worktree(project)
    first = json.loads((tree / "work/7/metrics.json").read_text(encoding="utf-8"))
    move_base(project, {"other.txt": "x\n"})
    assert run_update(project, tracker, runtime).exit_code == 0
    data = json.loads(project.show("ariane/7", "work/7/metrics.json"))
    assert data["updates"] == 1
    assert data["started"] == first["started"]
    assert data["sessions"][: len(first["sessions"])] == first["sessions"]
    assert len(data["sessions"]) == len(first["sessions"]) + 1
    assert data["sessions"][-1]["role"] == "reviewer" and data["sessions"][-1]["round"] == 1
    assert data["steps"][: len(first["steps"])] == first["steps"]
    assert "base merged" in [s["name"] for s in data["steps"]]
    assert data["outcome"] == "delivered"


def test_c11_update_command_line(
    project: Project,
    tracker: InMemoryTracker,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    called: dict[str, Any] = {}

    def fake(number: int, **kwargs: Any) -> flow.Outcome:
        called["number"] = number
        return flow.Outcome(0, "Ticket #7 is up to date with main. Next: nothing.")

    (project.root / "ariane.toml").write_text(
        Path(__file__).parent.parent.joinpath("docs/ariane.example.toml").read_text("utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(update, "update", fake)
    monkeypatch.chdir(project.root)
    monkeypatch.setenv("GH_TOKEN", "t")
    assert cli.main(["update", "#7"]) == 0
    assert called == {"number": 7}
    assert "up to date" in capsys.readouterr().out


def test_c11_update_up_to_date_is_decided_before_any_fetch(
    project: Project, tracker: InMemoryTracker, pushes: list[str]
) -> None:
    """An up-to-date branch is answered from the remote's base listed by `ls-remote`: no fetch
    runs, so `FETCH_HEAD`, the base's tracking ref and its reflog are as they were."""
    runtime = delivered(project, tracker, pushes)
    common = Path(
        git.out(["rev-parse", "--path-format=absolute", "--git-common-dir"], project.root)
    )

    def metadata() -> tuple[str, str, str]:
        fetched = common / "FETCH_HEAD"
        log = common / "logs/refs/remotes/origin/main"
        return (
            fetched.read_text(encoding="utf-8") if fetched.exists() else "",
            git.out(["rev-parse", "refs/remotes/origin/main"], project.root),
            log.read_text(encoding="utf-8") if log.exists() else "",
        )

    before = metadata()
    (common / "FETCH_HEAD").unlink(missing_ok=True)
    outcome = run_update(project, tracker, runtime)
    assert outcome.line == "Ticket #7 is up to date with main. Next: nothing."
    assert not (common / "FETCH_HEAD").exists()
    assert metadata()[1:] == before[1:]


@pytest.mark.parametrize("how", ["ctrl-c after a conflicting merge", "the abort raises"])
def test_c11_update_a_merge_left_half_done_writes_no_record(
    project: Project,
    tracker: InMemoryTracker,
    pushes: list[str],
    monkeypatch: pytest.MonkeyPatch,
    how: str,
) -> None:
    """Ctrl-C or an error once git wrote the merge state: nothing is written or committed (a
    record commit's reset would drop the unresolved merge), the merge state is kept."""
    runtime = delivered(project, tracker, pushes)
    move_base(project, {"app.txt": "version 3\n"})
    tree = worktree(project)
    local = head(project)
    records = {n: (tree / "work/7" / n).read_text("utf-8") for n in ("journal.md", "status.md")}
    real = git.git

    def interrupting(args: list[str], cwd: Path, **kwargs: Any) -> process.Completed:
        if how == "the abort raises" and args == ["merge", "--abort"]:
            raise OSError("the abort could not start")
        done = real(args, cwd, **kwargs)
        if how.startswith("ctrl-c") and args[:2] == ["merge", "--no-ff"]:
            raise KeyboardInterrupt
        return done

    monkeypatch.setattr(git, "git", interrupting)
    outcome = run_update(project, tracker, runtime)
    assert outcome.exit_code == 1, outcome.line
    assert "needs a human" in outcome.line and "neither finished nor undone" in outcome.line
    assert head(project) == local and pushes == [] and runtime.sessions == []
    assert {n: (tree / "work/7" / n).read_text("utf-8") for n in records} == records
    monkeypatch.setattr(git, "git", real)
    assert git.git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], tree, check=False).ok
    assert "app.txt" in git.out(["diff", "--name-only", "--diff-filter=U"], tree)


def test_c11_update_a_check_scoped_to_files_only_the_base_changed_still_runs(
    project: Project, tracker: InMemoryTracker, pushes: list[str]
) -> None:
    """The checks are selected from what the merge brings from the base too: a blocking check
    scoped to `src/**`, which the ticket never touched, runs once the base changes `src/` and
    stops the push when the combination breaks it (ADR 0033, ADR 0056)."""
    scoped = CheckConfig(
        "src still works",
        (PY, "-c", "import os, sys; sys.exit(1 if os.path.exists('src/broken.txt') else 0)"),
        True,
        1.0,
        paths=("src/**",),
    )
    base = make_config()
    scoped_config = make_config(checks=(*base.checks, scoped))
    outcome = start(project, tracker, FakeRuntime(), scoped_config)
    assert outcome.exit_code == 0, outcome.line
    tracker.pull_states["ariane/7"] = OPEN
    pushes.clear()
    remote = project.remote_branches()["ariane/7"]
    move_base(project, {"src/broken.txt": "the base broke src\n"})
    runtime = FakeRuntime()
    outcome = update.update(
        7,
        repo_root=project.root,
        config=scoped_config,
        tracker=tracker,
        runtime=runtime,
        environ=environ(),
    )
    assert outcome.exit_code == 1, outcome.line
    assert "src still works" in outcome.line
    assert pushes == [] and project.remote_branches()["ariane/7"] == remote
