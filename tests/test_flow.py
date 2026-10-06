"""The slice 1 flow end to end, on real git with a local bare remote (C1, C5, C8, C9, C11)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ariane import flow, ticket
from ariane.config import CheckConfig, Config
from ariane.runtime import Session, StopReason
from ariane.tracker import InMemoryTracker

from conftest import PY, FakeRuntime, Project, make_config, sh

TOKEN = "secret-token-for-tests"


def environ() -> dict[str, str]:
    """Ariane's environment in a test: the real one (git identity, PATH) plus a token."""
    return {**os.environ, "GH_TOKEN": TOKEN}


def start(
    project: Project,
    tracker: InMemoryTracker,
    runtime: FakeRuntime,
    config: Config | None = None,
    number: int = 7,
) -> flow.Outcome:
    return flow.start(
        number,
        repo_root=project.root,
        config=config or make_config(),
        tracker=tracker,
        runtime=runtime,
        environ=environ(),
    )


def worktree(project: Project, number: int = 7) -> Path:
    return flow.worktree_path(project.root, number)


def journal(project: Project) -> str:
    return (worktree(project) / "work/7/journal.md").read_text(encoding="utf-8")


def test_c1_start_creates_ticket_folder_with_brief_prefilled_from_the_issue(
    project: Project, tracker: InMemoryTracker
) -> None:
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == 0, outcome.line
    brief = project.show("ariane/7", "work/7/brief.md")
    assert "# Product brief: Bump the app version" in brief
    assert "- Status: draft" in brief
    assert "Set app.txt to version 2." in brief
    assert "# Journal of ticket #7" in project.show("ariane/7", "work/7/journal.md")
    assert "State: delivered" in project.show("ariane/7", "work/7/status.md")


def test_c1_pull_request_number_is_refused_before_anything_is_created(
    project: Project, tracker: InMemoryTracker
) -> None:
    tracker.pull_request_numbers.add(9)
    runtime = FakeRuntime()
    outcome = start(project, tracker, runtime, number=9)
    assert outcome.exit_code == 1
    assert "pull request" in outcome.line
    assert not worktree(project, 9).exists()
    assert runtime.sessions == []


def test_c5_context_is_assembled_by_ariane_journaled_and_marks_the_issue_untrusted(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    assert start(project, tracker, runtime).exit_code == 0
    session = runtime.sessions[0]
    assert '<untrusted-ticket number="7">' in session.prompt
    assert "Set app.txt to version 2." in session.prompt
    assert session.prompt in journal(project)
    assert session.role == "implementer"
    assert "GH_TOKEN" not in session.env
    assert session.env["GIT_TERMINAL_PROMPT"] == "0"
    assert "Cost 0.4200 USD (as reported), tokens 10 in, 20 out" in journal(project)


def test_c5_budget_stop_keeps_the_work_on_the_branch_and_delivers_nothing(
    project: Project, tracker: InMemoryTracker
) -> None:
    outcome = start(project, tracker, FakeRuntime(stop_reason=StopReason.BUDGET))
    assert outcome.exit_code == 1
    assert "stopped: budget" in outcome.line
    assert (worktree(project) / "app.txt").read_text(encoding="utf-8") == "version 2\n"
    log = sh(["git", "log", "--format=%s", "-1", "--", "app.txt"], worktree(project))
    assert log == "#7: Bump the app version"
    assert "ariane/7" not in project.remote_branches()
    assert tracker.opened == []
    status = ticket.read_status(worktree(project) / "work/7")
    assert status["State"] == "stopped"


def test_c8_failing_setup_stops_the_ticket_with_its_output_and_no_agent_runs(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    setup = (PY, "-c", "import sys; print('setup exploded'); sys.exit(3)")
    outcome = start(project, tracker, runtime, make_config(setup=setup))
    assert outcome.exit_code == 1
    assert "setup" in outcome.line and "exit 3" in outcome.line
    assert "setup exploded" in outcome.detail
    assert "setup exploded" in journal(project)
    assert runtime.sessions == []


def test_c8_setup_leftovers_not_ignored_by_git_stop_the_ticket(
    project: Project, tracker: InMemoryTracker
) -> None:
    runtime = FakeRuntime()
    setup = (PY, "-c", "open('leftover.log', 'w').write('x')")
    outcome = start(project, tracker, runtime, make_config(setup=setup))
    assert outcome.exit_code == 1
    assert "does not ignore" in outcome.line
    assert "leftover.log" in journal(project)
    assert runtime.sessions == []


def test_c8_setup_files_ignored_by_git_are_accepted(
    project: Project, tracker: InMemoryTracker
) -> None:
    setup = (
        PY,
        "-c",
        "import os; os.makedirs('ignored-by-git'); open('ignored-by-git/x', 'w').write('x')",
    )
    outcome = start(project, tracker, FakeRuntime(), make_config(setup=setup))
    assert outcome.exit_code == 0, outcome.line


def test_c9_every_check_runs_and_a_failing_blocking_check_prevents_delivery(
    project: Project, tracker: InMemoryTracker
) -> None:
    checks = (
        CheckConfig("always fails", (PY, "-c", "print('broken'); raise SystemExit(1)"), True, 1),
        CheckConfig("always passes", (PY, "-c", "print('fine')"), True, 1),
    )
    outcome = start(project, tracker, FakeRuntime(), make_config(checks=checks))
    assert outcome.exit_code == 1
    assert "blocking checks failed: always fails" in outcome.line
    report = (worktree(project) / "work/7/checks.md").read_text(encoding="utf-8")
    assert "## always fails" in report and "broken" in report
    assert "## always passes" in report and "fine" in report
    assert report.rstrip().endswith("Summary: 1 passed, 1 failed (1 blocking).")
    assert "ariane/7" not in project.remote_branches()
    assert tracker.opened == []


def test_c9_a_failing_advisory_check_does_not_block_delivery(
    project: Project, tracker: InMemoryTracker
) -> None:
    checks = (CheckConfig("advisory", (PY, "-c", "raise SystemExit(1)"), False, 1),)
    outcome = start(project, tracker, FakeRuntime(), make_config(checks=checks))
    assert outcome.exit_code == 0, outcome.line
    assert "Summary: 0 passed, 1 failed (0 blocking)." in tracker.opened[0]["body"]


def test_c11_delivery_is_a_pushed_branch_and_a_pull_request_the_human_merges(
    project: Project, tracker: InMemoryTracker
) -> None:
    before = project.remote_branches()["main"]
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == 0
    assert outcome.line.startswith("Opened pull request memory://pulls/1001")
    assert "Next: review and merge it." in outcome.line
    heads = project.remote_branches()
    assert heads["main"] == before
    assert project.show("ariane/7", "app.txt") == "version 2"
    assert "Summary: 1 passed, 0 failed (0 blocking)." in project.show(
        "ariane/7", "work/7/checks.md"
    )
    pull = tracker.opened[0]
    assert (pull["head"], pull["base"]) == ("ariane/7", "main")
    assert pull["body"].startswith("Closes #7")
    assert "memory://blob/ariane/7/work/7/checks.md" in pull["body"]


def test_c11_the_main_checkout_is_never_modified(
    project: Project, tracker: InMemoryTracker
) -> None:
    head = sh(["git", "rev-parse", "HEAD"], project.root)
    assert start(project, tracker, FakeRuntime()).exit_code == 0
    assert sh(["git", "rev-parse", "HEAD"], project.root) == head
    assert sh(["git", "status", "--porcelain"], project.root) == ""
    assert (project.root / "app.txt").read_text(encoding="utf-8") == "version 1\n"
    assert not worktree(project).is_relative_to(project.root)


def _git_in_agent(session: Session, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=session.cwd, env=dict(session.env), capture_output=True, text=True
    )


def test_c11_a_plain_push_from_the_agent_working_tree_fails(
    project: Project, tracker: InMemoryTracker
) -> None:
    attempts: list[subprocess.CompletedProcess[str]] = []

    def push_then_edit(session: Session) -> None:
        sh(["git", "commit", "--quiet", "--allow-empty", "-m", "sneaky"], session.cwd)
        attempts.append(_git_in_agent(session, "push", "origin", "HEAD:main"))
        (session.cwd / "app.txt").write_text("version 2\n", encoding="utf-8")

    main_before = project.remote_branches()["main"]
    assert start(project, tracker, FakeRuntime(action=push_then_edit)).exit_code == 0
    assert attempts[0].returncode != 0
    assert project.remote_branches()["main"] == main_before


def test_c11_a_push_that_bypasses_the_guard_is_detected(
    project: Project, tracker: InMemoryTracker
) -> None:
    def push_explicitly(session: Session) -> None:
        (session.cwd / "app.txt").write_text("version 2\n", encoding="utf-8")
        sh(["git", "commit", "--quiet", "-am", "agent commit"], session.cwd)
        sh(
            ["git", "push", "--quiet", str(project.remote), "HEAD:refs/heads/elsewhere"],
            session.cwd,
        )

    outcome = start(project, tracker, FakeRuntime(action=push_explicitly))
    assert outcome.exit_code == 1
    assert "the remote changed during the agent session (refs/heads/elsewhere)" in outcome.line
    assert tracker.opened == []


def test_c11_an_agent_switching_branch_is_detected(
    project: Project, tracker: InMemoryTracker
) -> None:
    def switch(session: Session) -> None:
        sh(["git", "switch", "--quiet", "-c", "other"], session.cwd)

    outcome = start(project, tracker, FakeRuntime(action=switch))
    assert outcome.exit_code == 1
    assert "left branch ariane/7 (now other)" in outcome.line


def test_c11_an_agent_rewriting_history_is_detected(
    project: Project, tracker: InMemoryTracker
) -> None:
    def rewrite(session: Session) -> None:
        sh(["git", "reset", "--quiet", "--hard", "HEAD~1"], session.cwd)

    outcome = start(project, tracker, FakeRuntime(action=rewrite))
    assert outcome.exit_code == 1
    assert "rewrote the ticket branch's history" in outcome.line
    assert "Ticket started" in journal(project)  # the reset deleted it; Ariane restored it


def test_c11_an_agent_that_changed_nothing_stops_without_a_pull_request(
    project: Project, tracker: InMemoryTracker
) -> None:
    outcome = start(project, tracker, FakeRuntime(action=lambda session: None))
    assert outcome.exit_code == 1
    assert "changed no file" in outcome.line
    assert tracker.opened == []


def test_c11_a_ticket_already_started_is_refused(
    project: Project, tracker: InMemoryTracker
) -> None:
    sh(["git", "push", "--quiet", "origin", "main:refs/heads/ariane/7"], project.root)
    runtime = FakeRuntime()
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == 1
    assert "already exists on origin" in outcome.line
    assert not worktree(project).exists()
    assert runtime.sessions == []
    assert start(project, tracker, runtime, number=7).exit_code == 1
