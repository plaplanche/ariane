"""C9, C11: a run starts fewer git processes per round, with the same guarantees (#214, ADR 0053).

The counts per phase are those of `process_phases`. `BEFORE` is what the code before #214
started, `AFTER` the bound a later change must not exceed: raising one needs a new decision."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path

import pytest
from process_phases import PHASES, Count, counted
from test_c23_restart import nothing
from test_c23_restart import start as restart_start
from test_fix_rounds import NO_GO

from ariane import git
from ariane.config import CheckConfig, Config
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import PY, FakeRuntime, Project, edit_app, make_config, sh
from test_flow import start, worktree

CUT = ("guard verification", "remote listing", "record commits")


def _phases(*counts: int) -> dict[str, int]:
    return dict(zip(PHASES, counts, strict=True))


# setup, session, guard verification, remote listing, replay, review, record commits, delivery
BEFORE = {
    "go": _phases(11, 7, 46, 5, 3, 6, 12, 3),
    "three no-go": _phases(13, 29, 108, 11, 9, 18, 12, 3),
    "restart": _phases(29, 7, 46, 5, 3, 6, 12, 3),
    "three checks": _phases(11, 7, 68, 7, 9, 6, 12, 3),
}
AFTER = {
    "go": _phases(11, 6, 22, 5, 3, 6, 9, 3),
    "three no-go": _phases(13, 26, 48, 11, 9, 18, 9, 3),
    "restart": _phases(29, 6, 22, 5, 3, 6, 9, 3),
    "three checks": _phases(11, 6, 30, 5, 9, 6, 9, 3),
}


def _within(run: str, count: Count) -> None:
    over = {p: n for p, n in count.phases.items() if n > AFTER[run][p]}
    assert not over, f"{run}: {count.line()}; above the bound: {over}"
    assert set(count.phases) <= set(PHASES)
    for phase in CUT:  # every cut phase stays below what it was, where it was not already one
        if BEFORE[run][phase] > AFTER[run][phase]:
            assert count.phases[phase] < BEFORE[run][phase]


def _three_checks() -> Config:
    check = make_config().checks[0]
    return make_config(checks=tuple(dataclasses.replace(check, name=f"c{i}") for i in range(3)))


def test_c11_fewer_processes_a_go_on_the_first_round(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    with counted(monkeypatch) as count:
        outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == 0, outcome.line
    _within("go", count)
    assert sum(BEFORE["go"].values()) == 93 and count.total <= 65


def test_c11_fewer_processes_three_no_go_rounds_to_a_draft(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    with counted(monkeypatch) as count:
        outcome = start(project, tracker, FakeRuntime(answers=[NO_GO]))
    assert outcome.exit_code == 1 and "draft pull request" in outcome.line, outcome.line
    _within("three no-go", count)
    assert sum(BEFORE["three no-go"].values()) == 203 and count.total <= 137


def test_c11_fewer_processes_a_restart(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert restart_start(project, tracker, FakeRuntime(action=nothing)).exit_code == 1
    with counted(monkeypatch) as count:
        outcome = restart_start(project, tracker, FakeRuntime(), restarting=True)
    assert outcome.exit_code == 0, outcome.line
    _within("restart", count)
    assert sum(BEFORE["restart"].values()) == 111 and count.total <= 83


def test_c11_fewer_processes_the_replay_lists_the_remote_once_for_all_its_checks(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    with counted(monkeypatch) as count:
        outcome = start(project, tracker, FakeRuntime(), _three_checks())
    assert outcome.exit_code == 0, outcome.line
    _within("three checks", count)
    # The start, the agent session, the checks (once for three), the reviewer, the delivery.
    assert count.of("remote listing", "ls-remote") == 5


def test_c11_fewer_processes_a_snapshot_starts_three_git_processes(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    sh(["git", "branch", "a-first"], project.root)  # listed before the checked-out branch
    with counted(monkeypatch) as count:
        state = git.state(project.root, ignore_ref="none", watch_refs=["refs/remotes/origin/main"])
    assert count.total == 3, count.commands
    assert state.branch == "main" and state.head == sh(["git", "rev-parse", "HEAD"], project.root)
    assert state.snapshot["ref refs/heads/main"] == state.head
    assert state.snapshot["ref refs/heads/a-first"] == state.head
    assert state.snapshot["ref refs/remotes/origin/main"] == state.head
    assert git.config_snapshot(project.root, ignore_ref="none") == {
        k: v for k, v in state.snapshot.items() if k != "ref refs/remotes/origin/main"
    }
    sh(["git", "update-ref", "--no-deref", "HEAD", "HEAD"], project.root)  # detached
    detached = git.state(project.root, ignore_ref="none")
    assert (detached.branch, detached.head) == ("", "")
    assert git.detached_head(project.root) == state.head


def test_c11_fewer_processes_a_record_commit_starts_three_git_processes(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    (project.root / "record.txt").write_text("recorded\n", encoding="utf-8")
    env = git.token_free_environment()
    with counted(monkeypatch) as count:
        assert git.commit(project.root, ["record.txt"], "record", env=env)
    assert [_subcommand(argv) for _, argv in count.commands] == ["reset", "add", "commit"]
    with counted(monkeypatch) as count:  # nothing to commit: only then the index is compared
        assert not git.commit(project.root, ["record.txt"], "again", env=env)
    assert count.total == 4
    assert sh(["git", "log", "--format=%s", "-1"], project.root) == "record"


def _common(session: Session) -> Path:
    return Path(sh(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], session.cwd))


def _subcommand(argv: tuple[str, ...]) -> str:
    """The git command of `argv`, after its `-c key=value` options."""
    rest = list(argv[1:])
    while rest[0] == "-c":
        rest = rest[2:]
    return rest[0]


def _hook(session: Session) -> None:
    (_common(session) / "hooks" / "pre-push").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")


def _comment(session: Session) -> None:
    with (_common(session) / "config").open("a", encoding="utf-8") as config:
        config.write("# only a comment\n")


def _base_ref(session: Session) -> None:
    sh(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], session.cwd)


def _remote_branch(remote: Path) -> Callable[[Session], object]:
    def push(session: Session) -> None:
        sh(["git", "push", "--quiet", str(remote), "HEAD:refs/heads/ariane/7"], session.cwd)

    return push


def _rewrite(session: Session) -> None:
    sh(["git", "reset", "--quiet", "--soft", "HEAD~1"], session.cwd)


GIT_CHANGED = "the agent session changed git configuration, hooks or local branches"
CASES: dict[str, tuple[Callable[[Session], object], str]] = {
    "a hook": (_hook, GIT_CHANGED),
    "a config key": (
        lambda s: sh(["git", "config", "core.sshCommand", "evil"], s.cwd),
        GIT_CHANGED,
    ),
    "a comment in the shared config": (_comment, GIT_CHANGED),
    "a local branch": (lambda s: sh(["git", "branch", "other"], s.cwd), GIT_CHANGED),
    "a tag": (lambda s: sh(["git", "tag", "v9"], s.cwd), GIT_CHANGED),
    "the base's tracking ref": (_base_ref, GIT_CHANGED),
    "the checked-out branch": (
        lambda s: sh(["git", "update-ref", "--no-deref", "HEAD", "HEAD"], s.cwd),
        "the agent session left branch ariane/7 (now detached)",
    ),
    "the history": (_rewrite, "the agent session rewrote the ticket branch's history"),
}


@pytest.mark.parametrize("tampering", [*CASES, "a remote branch"])
def test_c11_fewer_processes_the_guard_still_stops_on_each_tampering(
    project: Project, tracker: InMemoryTracker, tampering: str
) -> None:
    if tampering == "a remote branch":
        action, reason = _remote_branch(project.remote), "the remote changed during the agent"
    else:
        action, reason = CASES[tampering]

    def tamper(session: Session) -> None:
        edit_app(session)
        action(session)

    outcome = start(project, tracker, FakeRuntime(action=tamper))
    assert outcome.exit_code == 1
    assert reason in outcome.line, outcome.line
    assert tracker.opened == []
    if tampering != "a remote branch":
        assert "ariane/7" not in project.remote_branches()


def test_c11_fewer_processes_a_check_that_changes_the_remote_still_stops_the_replay(
    project: Project, tracker: InMemoryTracker
) -> None:
    sneak = (
        PY,
        "-c",
        "import subprocess; subprocess.run(['git', 'push', '--quiet',"
        f" {str(project.remote)!r}, 'HEAD:refs/tags/sneaky'], check=True)",
    )
    checks = (*_three_checks().checks[:2], CheckConfig("sneaky", sneak, True, 1))
    outcome = start(project, tracker, FakeRuntime(), make_config(checks=checks))
    assert outcome.exit_code == 1
    assert "the remote changed during the checks (refs/tags/sneaky)" in outcome.line
    assert tracker.opened == [] and "ariane/7" not in project.remote_branches()


def test_c11_fewer_processes_a_reviewer_moving_the_ticket_branch_is_still_stopped(
    project: Project, tracker: InMemoryTracker
) -> None:
    """The ancestry of a head already verified is not checked twice; its head still is."""
    tree = worktree(project)
    identity = ["-c", "user.name=Sneak", "-c", "user.email=sneak@example.invalid"]

    def move(session: Session) -> None:
        sh(["git", *identity, "commit", "-q", "--allow-empty", "-m", "unreviewed"], tree)

    outcome = start(project, tracker, FakeRuntime(review_actions=[move]))
    assert outcome.exit_code == 1
    assert "the reviewer moved the ticket branch" in outcome.line, outcome.line
    assert tracker.opened == [] and "ariane/7" not in project.remote_branches()
