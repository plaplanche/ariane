"""C9: the workflow script replays the checks and publishes them as commit statuses."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from test_github import TOKEN, Stub, stub  # noqa: F401

from ariane import checks
from ariane.checks import CheckResult

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "publish_check_statuses.py"
WORKFLOW = ROOT / ".github" / "workflows" / "check-statuses.yml"
SHA = "a" * 40
STATUS_PATH = f"/repos/owner/name/statuses/{SHA}"


def run_script(cwd: Path, url: str, ref: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "GITHUB_TOKEN": TOKEN,
        "GITHUB_REPOSITORY": "owner/name",
        "GITHUB_API_URL": url,
        "HEAD_SHA": SHA,
        "HEAD_REF": ref,
        "GITHUB_RUN_ID": "42",
        "GITHUB_SERVER_URL": "https://github.com",
        "NO_PROXY": "127.0.0.1,localhost",
    }
    for name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        env.pop(name, None)
    return subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=cwd, env=env, capture_output=True, text=True
    )


def write_config(cwd: Path, *, lint_ok: bool, setup_ok: bool = True) -> None:
    def command(ok: bool) -> str:
        return f'["{Path(sys.executable).as_posix()}", "-c", "raise SystemExit({0 if ok else 1})"]'

    (cwd / "ariane.toml").write_text(
        f"""[project]
base_branch = "main"
setup = {command(setup_ok)}

[tracker]
kind = "github"
repository = "owner/name"
token_env = "GH_TOKEN"

[agents.implementer]
runtime = "claude-code"
model = "m"
tools = ["Read"]
max_budget_usd = 1.0
timeout_minutes = 1

[[checks]]
name = "lint"
command = {command(lint_ok)}

[[checks]]
name = "tests"
command = {command(False)}
""",
        encoding="utf-8",
    )


def forge_report(cwd: Path) -> None:
    results = [
        CheckResult("lint", ("x",), True, True, "exit 0", "", 0.1),
        CheckResult("tests", ("y",), True, True, "exit 0", "", 0.1),
    ]
    (cwd / "work" / "8").mkdir(parents=True)
    (cwd / "work" / "8" / "checks.md").write_text(checks.report(results, "abc"), encoding="utf-8")


def published(state: Stub) -> list[tuple[str, str]]:
    return [(r["body"]["context"], r["body"]["state"]) for r in state.requests]


def test_c9_statuses_from_replay_follow_real_results(
    stub: tuple[Stub, str],  # noqa: F811
    tmp_path: Path,
) -> None:
    state, url = stub
    state.responses[("POST", STATUS_PATH)] = (201, {})
    write_config(tmp_path, lint_ok=True)
    done = run_script(tmp_path, url, "ariane/8")
    assert done.returncode == 0, done.stderr
    assert published(state) == [("ariane/lint", "success"), ("ariane/tests", "failure")]
    lint, tests = (r["body"] for r in state.requests)
    assert lint["description"].startswith("pass, ")
    assert tests["description"].startswith("exit 1, ")
    assert {r["body"]["target_url"] for r in state.requests} == {
        "https://github.com/owner/name/actions/runs/42"
    }
    assert all(r["path"] == STATUS_PATH for r in state.requests)


def test_c9_statuses_from_replay_ignore_forged_report(
    stub: tuple[Stub, str],  # noqa: F811
    tmp_path: Path,
) -> None:
    state, url = stub
    state.responses[("POST", STATUS_PATH)] = (201, {})
    write_config(tmp_path, lint_ok=False)
    forge_report(tmp_path)
    assert run_script(tmp_path, url, "ariane/8").returncode == 0
    assert published(state) == [("ariane/lint", "failure"), ("ariane/tests", "failure")]


def test_c9_statuses_from_replay_failed_setup_fails_every_check(
    stub: tuple[Stub, str],  # noqa: F811
    tmp_path: Path,
) -> None:
    state, url = stub
    state.responses[("POST", STATUS_PATH)] = (201, {})
    write_config(tmp_path, lint_ok=True, setup_ok=False)
    assert run_script(tmp_path, url, "ariane/8").returncode == 0
    assert published(state) == [("ariane/lint", "failure"), ("ariane/tests", "failure")]


def test_c9_statuses_from_replay_other_branch_sends_nothing(
    stub: tuple[Stub, str],  # noqa: F811
    tmp_path: Path,
) -> None:
    state, url = stub
    write_config(tmp_path, lint_ok=True)
    assert run_script(tmp_path, url, "feature/x").returncode == 0
    assert state.requests == []


def test_c9_exit_1_when_a_status_is_refused(stub: tuple[Stub, str], tmp_path: Path) -> None:  # noqa: F811
    state, url = stub
    state.responses[("POST", STATUS_PATH)] = (403, {"message": "not permitted"})
    write_config(tmp_path, lint_ok=True)
    done = run_script(tmp_path, url, "ariane/8")
    assert done.returncode == 1
    assert len(state.requests) == 2
    assert TOKEN not in done.stdout + done.stderr


def test_c9_workflow_trigger_condition_and_permissions() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:" in text
    assert "types: [opened, synchronize, reopened]" in text
    assert "startsWith(github.head_ref, 'ariane/')" in text
    assert "github.event.pull_request.head.repo.full_name == github.repository" in text
    assert "contents: read" in text
    assert "statuses: write" in text
    assert "astral-sh/setup-uv@v6" in text
    assert "persist-credentials: false" in text
    assert "uv run --no-sync" in text


def test_c9_script_never_reads_work_folder() -> None:
    assert "work/" not in SCRIPT.read_text(encoding="utf-8")


def test_c9_statuses_from_replay_checks_run_without_the_token(
    stub: tuple[Stub, str],  # noqa: F811
    tmp_path: Path,
) -> None:
    state, url = stub
    state.responses[("POST", STATUS_PATH)] = (201, {})
    write_config(tmp_path, lint_ok=True)
    probe = "import os, sys; sys.exit(1 if 'GITHUB_TOKEN' in os.environ else 0)"
    text = (tmp_path / "ariane.toml").read_text(encoding="utf-8")
    text = text.replace(
        'name = "tests"\ncommand = ',
        f'name = "tests"\ncommand = ["{Path(sys.executable).as_posix()}", "-c", "{probe}"]\n# ',
    )
    (tmp_path / "ariane.toml").write_text(text, encoding="utf-8")
    assert run_script(tmp_path, url, "ariane/8").returncode == 0
    assert published(state) == [("ariane/lint", "success"), ("ariane/tests", "success")]


def test_c9_statuses_from_replay_setup_runs_without_the_token(
    stub: tuple[Stub, str],  # noqa: F811
    tmp_path: Path,
) -> None:
    state, url = stub
    state.responses[("POST", STATUS_PATH)] = (201, {})
    write_config(tmp_path, lint_ok=True)
    probe = "import os, sys; sys.exit(1 if 'GITHUB_TOKEN' in os.environ else 0)"
    text = (tmp_path / "ariane.toml").read_text(encoding="utf-8")
    text = text.replace(
        "setup = ",
        f'setup = ["{Path(sys.executable).as_posix()}", "-c", "{probe}"]\n# ',
        1,
    )
    (tmp_path / "ariane.toml").write_text(text, encoding="utf-8")
    assert run_script(tmp_path, url, "ariane/8").returncode == 0
    assert published(state)[0] == ("ariane/lint", "success")


def test_c9_statuses_from_replay_unreadable_config_exits_1(
    stub: tuple[Stub, str],  # noqa: F811
    tmp_path: Path,
) -> None:
    state, url = stub
    (tmp_path / "ariane.toml").write_text("[project]\nbase_brunch = 'main'\n", encoding="utf-8")
    done = run_script(tmp_path, url, "ariane/8")
    assert done.returncode == 1
    assert "Cannot publish statuses" in done.stdout
    assert state.requests == []
