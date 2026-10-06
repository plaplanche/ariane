"""C9: the workflow script publishes the committed report as commit statuses."""

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
        "NO_PROXY": "127.0.0.1,localhost",
    }
    for name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        env.pop(name, None)
    return subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=cwd, env=env, capture_output=True, text=True
    )


def write_report(cwd: Path) -> None:
    results = [
        CheckResult("lint", ("x",), True, True, "exit 0", "", 0.1),
        CheckResult("tests", ("y",), True, False, "exit 1", "", 33.7),
    ]
    (cwd / "work" / "8").mkdir(parents=True)
    (cwd / "work" / "8" / "checks.md").write_text(checks.report(results, "abc"), encoding="utf-8")


def test_c9_one_status_per_check(stub: tuple[Stub, str], tmp_path: Path) -> None:  # noqa: F811
    state, url = stub
    state.responses[("POST", STATUS_PATH)] = (201, {})
    write_report(tmp_path)
    done = run_script(tmp_path, url, "ariane/8")
    assert done.returncode == 0, done.stderr
    assert [r["body"] for r in state.requests] == [
        {
            "state": "success",
            "context": "ariane/lint",
            "description": "pass, 0.1 s",
            "target_url": f"{url}/owner/name/blob/ariane/8/work/8/checks.md",
        },
        {
            "state": "failure",
            "context": "ariane/tests",
            "description": "exit 1, 33.7 s",
            "target_url": f"{url}/owner/name/blob/ariane/8/work/8/checks.md",
        },
    ]
    assert all(r["path"] == STATUS_PATH for r in state.requests)


def test_c9_other_branch_or_missing_report_sends_nothing(
    stub: tuple[Stub, str],  # noqa: F811
    tmp_path: Path,
) -> None:
    state, url = stub
    write_report(tmp_path)
    assert run_script(tmp_path, url, "feature/x").returncode == 0
    assert run_script(tmp_path, url, "ariane/9").returncode == 0
    assert state.requests == []


def test_c9_exit_1_when_a_status_is_refused(stub: tuple[Stub, str], tmp_path: Path) -> None:  # noqa: F811
    state, url = stub
    state.responses[("POST", STATUS_PATH)] = (403, {"message": "not permitted"})
    write_report(tmp_path)
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
