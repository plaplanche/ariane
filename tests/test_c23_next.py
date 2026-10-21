"""`ariane next`: the queue, its dependencies, the files each ticket is expected to touch, the run
slots and the last run decide the proposal; `--start` starts it on confirmation (C11, C22, C23,
ADR 0059)."""

from __future__ import annotations

import dataclasses
import getpass
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from ariane import config, flow, next_ticket, runs, slots, ticket
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, commit_on_branch, make_config
from test_flow import environ

LABEL = "ariane-next"


def queued(tracker: InMemoryTracker, number: int, body: str, at: str, *labels: str) -> None:
    """Issue `number`, its queue label added at `at` (an ISO time)."""
    tracker.add_issue(number, f"Issue {number}", body)
    tracker.labels[number] = [LABEL, *labels]
    tracker.labelled_at[(number, LABEL)] = at


def at(minute: int) -> str:
    return f"2026-10-21T10:{minute:02d}:00Z"


def numbers(proposal: next_ticket.Proposal) -> list[int]:
    return [c.number for c in proposal.candidates]


def reasons(proposal: next_ticket.Proposal, number: int) -> tuple[str, ...]:
    return next(c.reasons for c in proposal.candidates if c.number == number)


def test_c23_next_queue_follows_the_label_order_without_closed_or_unlabelled_issues(
    project: Project,
) -> None:
    tracker = InMemoryTracker()
    queued(tracker, 3, "Edit `a.txt`.", at(5))
    queued(tracker, 4, "Edit `b.txt`.", at(1))
    queued(tracker, 6, "Edit `c.txt`.", at(0))
    tracker.closed[6] = "completed"
    tracker.add_issue(5, "Not queued", "No label.")
    tracker.labels[5] = ["ariane"]
    proposal = next_ticket.propose(project.root, make_config(), tracker)
    assert numbers(proposal) == [4, 3]
    assert proposal.number == 4
    assert proposal.last_line() == ("Next: #4 (nothing runs). Start it with ariane next --start.")


def test_c23_next_look_ahead_limits_the_issues_looked_at(project: Project) -> None:
    tracker = InMemoryTracker()
    for n in range(1, 9):
        queued(tracker, n, "", at(n))
    cfg = dataclasses.replace(make_config(), next=config.NextConfig(look_ahead=2))
    assert numbers(next_ticket.propose(project.root, cfg, tracker)) == [1, 2]
    assert len(numbers(next_ticket.propose(project.root, make_config(), tracker))) == 5


def test_c23_next_needs_waits_until_each_issue_is_closed_as_completed(project: Project) -> None:
    assert next_ticket.needs("Text.\n\nNeeds #8 and #9.\n- Needs #9, #12\nIt Needs #3") == [
        8,
        9,
        12,
    ]
    tracker = InMemoryTracker()
    queued(tracker, 10, "## Related\n\nNeeds #8 and #9.", at(0))
    tracker.closed[8] = "completed"
    proposal = next_ticket.propose(project.root, make_config(), tracker)
    assert reasons(proposal, 10) == ("waits on #9",)
    assert proposal.number is None
    tracker.closed[9] = "not_planned"
    assert reasons(next_ticket.propose(project.root, make_config(), tracker), 10) == (
        "waits on #9",
    )
    tracker.closed[9] = "completed"
    assert next_ticket.propose(project.root, make_config(), tracker).number == 10


def module_files(project: Project) -> None:
    for path in ("docs/architecture/modules/cli.md", "src/pkg/cli.py", "tests/test_cli.py"):
        (project.root / path).parent.mkdir(parents=True, exist_ok=True)
        (project.root / path).write_text("x\n", encoding="utf-8")
    (project.root / "tests/test_client.py").write_text("x\n", encoding="utf-8")


def test_c23_next_expected_paths_from_the_body_modules_and_label_globs(project: Project) -> None:
    module_files(project)
    body = (
        "Change `src/pkg/x.py`, see https://example.invalid/a/b.md and owner/name.\n"
        "Update `cli.md`, the README.md, `docs/adr/` and `<repo>.ariane/next.md`; `notes.md`."
    )
    settings = config.NextConfig(paths=(("docs", ("docs/**/*.md",)), ("other", ("x/**",))))
    found = next_ticket.expected_paths(body, ("docs",), project.root, settings)
    assert found == (
        "src/pkg/x.py",
        "docs/architecture/modules/cli.md",
        "docs/adr/**",
        "src/pkg/cli.py",
        "tests/test_cli.py",
        "docs/**/*.md",
    )
    (project.root / "README.md").write_text("x\n", encoding="utf-8")
    assert "README.md" in next_ticket.expected_paths(body, (), project.root, settings)
    assert next_ticket.shared(["docs/adr/**", "a.py"], ["docs/adr/0001.md", "a.py", "b/**"]) == [
        "a.py",
        "docs/adr/0001.md",
    ]


def test_c23_next_a_shared_file_with_a_running_ticket_is_named_and_not_proposed(
    project: Project,
) -> None:
    module_files(project)
    commit_on_branch(project.root, "ariane/12", "work", {"app.txt": "v2\n"}, parent="main")
    tracker = InMemoryTracker()
    queued(tracker, 12, "Change `src/pkg/cli.py`.", at(0))
    queued(tracker, 13, "Edit `app.txt` again.", at(1))
    queued(tracker, 14, "Document it in `cli.md`.", at(2))
    queued(tracker, 15, "Write `docs/other/new.md`.", at(3))
    with runs.registered(runs.folder(project.root), 12, "ariane/12"):
        proposal = next_ticket.propose(project.root, make_config(), tracker)
    assert proposal.running == (12,)
    assert numbers(proposal) == [13, 14, 15]
    assert reasons(proposal, 13) == ("shares app.txt with running #12",)
    assert reasons(proposal, 14) == ("shares src/pkg/cli.py with running #12",)
    assert proposal.number == 15
    assert proposal.last_line() == (
        "Next: #15 (no shared file with #12). Start it with ariane next --start."
    )
    assert "- #13: shares app.txt with running #12" in proposal.lines()


def test_c23_next_an_already_started_issue_is_not_proposed(project: Project) -> None:
    commit_on_branch(project.root, "ariane/3", "work", {"app.txt": "v2\n"}, parent="main")
    tracker = InMemoryTracker()
    queued(tracker, 3, "", at(0))
    queued(tracker, 4, "", at(1))
    proposal = next_ticket.propose(project.root, make_config(), tracker)
    assert reasons(proposal, 3) == ("already started (branch ariane/3); see ariane status 3",)
    assert proposal.number == 4


def test_c23_next_no_free_run_slot_proposes_nothing_and_says_why(
    project: Project, isolated_slots: Path
) -> None:
    tracker = InMemoryTracker()
    queued(tracker, 4, "", at(0))
    with slots.several(slots.COUNT, isolated_slots):
        proposal = next_ticket.propose(project.root, make_config(), tracker)
    assert proposal.number is None
    assert reasons(proposal, 4) == (f"no free run slot ({slots.REASON})",)
    assert proposal.last_line() == (
        f"Nothing to start: no free run slot ({slots.REASON})."
        " Next: wait for a run to end, then run ariane next."
    )
    assert next_ticket.propose(project.root, make_config(), tracker).number == 4


def stopped_run(project: Project, number: int, stop_reason: str) -> None:
    where = runs.folder(project.root)
    where.mkdir(parents=True, exist_ok=True)
    lines = [
        {"number": 2, "branch": "ariane/2", "pid": 1, "started": at(0), "ended": at(1)},
        {"number": number, "branch": "x", "pid": 1, "started": at(2), "ended": at(9)},
    ]
    (where / runs.ENDED).write_text("".join(json.dumps(e) + "\n" for e in lines), "utf-8")
    folder = ticket.folder_path(flow.worktree_path(project.root, number), number)
    folder.mkdir(parents=True)
    metrics = {"outcome": "stopped", "sessions": [{"stop_reason": stop_reason}]}
    (folder / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")


def test_c23_next_a_last_run_stopped_on_a_quota_proposes_nothing(project: Project) -> None:
    tracker = InMemoryTracker()
    queued(tracker, 4, "", at(0))
    stopped_run(project, 20, "quota")
    proposal = next_ticket.propose(project.root, make_config(), tracker)
    assert proposal.number is None
    assert reasons(proposal, 4) == ("the last run, #20, stopped on a quota of its agent",)
    assert proposal.last_line().endswith(
        "Next: once the quota resets, run ariane start 20 --restart."
    )


def test_c23_next_a_last_run_stopped_otherwise_does_not_block(project: Project) -> None:
    tracker = InMemoryTracker()
    queued(tracker, 4, "", at(0))
    stopped_run(project, 20, "error")
    assert next_ticket.last_quota_stop(project.root) is None
    assert next_ticket.propose(project.root, make_config(), tracker).number == 4


def test_c23_next_start_refuses_a_proposal_that_changed_since_it_was_printed(
    project: Project,
) -> None:
    tracker = InMemoryTracker()
    queued(tracker, 4, "", at(0), "ariane")
    queued(tracker, 5, "", at(1), "ariane")
    launched: list[int] = []

    def launch(number: int) -> int:
        launched.append(number)
        return 1

    _, outcome = next_ticket.start(project.root, make_config(), tracker, launch)
    assert outcome.exit_code == flow.EXIT_STOPPED
    assert "was none printed, now #4 (nothing runs)" in outcome.line
    assert next_ticket.show(project.root, make_config(), tracker).number == 4
    tracker.closed[4] = "completed"
    _, outcome = next_ticket.start(project.root, make_config(), tracker, launch)
    assert outcome.line == (
        "Did not start: the proposal changed since it was printed (was #4 (nothing runs), now"
        " #5 (nothing runs)). Next: read it above, then run ariane next --start to confirm it."
    )
    assert launched == []
    assert tracker.removed_labels == []


def test_c23_next_start_relabels_the_issue_and_starts_it(project: Project) -> None:
    tracker = InMemoryTracker()
    queued(tracker, 7, "Set `app.txt` to version 2.", at(0), "ariane")
    queued(tracker, 8, "Needs #7", at(1), "ariane")
    cfg = make_config()
    outcomes: list[flow.Outcome] = []

    def launch(number: int) -> int:
        # The fake runtime: the ticket runs here, to its pull request.
        outcomes.append(
            flow.start(
                number,
                repo_root=project.root,
                config=cfg,
                tracker=tracker,
                runtime=FakeRuntime(),
                environ=environ(),
            )
        )
        return 4242

    assert next_ticket.show(project.root, cfg, tracker).number == 7
    proposal, outcome = next_ticket.start(project.root, cfg, tracker, launch)
    assert proposal.number == 7
    assert tracker.removed_labels == [(7, "ariane")]
    assert tracker.labels[7] == [LABEL, "ariane"]
    assert outcomes[0].exit_code == flow.EXIT_OK, outcomes[0].line
    journal = flow.worktree_path(project.root, 7) / "work/7/journal.md"
    assert journal.is_file()
    assert outcome.exit_code == flow.EXIT_OK
    assert outcome.line == (
        f"Started #7 in the background (process 4242); its journal will be {journal}, its output"
        f" {next_ticket.output_path(project.root, 7)}. Next: follow it with ariane status 7."
    )
    _, again = next_ticket.start(project.root, cfg, tracker, launch)
    assert again.exit_code == flow.EXIT_STOPPED  # #7 started since: the proposal changed
    assert len(outcomes) == 1


def test_c23_next_records_every_proposal_and_start_in_next_md(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(getpass, "getuser", lambda: "owner")
    tracker = InMemoryTracker()
    queued(tracker, 4, "Needs #2", at(0), "ariane")
    queued(tracker, 5, "", at(1), "ariane")
    next_ticket.show(project.root, make_config(), tracker)
    next_ticket.start(project.root, make_config(), tracker, lambda number: 99)
    text = next_ticket.record_path(project.root).read_text(encoding="utf-8")
    assert next_ticket.record_path(project.root) == project.root.parent / "proj.ariane/next.md"
    entries = text.split("\n## ")
    assert entries[0] == "# Proposals of ariane next\n"
    assert entries[1].split("\n", 1)[0].endswith(": proposal")
    assert entries[2].split("\n", 1)[0].endswith(": start")
    for entry in entries[1:]:
        assert "- Running: none." in entry
        assert "- #4: waits on #2" in entry
        assert "- #5: can start" in entry
        assert "- Proposal: #5 (nothing runs)" in entry
    assert "- Confirmed by: owner (ariane next --start)" in entries[2]
    assert "- Started: #5, process 99" in entries[2]


def test_c23_next_spawn_runs_ariane_start_detached_with_its_output_kept(project: Project) -> None:
    pid = next_ticket.spawn(project.root, 31, environ())
    if sys.platform != "win32":
        assert os.getsid(pid) == pid  # its own session: detached from the terminal
    out = next_ticket.output_path(project.root, 31)
    assert out == project.root.parent / "proj.ariane/logs/31.out"
    deadline = time.monotonic() + 60
    while runs.alive(pid) and time.monotonic() < deadline:  # it ends before the project goes
        if sys.platform != "win32" and os.waitpid(pid, os.WNOHANG)[0]:
            break
        time.sleep(0.1)
    text = out.read_text(encoding="utf-8", errors="replace")
    assert "Refused configuration: ariane.toml: file not found" in text


def test_c23_next_config_reads_the_queue_label_and_the_next_table() -> None:
    tracker = {"kind": "github", "repository": "o/n", "token_env": "T"}
    base: dict[str, Any] = {
        "project": {"base_branch": "main"},
        "tracker": tracker,
        "agents": {
            role: {
                "runtime": "claude-code",
                "model": model,
                "tools": ["Read", "Glob", "Grep"],
                "max_budget_usd": 1,
                "timeout_minutes": 5,
            }
            for role, model in (("implementer", "a"), ("reviewer", "b"))
        },
        "checks": [{"name": "t", "command": ["x"]}],
    }
    parsed = config.parse(base)
    assert parsed.tracker.next_label == "ariane-next"
    assert parsed.next == config.NextConfig(look_ahead=5, paths=())
    data = {
        **base,
        "tracker": {**tracker, "next_label": "queue"},
        "next": {"look_ahead": 3, "paths": {"docs": ["docs/**"]}},
    }
    parsed = config.parse(data)
    assert parsed.tracker.next_label == "queue"
    assert parsed.next == config.NextConfig(look_ahead=3, paths=(("docs", ("docs/**",)),))
    for bad, key in (
        ({"next": {"look_ahead": 0}}, "next.look_ahead"),
        ({"next": {"other": 1}}, "next.other"),
        ({"next": {"paths": {"docs": "docs/**"}}}, "next.paths.docs"),
        ({"tracker": {**tracker, "next_label": "ariane"}}, "tracker.next_label"),
    ):
        with pytest.raises(config.ConfigError, match=key):
            config.parse({**base, **bad})


def test_c23_next_command_prints_the_reasons_and_one_last_line(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from ariane import cli

    tracker = InMemoryTracker()
    queued(tracker, 4, "Needs #2", at(0), "ariane")
    queued(tracker, 5, "", at(1), "ariane")
    monkeypatch.chdir(project.root)
    monkeypatch.setenv("GH_TOKEN", "token-for-next")
    monkeypatch.setattr(config, "load", lambda root: make_config())
    monkeypatch.setattr(cli, "GitHubTracker", lambda **kwargs: tracker)
    assert cli.main(["next"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Running: none.",
        "- #4: waits on #2",
        "- #5: can start",
        "Next: #5 (nothing runs). Start it with ariane next --start.",
    ]
    tracker.closed[5] = "completed"
    monkeypatch.setenv("GH_TOKEN", "token-for-next")
    assert cli.main(["next", "--start"]) == 1
    last = capsys.readouterr().out.splitlines()[-1]
    assert last.startswith(
        "Did not start: the proposal changed since it was printed (was #5 (nothing runs), now"
        " nothing)."
    )
