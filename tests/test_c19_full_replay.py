"""C9, C19: a sampled full replay after delivery catches what selective checks missed, records
the escapes, publishes them, and `ariane report` shows the time saved and the escape rate
(ADR 0056)."""

from __future__ import annotations

import copy
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from test_config import VALID

from ariane import flow, full_replay, git, report, risk
from ariane.config import CheckConfig, ChecksPolicy, Config, ConfigError, parse
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, make_config, sh
from test_flow import TOKEN, journal, start, worktree

PY = sys.executable
PASS = (PY, "-c", "print('ran')")
# Passes on a related-tests run and fails on the full suite, printing a secret it must not show.
FULL_FAILS = (
    PY,
    "-c",
    f"import os, sys; print('full suite broke {TOKEN}');"
    " sys.exit(os.environ['ARIANE_FULL_SUITE'] == '1')",
)


def config(sample: float, *checks: CheckConfig, policy: bool = True) -> Config:
    cfg = make_config(checks=checks or (CheckConfig("app", PASS, True, 1),))
    return dataclasses.replace(
        cfg, checks_policy=ChecksPolicy(full_replay_sample=sample) if policy else None
    )


def skipped_docs() -> CheckConfig:
    """Covers `docs/` only: the fake implementer changes `app.txt`, so the round skips it."""
    return CheckConfig("docs", PASS, True, 1, paths=("docs/**",))


def metrics(project: Project) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (worktree(project) / "work/7/metrics.json").read_text(encoding="utf-8")
    )
    return data


def statuses(tracker: InMemoryTracker, context: str) -> list[dict[str, str]]:
    return [s for s in tracker.statuses if s["context"] == context]


def test_c19_full_replay_runs_after_delivery_when_a_check_was_skipped(
    project: Project, tracker: InMemoryTracker
) -> None:
    cfg = config(1.0, CheckConfig("app", PASS, True, 1, full_when="always"), skipped_docs())
    assert start(project, tracker, FakeRuntime(), cfg).exit_code == 0
    log = journal(project)
    assert "Checks skipped" in log
    assert (
        log.index("Delivered") < log.index("Full replay started") < log.index("Full replay passed")
    )
    record = (worktree(project) / "work/7/full-replay.md").read_text(encoding="utf-8")
    assert "| docs | skipped | pass | no |" in record
    assert "| app | ran in full | pass | no |" in record
    assert "Escapes: 0." in record
    [status] = statuses(tracker, "ariane/full-replay")
    assert (status["state"], status["description"]) == ("success", "full replay passed")
    assert tracker.comments == {}
    done = metrics(project)
    assert done["full_replay"]["ran"] is True and done["full_replay"]["escapes"] == []
    assert done["replays"] == [
        {
            "round": 0,
            "selected": ["app"],
            "skipped": ["docs"],
            "partial": [],
            "duration_s": done["replays"][0]["duration_s"],
        }
    ]
    assert done["outcome"] == "delivered"


def test_c19_full_replay_sample_zero_or_nothing_selective_runs_none(
    project: Project, tracker: InMemoryTracker
) -> None:
    cfg = config(0.0, CheckConfig("app", PASS, True, 1), skipped_docs())
    assert start(project, tracker, FakeRuntime(), cfg).exit_code == 0
    assert "Full replay not sampled" in journal(project)
    assert "Full replay started" not in journal(project)
    assert not (worktree(project) / "work/7/full-replay.md").exists()
    assert statuses(tracker, "ariane/full-replay") == []
    assert metrics(project)["full_replay"] == {"ran": False, "duration_s": 0.0, "escapes": []}


def test_c19_full_replay_not_considered_without_a_skipped_or_partial_check(
    project: Project, tracker: InMemoryTracker
) -> None:
    """Without `[checks_policy]` every round is high: no check runs partly, none is skipped."""
    cfg = config(1.0, CheckConfig("app", PASS, True, 1), policy=False)
    assert start(project, tracker, FakeRuntime(), cfg).exit_code == 0
    assert "Full replay" not in journal(project)
    assert "full_replay" not in metrics(project)
    assert metrics(project)["replays"][0]["skipped"] == []
    assert statuses(tracker, "ariane/full-replay") == []


def test_c19_full_replay_sampling_is_deterministic_for_a_ticket_and_commit() -> None:
    commits = [f"{k:040x}" for k in range(400)]
    draws = [full_replay.sampled(7, c, 0.2) for c in commits]
    assert draws == [full_replay.sampled(7, c, 0.2) for c in commits]
    assert 40 < sum(draws) < 120  # about a fifth of the commits
    assert [full_replay.sampled(8, c, 0.2) for c in commits] != draws  # the ticket counts too
    assert all(full_replay.sampled(7, c, 1.0) for c in commits)
    assert not any(full_replay.sampled(7, c, 0.0) for c in commits)


def test_c19_full_replay_an_escape_is_recorded_journaled_commented_and_a_failing_status(
    project: Project, tracker: InMemoryTracker
) -> None:
    """The low round runs `related` with ARIANE_FULL_SUITE=0, where it passes; the full suite
    fails it: an escape."""
    cfg = config(1.0, CheckConfig("related", FULL_FAILS, True, 1))
    assert start(project, tracker, FakeRuntime(), cfg).exit_code == 0
    log = journal(project)
    assert "Escape: related" in log
    assert "- related (partial): exit 1" in log
    record = (worktree(project) / "work/7/full-replay.md").read_text(encoding="utf-8")
    assert "| related | partial | **fail** (exit 1) | yes |" in record
    assert "## related (escape)" in record
    assert "full suite broke" in record and TOKEN not in record
    [status] = statuses(tracker, "ariane/full-replay")
    assert status["state"] == "failure"
    assert status["description"] == "escape: related failed only in the full replay"
    [comment] = tracker.comments[1001]
    assert "`related` (partial): exit 1" in comment and TOKEN not in comment
    done = metrics(project)
    assert done["replays"][0]["partial"] == ["related"]
    assert done["full_replay"]["escapes"] == ["related"]
    assert done["full_replay"]["duration_s"] > 0


def test_c19_full_replay_never_changes_the_pushed_commit_or_the_review_result(
    project: Project, tracker: InMemoryTracker
) -> None:
    cfg = config(1.0, CheckConfig("related", FULL_FAILS, True, 1))
    outcome = start(project, tracker, FakeRuntime(), cfg)
    assert outcome.exit_code == 0
    assert "checks replayed green, review go" in outcome.line
    pushed = project.remote_branches()["ariane/7"]
    assert {s["sha"] for s in tracker.statuses} == {pushed}  # every status on the pushed commit
    [opened] = tracker.opened
    assert opened["draft"] is False and "escape" not in opened["body"].lower()
    assert metrics(project)["first_pass_verdict"] == "go"
    assert metrics(project)["outcome"] == "delivered"
    tree = worktree(project)
    # The full replay's record is a local commit on top of the pushed one, never pushed.
    assert sh(["git", "log", "-1", "--format=%s"], tree).strip() == "#7: record the full replay"
    assert sh(["git", "merge-base", "--is-ancestor", pushed, "HEAD"], tree) == ""
    assert "work/7/full-replay.md" in sh(["git", "show", "--name-only", "HEAD"], tree)


def test_c19_full_replay_a_later_stop_keeps_an_escape_already_seen(
    project: Project, tracker: InMemoryTracker
) -> None:
    """Both skipped in the round: `a` fails the full suite, then `b`'s setup stops the full
    replay. `a`'s failure is still an escape, recorded, journaled and published."""
    cfg = config(
        1.0,
        CheckConfig("app", PASS, True, 1, full_when="always"),
        CheckConfig("a", FULL_FAILS, True, 1, paths=("docs/**",)),
        CheckConfig("b", PASS, True, 1, setup=(PY, "-c", "raise SystemExit(3)"), paths=("x/**",)),
    )
    outcome = start(project, tracker, FakeRuntime(), cfg)
    assert outcome.exit_code == 0 and "review go" in outcome.line
    log = journal(project)
    assert "Escape: a" in log and "- a (skipped): exit 1" in log
    assert log.index("Escape: a") < log.index("Full replay stopped")
    record = (worktree(project) / "work/7/full-replay.md").read_text(encoding="utf-8")
    assert "| a | skipped | **fail** (exit 1) | yes |" in record
    assert "## a (escape)" in record and "full suite broke" in record and TOKEN not in record
    assert "## Stopped" in record and "| b |" not in record
    [status] = statuses(tracker, "ariane/full-replay")
    assert status["state"] == "failure"
    [comment] = tracker.comments[1001]
    assert "`a` (skipped): exit 1" in comment
    done = metrics(project)
    assert done["full_replay"]["escapes"] == ["a"] and done["full_replay"]["stopped"]
    assert done["outcome"] == "delivered"


def test_c19_full_replay_a_stop_without_an_escape_publishes_no_status(
    project: Project, tracker: InMemoryTracker
) -> None:
    cfg = config(
        1.0,
        CheckConfig("app", PASS, True, 1, full_when="always"),
        CheckConfig("b", PASS, True, 1, setup=(PY, "-c", "raise SystemExit(3)"), paths=("x/**",)),
    )
    assert start(project, tracker, FakeRuntime(), cfg).exit_code == 0
    assert "Full replay stopped" in journal(project) and "Escape" not in journal(project)
    assert statuses(tracker, "ariane/full-replay") == []
    assert metrics(project)["full_replay"]["escapes"] == []


def test_c19_full_replay_its_status_name_is_no_check_name() -> None:
    """A check is published as `ariane/<name>`: one named `full-replay` would share the full
    replay's status, whose success could hide the check's failure."""
    data = copy.deepcopy(VALID)
    data["checks"] = [{"name": "full-replay", "command": ["x"]}]
    with pytest.raises(ConfigError, match=r"checks\[0\]\.name: 'full-replay' is reserved"):
        parse(data)
    assert full_replay.STATUS == "ariane/full-replay"


def test_c19_full_replay_a_refused_comment_is_a_warning(
    project: Project, tracker: InMemoryTracker
) -> None:
    tracker.refuse_comments = True
    cfg = config(1.0, CheckConfig("related", FULL_FAILS, True, 1))
    assert start(project, tracker, FakeRuntime(), cfg).exit_code == 0
    assert "Warning: comment refused\n\ncomments are refused" in journal(project)
    assert statuses(tracker, "ariane/full-replay")[0]["state"] == "failure"


def test_c19_full_replay_interrupted_while_publishing_keeps_the_delivered_outcome(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupt(self: InMemoryTracker, *args: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(InMemoryTracker, "comment", interrupt)
    cfg = config(1.0, CheckConfig("related", FULL_FAILS, True, 1))
    outcome = start(project, tracker, FakeRuntime(), cfg)
    assert outcome.exit_code == 0 and "review go" in outcome.line
    assert "Full replay stopped: interrupted by the user" in journal(project)
    status = (worktree(project) / "work/7/status.md").read_text(encoding="utf-8")
    assert "- Last action: delivered" in status
    done = metrics(project)
    assert done["outcome"] == "delivered" and done["full_replay"]["escapes"] == ["related"]
    tree = worktree(project)
    assert sh(["git", "log", "-1", "--format=%s"], tree).strip() == "#7: record the full replay"


def test_c19_full_replay_a_failed_final_commit_keeps_the_delivered_outcome(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    commit = flow._TicketRun._commit_record

    def refuse(self: flow._TicketRun, message: str) -> None:
        if message.endswith("record the full replay"):
            raise git.GitError("commit refused")
        commit(self, message)

    monkeypatch.setattr(flow._TicketRun, "_commit_record", refuse)
    cfg = config(1.0, CheckConfig("app", PASS, True, 1, full_when="always"), skipped_docs())
    outcome = start(project, tracker, FakeRuntime(), cfg)
    assert outcome.exit_code == 0 and "review go" in outcome.line
    assert "Full replay stopped: commit refused" in journal(project)
    status = (worktree(project) / "work/7/status.md").read_text(encoding="utf-8")
    assert "- Last action: delivered" in status
    assert statuses(tracker, "ariane/full-replay")[0]["state"] == "success"


def test_c19_full_replay_report_from_the_main_checkout_after_a_sampled_delivery(
    project: Project, tracker: InMemoryTracker
) -> None:
    """The full replay is committed in the ticket worktree only, after the push: the report
    reads it there, in place of the merged record of the same run."""
    cfg = config(1.0, CheckConfig("related", FULL_FAILS, True, 1))
    assert start(project, tracker, FakeRuntime(), cfg).exit_code == 0
    pushed = project.remote_branches()["ariane/7"]
    sh(["git", "fetch", "origin", "ariane/7"], project.root)
    sh(["git", "merge", "--ff-only", pushed], project.root)  # the pull request is merged
    assert "full_replay" not in project.show(pushed, "work/7/metrics.json")
    lines = report.build(project.root, None, None, 0.02).lines
    assert len([x for x in lines if x.startswith("#7 ")]) == 1
    [line] = [x for x in lines if x.startswith("Selective checks:")]
    assert "1 full replays, 1 escapes, escape rate 1/1 (100.0%)" in line
    assert any(x.startswith("Warning: the escape rate 100.0%") for x in lines)


def test_c19_full_replay_report_names_a_malformed_full_replay(tmp_path: Path) -> None:
    put(tmp_path, 1, [selective_round(10)], {"ran": True, "duration_s": 4, "escapes": 1})
    put(tmp_path, 2, [selective_round(10)], {"ran": True, "duration_s": 4, "escapes": ["t"]})
    result = report.build(tmp_path, None)
    assert result.exit_code == 1
    assert (
        "Could not read work/1/metrics.json: full_replay.escapes is not a list of check names;"
        " skipped." in result.lines
    )
    assert any("1 full replays, 1 escapes" in x for x in result.lines)


def put(root: Path, number: int, rounds: list[dict[str, Any]], full: Any = None) -> None:
    data: dict[str, Any] = {
        "ticket": number,
        "mode": "delivered",
        "started": "2026-10-20T10:00:00",
        "sessions": [],
        "rounds": 0,
        "first_pass_verdict": "go",
        "outcome": "delivered",
        "replays": rounds,
    }
    if full is not None:
        data["full_replay"] = full
    path = root / "work" / str(number) / "metrics.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def selective_round(seconds: float, skipped: list[str] = ["docs"]) -> dict[str, Any]:  # noqa: B006
    return {"round": 0, "selected": [], "skipped": skipped, "partial": [], "duration_s": seconds}


@pytest.mark.parametrize(("rate", "warned"), [(0.02, True), (0.5, False)])
def test_c19_full_replay_report_shows_time_saved_escapes_and_rate(
    tmp_path: Path, rate: float, warned: bool
) -> None:
    put(tmp_path, 1, [selective_round(10)], {"ran": True, "duration_s": 40, "escapes": ["t"]})
    put(tmp_path, 2, [selective_round(20)], {"ran": True, "duration_s": 50, "escapes": []})
    put(tmp_path, 3, [selective_round(5)], {"ran": False, "duration_s": 0, "escapes": []})
    put(tmp_path, 4, [selective_round(60, skipped=[])])  # every check ran fully
    put(tmp_path, 5, [selective_round(9)], {"ran": True, "stopped": "x", "escapes": ["t"]})
    lines = report.build(tmp_path, None, None, rate).lines
    [line] = [x for x in lines if x.startswith("Selective checks:")]
    assert line == (
        "Selective checks: 4 tickets with selection, replay time 44.0 s; on the 2 sampled"
        " tickets 30.0 s selective versus 90.0 s full (60.0 s saved); 2 full replays,"
        " 1 escapes, escape rate 1/2 (50.0%)."
    )
    warning = [x for x in lines if x.startswith("Warning: the escape rate")]
    assert bool(warning) is warned
    if warned:
        assert "50.0% is above max_escape_rate 2%" in warning[0]


def test_c19_full_replay_report_without_selection_has_no_section(tmp_path: Path) -> None:
    put(tmp_path, 1, [selective_round(60, skipped=[])])
    assert not any(x.startswith("Selective checks") for x in report.build(tmp_path, None).lines)


def test_c19_full_replay_policy_keys_are_fractions() -> None:
    policy = risk.parse({"full_replay_sample": 1, "max_escape_rate": 0})
    assert policy is not None
    assert (policy.full_replay_sample, policy.max_escape_rate) == (1.0, 0.0)
    assert risk.parse({}) == ChecksPolicy(full_replay_sample=0.2, max_escape_rate=0.02)
    for bad in (1.5, -0.1, True, "0.2"):
        with pytest.raises(risk.PolicyError, match="full_replay_sample: expected a number"):
            risk.parse({"full_replay_sample": bad})
