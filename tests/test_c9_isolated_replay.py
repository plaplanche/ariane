"""C9: each check is replayed in its own clean working tree, as an isolated CI job runs it
(ADR 0041)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from test_config import VALID, with_change

from ariane import checks, config, verify
from ariane.config import CheckConfig
from ariane.tracker import InMemoryTracker

from conftest import FakeRuntime, Project, make_config, sh
from test_flow import environ, start, worktree

PY = sys.executable
WRITE = "import pathlib; pathlib.Path('ignored-by-git').mkdir(exist_ok=True); "
WRITE += "pathlib.Path('ignored-by-git/left.txt').write_text('x')"
NEEDS = (
    "import pathlib, sys; sys.exit(0 if pathlib.Path('ignored-by-git/left.txt').exists() else 1)"
)


def leaving_checks() -> tuple[CheckConfig, ...]:
    return (
        CheckConfig("writes", (PY, "-c", WRITE), True, 1),
        CheckConfig("needs it", (PY, "-c", NEEDS), True, 1),
    )


def appender(path: Path, text: str) -> tuple[str, ...]:
    code = f"open({str(path)!r}, 'a').write({text!r} + '\\n')"
    return (PY, "-c", code)


def trees(project: Project) -> str:
    return sh(["git", "worktree", "list"], project.root)


def test_c9_isolated_replay_check_relying_on_a_leftover_fails(
    project: Project, tracker: InMemoryTracker
) -> None:
    outcome = start(project, tracker, FakeRuntime(), make_config(checks=leaving_checks()))
    assert outcome.exit_code == 1
    assert "blocking checks failed: needs it" in outcome.line


def test_c9_isolated_replay_setup_runs_once_per_check(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    log = tmp_path / "setups.txt"
    passing = tuple(CheckConfig(n, (PY, "-c", "pass"), True, 1) for n in ("a", "b", "c"))
    config_ = make_config(setup=appender(log, "setup"), checks=passing)
    assert start(project, tracker, FakeRuntime(), config_).exit_code == 0
    # once for the implementer's tree, once per check
    assert log.read_text(encoding="utf-8").splitlines() == ["setup"] * 4


def test_c9_isolated_replay_check_setup_replaces_project_setup_in_its_tree(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    log = tmp_path / "setups.txt"
    own = CheckConfig("own", (PY, "-c", "pass"), True, 1, setup=appender(log, "own"))
    plain = CheckConfig("plain", (PY, "-c", "pass"), True, 1)
    config_ = make_config(setup=appender(log, "project"), checks=(own, plain))
    assert start(project, tracker, FakeRuntime(), config_).exit_code == 0
    assert log.read_text(encoding="utf-8").splitlines() == ["project", "own", "project"]


def test_c9_isolated_replay_setup_failure_names_the_check(
    project: Project, tracker: InMemoryTracker
) -> None:
    broken = CheckConfig(
        "broken", (PY, "-c", "pass"), True, 1, setup=(PY, "-c", "raise SystemExit(3)")
    )
    first = CheckConfig("first", (PY, "-c", "pass"), True, 1)
    outcome = start(project, tracker, FakeRuntime(), make_config(checks=(first, broken)))
    assert outcome.exit_code == 1
    assert "'broken'" in outcome.line
    assert "-replay-" not in trees(project)


def test_c9_isolated_replay_no_tree_is_left_after_green_failing_or_stopped(
    project: Project, tracker: InMemoryTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert start(project, tracker, FakeRuntime()).exit_code == 0
    assert "-replay-" not in trees(project)

    tracker.add_issue(8, "Second", "Body.")
    outcome = start(project, tracker, FakeRuntime(), make_config(checks=leaving_checks()), number=8)
    assert outcome.exit_code == 1
    assert "-replay-" not in trees(project)

    seen: list[str] = []
    real = checks.run_check

    def stop_on_second(check: CheckConfig, cwd: Path, env: Any = None) -> checks.CheckResult:
        seen.append(cwd.name)
        if len(seen) == 2:
            raise KeyboardInterrupt
        return real(check, cwd, env)

    monkeypatch.setattr(checks, "run_check", stop_on_second)
    tracker.add_issue(9, "Third", "Body.")
    outcome = start(project, tracker, FakeRuntime(), make_config(checks=leaving_checks()), number=9)
    assert outcome.exit_code == 130
    assert seen == ["9-replay-1", "9-replay-2"]
    assert "-replay-" not in trees(project)


def test_c9_isolated_replay_records_one_line_per_check(
    project: Project, tracker: InMemoryTracker
) -> None:
    assert start(project, tracker, FakeRuntime()).exit_code == 0
    folder = worktree(project) / "work/7"
    journal = (folder / "journal.md").read_text(encoding="utf-8")
    assert "7-replay-1`" in journal
    assert "7-replay-2`" not in journal
    assert "own clean working tree" in (folder / "checks.md").read_text(encoding="utf-8")


def test_c9_isolated_replay_leftover_tree_is_refused(
    project: Project, tracker: InMemoryTracker
) -> None:
    (worktree(project).with_name("7-replay-1")).mkdir(parents=True)
    outcome = start(project, tracker, FakeRuntime())
    assert outcome.exit_code == 1
    assert "remove it, then retry" in outcome.line


def test_c9_isolated_replay_verify_uses_one_tree_per_check(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    sh(["git", "branch", "hand/iso"], project.root)
    seen: list[str] = []
    real = checks.run_check

    def spy(check: CheckConfig, cwd: Path, env: Any = None) -> checks.CheckResult:
        seen.append(cwd.name)
        return real(check, cwd, env)

    monkeypatch.setattr(checks, "run_check", spy)
    outcome = verify.verify(
        "hand/iso",
        repo_root=project.root,
        config=make_config(checks=leaving_checks()),
        runtime=FakeRuntime(),
        environ=environ(),
    )
    assert seen == ["verify-hand-iso-1", "verify-hand-iso-2"]
    assert outcome.exit_code == 1
    assert "-iso-" not in trees(project)


def test_c9_isolated_replay_config_accepts_check_setup() -> None:
    data = with_change("checks.0.setup", ["uv", "sync"])
    assert config.parse(data).checks[0].setup == ("uv", "sync")
    assert config.parse(VALID).checks[0].setup is None


@pytest.mark.parametrize("bad", [[], "uv sync", [1]])
def test_c9_isolated_replay_config_refuses_bad_setup(bad: Any) -> None:
    with pytest.raises(config.ConfigError, match=r"checks\[0\]\.setup"):
        config.parse(with_change("checks.0.setup", bad))
