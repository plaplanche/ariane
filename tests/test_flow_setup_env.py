"""The setup command runs without credentials, on the base code and in the replay (C9, C21)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ariane import flow, process
from ariane.tracker import InMemoryTracker

from conftest import PY, FakeRuntime, Project, make_config
from test_flow import start

PROBE = """
import json, os, subprocess, sys
push = subprocess.run(
    ["git", "push", "--quiet", "origin", "HEAD:refs/heads/stolen"],
    capture_output=True,
)
with open(sys.argv[1], "a", encoding="utf-8") as out:
    record = {"token": os.environ.get("GH_TOKEN"), "push": push.returncode}
    out.write(json.dumps(record) + "\\n")
"""


def records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def probe_config(out: Path):  # type: ignore[no-untyped-def]
    return make_config(setup=(PY, "-c", PROBE, str(out)))


def test_c9_setup_without_credentials_first_setup_sees_no_token_and_cannot_push(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    out = tmp_path / "seen.jsonl"
    start(project, tracker, FakeRuntime(), probe_config(out))
    first = records(out)[0]
    assert first["token"] is None
    assert first["push"] != 0
    assert "stolen" not in project.remote_branches()


def test_c9_setup_without_credentials_replay_setup_sees_no_token_and_cannot_push(
    project: Project, tracker: InMemoryTracker, tmp_path: Path
) -> None:
    out = tmp_path / "seen.jsonl"
    start(project, tracker, FakeRuntime(), probe_config(out))
    seen = records(out)
    assert len(seen) == 2
    assert seen[1]["token"] is None
    assert seen[1]["push"] != 0
    assert "stolen" not in project.remote_branches()


def test_c9_setup_without_credentials_negative_control_full_environment_is_detected(
    project: Project,
    tracker: InMemoryTracker,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = process.run

    def run_with_full_environment(argv, **kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("timeout_s") == flow.SETUP_TIMEOUT_S:
            kwargs["env"] = None
        return real(argv, **kwargs)

    monkeypatch.setattr(process, "run", run_with_full_environment)
    out = tmp_path / "seen.jsonl"
    start(project, tracker, FakeRuntime(), probe_config(out))
    assert [seen["token"] for seen in records(out)] != [None, None]
