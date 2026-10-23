"""`ariane next`: the queue, its dependencies, the files each ticket is expected to touch, the run
slots and the last run decide the proposal; `--start` starts it on confirmation (C11, C22, C23,
ADR 0060)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from ariane import config, flow, next_ticket, runs, slots, ticket
from ariane.tracker import InMemoryTracker, QueuedIssue, TrackerError

from conftest import Project, commit_on_branch, make_config

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


def test_c23_next_a_module_not_created_yet_is_still_shared(project: Project) -> None:
    """A ticket that will add `scheduler` names only its module doc: its source, absent from the
    checkout, is the glob `src/*/scheduler.py`, which another issue naming the source shares."""
    adding = next_ticket.expected_paths(
        "Add `docs/architecture/modules/scheduler.md`.", (), project.root, config.NextConfig()
    )
    assert "src/*/scheduler.py" in adding
    naming = next_ticket.expected_paths(
        "Change `src/ariane/scheduler.py`.", (), project.root, config.NextConfig()
    )
    assert next_ticket.shared(adding, naming) == ["src/ariane/scheduler.py"]


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


@pytest.mark.parametrize(
    "body",
    [
        "Edit [src/pkg/cli.py](src/pkg/cli.py).",
        "Edit [the command line](src/pkg/cli.py).",
        "Edit `src/pkg/cli.py:65`.",
        "Edit src/pkg/cli.py#L3-L9 and src/pkg/cli.py:12:4.",
        "Edit `src/pkg/./cli.py`.",
        "Edit ./src//pkg/../pkg/cli.py.",
    ],
)
def test_c23_next_a_shared_file_named_in_any_notation_is_not_proposed(
    project: Project, body: str
) -> None:
    module_files(project)
    commit_on_branch(project.root, "ariane/12", "work", {"src/pkg/cli.py": "v2\n"}, parent="main")
    tracker = InMemoryTracker()
    queued(tracker, 12, "", at(0))
    queued(tracker, 13, body, at(1))
    assert "src/pkg/cli.py" in next_ticket.expected_paths(
        body, (), project.root, config.NextConfig()
    )
    with runs.registered(runs.folder(project.root), 12, "ariane/12"):
        proposal = next_ticket.propose(project.root, make_config(), tracker)
    assert reasons(proposal, 13) == ("shares src/pkg/cli.py with running #12",)
    assert proposal.number is None


def test_c23_next_paths_outside_the_repository_are_left_out(project: Project) -> None:
    body = "See ../other/a.py, /etc/a.conf, a/../../b.py and https://example.invalid/c.py:3."
    assert next_ticket.expected_paths(body, (), project.root, config.NextConfig()) == ()


def test_c23_next_overlapping_globs_share_their_known_files_or_the_globs(project: Project) -> None:
    assert next_ticket.shared(["docs/**"], ["docs/architecture/**"]) == [
        "docs/** and docs/architecture/**"
    ]
    known = ["docs/architecture/cli.md", "docs/x.md", "src/ariane/a.py", "src/b/c.py"]
    assert next_ticket.shared(["docs/**"], ["docs/architecture/**"], known) == [
        "docs/architecture/cli.md"
    ]
    assert next_ticket.shared(["src/**/*.py"], ["src/ariane/*.py"], known) == ["src/ariane/a.py"]
    many = [f"docs/architecture/{n}.md" for n in range(5)]
    assert next_ticket.shared(["docs/**"], ["docs/architecture/*.md"], many) == [
        "docs/** and docs/architecture/*.md (5 files)"
    ]
    assert next_ticket.shared(["docs/**", "*.md"], ["src/**", "docs/*/x.py"], known) == [
        "docs/** and docs/*/x.py"
    ]
    module_files(project)
    commit_on_branch(project.root, "ariane/12", "work", {"app.txt": "v2\n"}, parent="main")
    tracker = InMemoryTracker()
    queued(tracker, 12, "Rewrite `docs/architecture/`.", at(0))
    queued(tracker, 13, "Edit `docs/**/*.md`.", at(1))
    with runs.registered(runs.folder(project.root), 12, "ariane/12"):
        proposal = next_ticket.propose(project.root, make_config(), tracker)
    assert reasons(proposal, 13) == ("shares docs/architecture/modules/cli.md with running #12",)
    assert proposal.number is None


def unreadable(tracker: InMemoryTracker, number: int) -> QueuedIssue:
    raise TrackerError("HTTP 502")


def test_c23_next_a_running_ticket_whose_files_cannot_be_read_holds_every_issue(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracker = InMemoryTracker()
    queued(tracker, 12, "Edit `a.txt`.", at(0))
    queued(tracker, 13, "Edit `b.txt`.", at(1))
    where = runs.folder(project.root)
    with runs.registered(where, 12, "ariane/12"):  # registered, its branch not prepared yet
        proposal = next_ticket.propose(project.root, make_config(), tracker)
    why = "the files of running #12 are not known (its branch ariane/12 does not exist yet)"
    assert reasons(proposal, 13) == (why,)
    assert proposal.number is None
    assert proposal.last_line() == (
        f"Nothing to start: {why}. Next: wait for the running tickets to start their branches,"
        " then run ariane next."
    )
    commit_on_branch(project.root, "ariane/12", "work", {"app.txt": "v2\n"}, parent="main")
    cfg = dataclasses.replace(make_config(), base_branch="no-such-base")
    with runs.registered(where, 12, "ariane/12"):
        proposal = next_ticket.propose(project.root, cfg, tracker)
        assert proposal.number is None
        assert "git cannot read its changes" in reasons(proposal, 13)[0]
        tracker.labels[12] = ["ariane"]  # no longer queued: its issue is read from the tracker
        monkeypatch.setattr(InMemoryTracker, "peek_issue", unreadable)
        proposal = next_ticket.propose(project.root, make_config(), tracker)
    assert reasons(proposal, 13) == (
        "the files of running #12 are not known (its issue cannot be read: HTTP 502)",
    )
    monkeypatch.undo()
    assert next_ticket.propose(project.root, make_config(), tracker).number == 13


def test_c23_next_a_running_ticket_outside_the_queue_keeps_its_label_globs(
    project: Project,
) -> None:
    module_files(project)
    commit_on_branch(project.root, "ariane/12", "work", {"app.txt": "v2\n"}, parent="main")
    tracker = InMemoryTracker()
    tracker.add_issue(12, "Started by hand", "Rewrite the documentation.")
    tracker.labels[12] = ["ariane", "docs"]
    queued(tracker, 13, "Update `docs/architecture/modules/cli.md`.", at(1))
    settings = config.NextConfig(paths=(("docs", ("docs/**",)),))
    cfg = dataclasses.replace(make_config(), next=settings)
    with runs.registered(runs.folder(project.root), 12, "ariane/12"):
        proposal = next_ticket.propose(project.root, cfg, tracker)
    assert proposal.running == (12,)
    assert reasons(proposal, 13) == ("shares docs/architecture/modules/cli.md with running #12",)
    assert proposal.number is None


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
        "Next: once the quota resets, run ariane start 20 --resume."
    )


def test_c23_next_a_last_run_stopped_otherwise_does_not_block(project: Project) -> None:
    tracker = InMemoryTracker()
    queued(tracker, 4, "", at(0))
    stopped_run(project, 20, "error")
    assert next_ticket.last_quota_stop(project.root) is None
    assert next_ticket.propose(project.root, make_config(), tracker).number == 4


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
