"""`ariane start <n> --resume`: a ticket stopped by its implementer's budget, turn or time limit,
or by a runtime's quota, continues from the work its previous run saved (C5, C23, ADR 0062)."""

from __future__ import annotations

import dataclasses
import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ariane import config, flow, resume
from ariane.config import Config
from ariane.runtime import Session, SessionResult, StopReason, reset_moment
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, make_config, sh
from test_flow import environ, worktree

RESUME_BLOCK = re.compile(r'<untrusted-ticket kind="resume">\n(.*?)</untrusted-ticket>', re.DOTALL)


def kept_branches(project: Project) -> list[str]:
    listing = sh(["git", "branch", "--list", "--format=%(refname:short)", "ariane-*"], project.root)
    return listing.split()


def partial_work(session: Session) -> None:
    """An implementer that wrote part of the work when its limit stopped it."""
    (session.cwd / "partial.txt").write_text("half done\n", encoding="utf-8")


def finish_work(session: Session) -> None:
    """The resumed implementer: the previous attempt's file is there; it finishes the ticket."""
    assert (session.cwd / "partial.txt").read_text(encoding="utf-8") == "half done\n"
    (session.cwd / "app.txt").write_text("version 2\n", encoding="utf-8")


@dataclass
class Scripted(FakeRuntime):
    """`FakeRuntime` whose implementer sessions stop with `reasons` in turn, then finish; the
    reviewer's first sessions return `reviews` in turn, then answer as `FakeRuntime`."""

    reasons: list[StopReason] = field(default_factory=list)
    reviews: list[SessionResult] = field(default_factory=list)

    def run(self, session: Session) -> SessionResult:
        if session.role == "reviewer" and self.reviews:
            self.sessions.append(session)
            return self.reviews.pop(0)
        if session.role != "reviewer":
            self.stop_reason = self.reasons.pop(0) if self.reasons else StopReason.FINISHED
        return super().run(session)


def start(
    project: Project,
    tracker: InMemoryTracker,
    runtime: FakeRuntime,
    cfg: Config | None = None,
    **flags: bool,
) -> flow.Outcome:
    return flow.start(
        7,
        repo_root=project.root,
        config=cfg or make_config(),
        tracker=tracker,
        runtime=runtime,
        environ=environ(),
        **flags,
    )


def implementers(runtime: FakeRuntime) -> list[Session]:
    return [s for s in runtime.sessions if s.role == "implementer"]


def metrics_of(project: Project) -> dict[str, object]:
    data = json.loads(sh(["git", "show", "ariane/7:work/7/metrics.json"], project.root))
    assert isinstance(data, dict)
    return data


def stopped_on(
    project: Project, tracker: InMemoryTracker, reason: StopReason, cfg: Config | None = None
) -> flow.Outcome:
    """A first run whose implementer wrote `partial.txt`, then stopped on `reason`."""
    stopped = start(project, tracker, Scripted(action=partial_work, reasons=[reason]), cfg)
    assert stopped.exit_code == 1, stopped.line
    return stopped


def test_c5_resume_after_a_timeout_continues_from_the_kept_head_with_twice_the_time(
    project: Project, tracker: InMemoryTracker
) -> None:
    stopped_on(project, tracker, StopReason.TIMEOUT)
    previous = sh(["git", "rev-parse", "ariane/7"], project.root)
    left = worktree(project) / "notes.txt"  # left uncommitted: the restart saves it
    left.write_text("uncommitted note\n", encoding="utf-8")

    runtime = Scripted(action=finish_work)
    done = start(project, tracker, runtime, resuming=True)
    assert done.exit_code == 0, done.line
    [session] = implementers(runtime)
    assert session.timeout_s == 2 * 60  # `timeout_minutes` 1, doubled for this session
    assert session.max_budget_usd == 1.0  # the other limit stays
    [kept] = kept_branches(project)
    kept_head = sh(["git", "rev-parse", kept], project.root)
    assert sh(["git", "rev-parse", f"{kept_head}^"], project.root) == previous  # the saved work
    is_ancestor = ["git", "merge-base", "--is-ancestor", kept_head, "ariane/7"]
    assert subprocess.run(is_ancestor, cwd=project.root, check=False).returncode == 0
    assert project.show("ariane/7", "partial.txt") == "half done"
    assert project.show("ariane/7", "notes.txt") == "uncommitted note"
    data = metrics_of(project)
    assert data["restarted_from"] == {
        "branch": kept,
        "stopped_at": data["restarted_from"]["stopped_at"],  # type: ignore[index]
        "resumed": True,
    }
    journal = project.show("ariane/7", "work/7/journal.md")
    assert journal.count("# Journal of ticket #7") == 1  # the records started a new run
    assert "Ticket resumed" in journal
    assert "Raised `timeout_minutes` from 1 to 2 min." in journal


@pytest.mark.parametrize(("cap", "raised"), [(None, 2.0), (1.5, 1.5)])
def test_c5_resume_after_a_budget_stop_doubles_the_budget_and_a_cap_lowers_it(
    project: Project, tracker: InMemoryTracker, cap: float | None, raised: float
) -> None:
    base = make_config()
    cfg = dataclasses.replace(
        base, implementer=dataclasses.replace(base.implementer, max_budget_usd_cap=cap)
    )
    stopped_on(project, tracker, StopReason.BUDGET, cfg)
    runtime = Scripted(action=finish_work)
    done = start(project, tracker, runtime, cfg, resuming=True)
    assert done.exit_code == 0, done.line
    [session] = implementers(runtime)
    assert session.max_budget_usd == raised
    assert session.timeout_s == 60  # the time limit stays
    journal = project.show("ariane/7", "work/7/journal.md")
    assert f"Raised `max_budget_usd` from 1 to {raised:g} USD." in journal


def test_c5_resume_the_prompt_names_the_stop_and_the_changed_files_as_untrusted_data(
    project: Project, tracker: InMemoryTracker
) -> None:
    stopped_on(project, tracker, StopReason.TIMEOUT)
    runtime = Scripted(action=finish_work)
    assert start(project, tracker, runtime, resuming=True).exit_code == 0
    [session] = implementers(runtime)
    found = RESUME_BLOCK.search(session.prompt)
    assert found is not None, session.prompt
    data = found[1]
    assert "Previous session: implementer, stopped: timeout." in data
    assert "- partial.txt" in data
    assert "Implementer session stopped: timeout" in data  # its last journal entries
    assert "Context given to the agent" not in data  # a session's prompt is left out
    assert "continues an interrupted attempt" in session.prompt
    assert session.prompt.index("continues an interrupted attempt") < found.start()


def failing_check(session: Session) -> None:
    (session.cwd / "app.txt").write_text("version 3\n", encoding="utf-8")


def new_branch(session: Session) -> None:
    partial_work(session)
    subprocess.run(["git", "branch", "stray"], cwd=session.cwd, check=True)


def invalid_review() -> FakeRuntime:
    return FakeRuntime(answers=["not an answer"])


@pytest.mark.parametrize(
    ("runtime", "why"),
    [
        (FakeRuntime(action=failing_check), "blocking checks failed"),
        (invalid_review(), "the reviewer's answer was invalid twice"),
        (
            Scripted(action=new_branch, reasons=[StopReason.TIMEOUT]),
            "changed git configuration, hooks or local branches",
        ),
    ],
    ids=["check failure", "review hand-over", "guard stop after a timeout"],
)
def test_c5_resume_refuses_any_other_stop_and_names_restart(
    project: Project, tracker: InMemoryTracker, runtime: FakeRuntime, why: str
) -> None:
    stopped = start(project, tracker, runtime)
    assert stopped.exit_code == 1 and why in stopped.line, stopped.line
    assert "--resume" not in stopped.line
    head = sh(["git", "rev-parse", "ariane/7"], project.root)

    refused = start(project, tracker, FakeRuntime(), resuming=True)
    assert refused.exit_code == 1
    assert "Did not start ticket #7" in refused.line
    assert "did not stop on its implementer's budget, turn or time limit" in refused.line
    assert "Next: run `ariane start 7 --restart`." in refused.line
    assert sh(["git", "rev-parse", "ariane/7"], project.root) == head  # nothing was cleared
    assert kept_branches(project) == []


def test_c5_resume_a_second_limit_stop_after_a_resume_refuses_another(
    project: Project, tracker: InMemoryTracker
) -> None:
    stopped_on(project, tracker, StopReason.TIMEOUT)
    again = start(
        project, tracker, Scripted(action=finish_work, reasons=[StopReason.TIMEOUT]), resuming=True
    )
    assert again.exit_code == 1
    assert "--resume" not in again.line  # only `--restart`, or a hand takeover
    assert "`ariane start 7 --restart`" in again.line

    refused = start(project, tracker, FakeRuntime(), resuming=True)
    assert refused.exit_code == 1
    assert "was resumed already and stopped on a limit again (timeout)" in refused.line
    assert "`ariane start 7 --restart`" in refused.line and "ariane verify" in refused.line
    assert len(kept_branches(project)) == 1


@pytest.mark.parametrize("reason", [StopReason.TIMEOUT, StopReason.BUDGET, StopReason.TURNS])
def test_c5_resume_the_stop_line_of_a_limit_stop_names_resume(
    project: Project, tracker: InMemoryTracker, reason: StopReason
) -> None:
    stopped = stopped_on(project, tracker, reason)
    assert f"the implementer session stopped: {reason.value}" in stopped.line
    assert (
        "to continue from its saved work, run `ariane start 7 --resume`"
        " (or `ariane start 7 --restart`)." in stopped.line
    )


def quota(reset_at: str | None) -> SessionResult:
    result = SessionResult.failed(StopReason.QUOTA, "usage limit reached")
    return dataclasses.replace(result, next_step="wait for the quota to reset", reset_at=reset_at)


def test_c5_resume_after_a_reviewer_quota_reviews_the_kept_head_without_an_implementer(
    project: Project, tracker: InMemoryTracker
) -> None:
    past = (datetime.now(UTC) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stopped = start(project, tracker, Scripted(reviews=[quota(past)]))
    assert stopped.exit_code == 1 and "reviewer quota reached" in stopped.line
    assert "`ariane start 7 --resume`" in stopped.line
    assert metrics_of(project)["sessions"][-1]["reset_at"] == past  # type: ignore[index]
    delivered_work = project_head_file(project)

    runtime = Scripted()
    done = start(project, tracker, runtime, resuming=True)
    assert done.exit_code == 0, done.line
    assert implementers(runtime) == []
    [review] = [s for s in runtime.sessions if s.role == "reviewer"]
    assert review.max_budget_usd == 1.0 and review.timeout_s == 60  # no limit raised
    assert project.show("ariane/7", "app.txt") == delivered_work
    journal = project.show("ariane/7", "work/7/journal.md")
    assert "No implementer session" in journal
    assert "No limit raised: the reviewer stopped on its runtime's quota." in journal
    assert "Checks replayed by Ariane" in journal
    assert "Implementer session started" not in journal


def project_head_file(project: Project) -> str:
    return sh(["git", "show", "ariane/7:app.txt"], project.root)


def test_c5_resume_is_refused_before_the_reset_time_the_runtime_gave(
    project: Project, tracker: InMemoryTracker
) -> None:
    later = (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    start(project, tracker, Scripted(reviews=[quota(later)]))
    refused = start(project, tracker, FakeRuntime(), resuming=True)
    assert refused.exit_code == 1
    assert f"the quota of the reviewer's runtime resets at {later}" in refused.line
    assert f"Next: run `ariane start 7 --resume` after {later}." in refused.line
    assert kept_branches(project) == []


def test_c5_resume_without_a_previous_branch_is_refused(
    project: Project, tracker: InMemoryTracker
) -> None:
    refused = start(project, tracker, FakeRuntime(), resuming=True)
    assert refused.exit_code == 1
    assert "has no branch ariane/7 to resume" in refused.line


def test_c5_resume_reset_times_of_a_runtime_are_read_as_utc() -> None:
    now = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
    assert reset_moment("2 hours 5 minutes", now) == "2026-10-23T14:05:00Z"
    assert reset_moment("2026-10-24T08:00:00+02:00", now) == "2026-10-24T06:00:00Z"
    clock = reset_moment("3:45 PM", now)
    assert clock is not None
    moment = datetime.fromisoformat(clock.replace("Z", "+00:00"))
    assert timedelta(0) < moment - now <= timedelta(days=1)
    assert moment.astimezone().strftime("%H:%M") == "15:45"
    assert reset_moment("later", now) is None
    assert reset_moment("13:61", now) is None


def test_c5_resume_settings_are_validated(tmp_path: Path) -> None:
    del tmp_path
    base = make_config().implementer
    assert (base.resume_factor, base.max_budget_usd_cap, base.timeout_minutes_cap) == (
        2,
        None,
        None,
    )
    raised, text = resume.raised(dataclasses.replace(base, timeout_minutes_cap=1.5), "timeout")
    assert raised.timeout_minutes == 1.5 and "from 1 to 1.5 min" in text
    data = valid_data()
    data["agents"]["implementer"] |= {"resume_factor": 3, "timeout_minutes_cap": 90}
    parsed = config.parse(data).implementer
    assert (parsed.resume_factor, parsed.timeout_minutes_cap) == (3.0, 90.0)
    for key, value, message in (
        ("resume_factor", 0.5, "resume_factor: must be at least 1"),
        ("max_budget_usd_cap", 1, "max_budget_usd_cap: must be at least 5"),
        ("timeout_minutes_cap", 10, "timeout_minutes_cap: must be at least 30"),
    ):
        data = valid_data()
        data["agents"]["implementer"][key] = value
        with pytest.raises(config.ConfigError, match=re.escape(message)):
            config.parse(data)
    data = valid_data()
    data["agents"]["reviewer"]["resume_factor"] = 2
    with pytest.raises(config.ConfigError, match=r"agents\.reviewer"):
        config.parse(data)


def valid_data() -> dict[str, dict[str, dict[str, object]]]:
    from test_config import VALID

    return json.loads(json.dumps(VALID))  # type: ignore[no-any-return]
