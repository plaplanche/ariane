"""C11, C22: each run holds a machine-wide slot and gives it to the project as `ARIANE_SLOT`
(ADR 0050)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_verify import BRANCH
from test_verify import run as verify_run

from ariane import context, flow, git, shadow, slots
from ariane.config import CheckConfig
from ariane.runtime import Session
from ariane.tracker import InMemoryTracker

from conftest import MACHINE_SLOTS, PY, FakeRuntime, Project, commit_on_branch, make_config, sh
from test_flow import environ, journal, start, worktree

HOLDER = """
import contextlib, sys
from pathlib import Path
from ariane import slots
with contextlib.ExitStack() as stack:
    taken = [stack.enter_context(slots.held(Path(sys.argv[1]))) for _ in range(int(sys.argv[2]))]
    print(" ".join(map(str, taken)), flush=True)
    sys.stdin.read()
"""

PROBE = """
import json, os, sys
with open(sys.argv[1], "a", encoding="utf-8") as out:
    out.write(json.dumps({"who": sys.argv[2], "slot": os.environ.get("ARIANE_SLOT")}) + "\\n")
if sys.argv[2] == "check":
    sys.exit(0 if "2" in open("app.txt").read() else 1)
"""


@pytest.fixture
def hold(isolated_slots: Path) -> Iterator[Any]:
    """Make another process hold `count` slots until the test ends."""
    holders: list[subprocess.Popen[str]] = []

    def take(count: int) -> str:
        child = subprocess.Popen(
            [PY, "-c", HOLDER, str(isolated_slots), str(count)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        holders.append(child)
        assert child.stdout is not None
        return child.stdout.readline().strip()

    yield take
    for child in holders:
        assert child.stdin is not None
        child.stdin.close()
        child.wait(timeout=30)


def probe_config(out: Path):  # type: ignore[no-untyped-def]
    check = CheckConfig("probe", (PY, "-c", PROBE, str(out), "check"), True, 1.0)
    return make_config(setup=(PY, "-c", PROBE, str(out), "setup"), checks=(check,))


def seen(out: Path) -> list[dict[str, str]]:
    return [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]


def free_slot() -> int:
    """The slot a new run would take now (released at once)."""
    with slots.held() as k:
        return k


def test_c11_run_slot_is_given_to_the_setup_the_checks_the_agents_and_the_commits(
    project: Project, tracker: InMemoryTracker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commits: list[str | None] = []
    real_commit = git.commit

    def commit(*args: Any, **kwargs: Any) -> bool:
        commits.append(kwargs["env"].get("ARIANE_SLOT"))
        return real_commit(*args, **kwargs)

    monkeypatch.setattr(git, "commit", commit)
    monkeypatch.setenv("ARIANE_SLOT", "9")  # Ariane's own value is withheld, then replaced
    out = tmp_path / "seen.jsonl"
    runtime = FakeRuntime()
    outcome = start(project, tracker, runtime, probe_config(out))
    assert outcome.exit_code == 0, outcome.line
    assert {(r["who"], r["slot"]) for r in seen(out)} == {("setup", "0"), ("check", "0")}
    assert [s.role for s in runtime.sessions] == ["implementer", "reviewer"]
    assert [s.env["ARIANE_SLOT"] for s in runtime.sessions] == ["0", "0"]
    assert commits and set(commits) == {"0"}
    assert "slot 0 (`ARIANE_SLOT`)" in journal(project)


def test_c11_run_slot_negative_control_without_a_slot_nothing_is_set(
    project: Project, tracker: InMemoryTracker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = context.untrusted_environment
    monkeypatch.setattr(
        context,
        "untrusted_environment",
        lambda *a, **k: real(*a, **{**k, "slot": None}),
    )
    out = tmp_path / "seen.jsonl"
    start(project, tracker, FakeRuntime(), probe_config(out))
    assert {r["slot"] for r in seen(out)} == {None}


def test_c11_run_slot_takes_the_next_slot_when_another_process_holds_slot_0(
    project: Project, tracker: InMemoryTracker, tmp_path: Path, hold: Any
) -> None:
    assert hold(1) == "0"
    out = tmp_path / "seen.jsonl"
    runtime = FakeRuntime()
    outcome = start(project, tracker, runtime, probe_config(out))
    assert outcome.exit_code == 0, outcome.line
    assert {r["slot"] for r in seen(out)} == {"1"}
    assert runtime.sessions[0].env["ARIANE_SLOT"] == "1"
    assert "slot 1 (`ARIANE_SLOT`)" in journal(project)


def test_c11_run_slot_all_16_held_refuses_start_before_any_branch_or_tree(
    project: Project, tracker: InMemoryTracker, hold: Any
) -> None:
    assert hold(16) == " ".join(str(k) for k in range(16))
    runtime = FakeRuntime()
    outcome = start(project, tracker, runtime)
    assert outcome.exit_code == flow.EXIT_STOPPED
    assert outcome.line == (
        "Did not start ticket #7: 16 Ariane runs already hold a slot on this machine."
        " Next: wait for one to end."
    )
    assert not worktree(project).exists()
    assert not git.local_branch_exists(project.root, flow.branch_name(7))
    assert runtime.sessions == []


def test_c11_run_slot_all_16_held_refuses_shadow_and_verify(
    project: Project, tracker: InMemoryTracker, hold: Any
) -> None:
    hold(16)
    outcome = shadow.start(
        7,
        repo_root=project.root,
        config=make_config(),
        tracker=tracker,
        runtime=FakeRuntime(),
        environ=environ(),
    )
    assert outcome.line.startswith("Did not start shadow ticket #7: 16 Ariane runs already hold")
    assert not shadow.clone_path(project.root, 7).exists()
    commit_on_branch(project.root, BRANCH, "By hand", {"app.txt": "version 2\n"}, parent="main")
    outcome = verify_run(project, FakeRuntime())
    assert outcome.exit_code == flow.EXIT_STOPPED
    assert outcome.line == (
        f"Did not verify {BRANCH}: 16 Ariane runs already hold a slot on this machine."
        " Next: wait for one to end."
    )


def test_c11_run_slot_verify_gives_and_records_its_slot(project: Project, hold: Any) -> None:
    hold(2)
    commit_on_branch(project.root, BRANCH, "By hand", {"app.txt": "version 2\n"}, parent="main")
    runtime = FakeRuntime()
    outcome = verify_run(project, runtime)
    assert outcome.exit_code == 0, outcome.line
    assert [s.env["ARIANE_SLOT"] for s in runtime.sessions] == ["2"]
    shown = sh(["git", "show", f"{BRANCH}:work/verify/{BRANCH}/review.md"], project.root)
    assert "Slot 2 (`ARIANE_SLOT=2`" in shown
    assert free_slot() == 2  # released; 0 and 1 are still the other process's


def test_c11_run_slot_is_held_during_the_run_and_released_at_its_end(
    project: Project, tracker: InMemoryTracker
) -> None:
    during: list[int] = []

    def edit(session: Session) -> None:
        during.append(free_slot())
        (session.cwd / "app.txt").write_text("version 2\n", encoding="utf-8")

    outcome = start(project, tracker, FakeRuntime(action=edit))
    assert outcome.exit_code == 0, outcome.line
    assert during == [1]
    assert free_slot() == 0


def test_c11_run_slot_is_released_after_a_stop(project: Project, tracker: InMemoryTracker) -> None:
    def nothing(session: Session) -> None:
        return None

    outcome = start(project, tracker, FakeRuntime(action=nothing))
    assert outcome.exit_code == flow.EXIT_STOPPED
    assert "the agent changed no file" in outcome.line
    assert free_slot() == 0


def test_c11_run_slot_is_released_after_ctrl_c(project: Project, tracker: InMemoryTracker) -> None:
    def interrupt(session: Session) -> None:
        raise KeyboardInterrupt

    outcome = start(project, tracker, FakeRuntime(action=interrupt))
    assert outcome.exit_code == flow.EXIT_INTERRUPTED
    assert free_slot() == 0


def test_c11_run_slot_lock_directory_is_created_when_missing(
    project: Project, tracker: InMemoryTracker, isolated_slots: Path, tmp_path: Path
) -> None:
    assert not isolated_slots.exists()
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == 0, outcome.line
    assert (isolated_slots / "0.lock").is_file()
    nested = tmp_path / "a" / "b"
    with slots.held(nested) as k:
        assert k == 0
        assert (nested / "0.lock").is_file()


def test_c11_run_slot_folder_is_under_the_users_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert MACHINE_SLOTS() == tmp_path / ".ariane" / "slots"
