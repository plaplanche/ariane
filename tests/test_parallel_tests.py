"""Tests run in parallel by default, serially with `-n 0`, and in shards (C9, ADR 0048, 0049)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_parallel_tests_are_the_default_of_uv_run_pytest() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    options = pyproject["tool"]["pytest"]["ini_options"]
    assert options["addopts"].split() == ["-n", "auto"]
    dev = pyproject["dependency-groups"]["dev"]
    assert any(dep.startswith("pytest-xdist") for dep in dev)
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    assert "pytest-xdist" in {package["name"] for package in lock["package"]}


def test_parallel_tests_each_worker_has_its_own_temporary_directory(
    tmp_path_factory: pytest.TempPathFactory, worker_id: str
) -> None:
    # Per-test state is what lets the tests run concurrently: under xdist every worker gets its
    # own base directory, named after it; serially (`-n 0`) the worker is "master".
    base = tmp_path_factory.getbasetemp()
    if worker_id == "master":
        assert "PYTEST_XDIST_WORKER" not in os.environ
    else:
        assert os.environ["PYTEST_XDIST_WORKER"] == worker_id
        assert worker_id in base.name


def _collected(*options: str) -> list[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    command = [sys.executable, "-m", "pytest", "-n", "0", "-p", "no:cacheprovider"]
    done = subprocess.run(
        [*command, "--collect-only", "-q", *options],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return [line for line in done.stdout.splitlines() if "::" in line]


def test_c9_shards_two_groups_split_the_whole_suite_from_the_stored_durations() -> None:
    # The Windows CI job may run in shards (ADR 0049): each runs one group of `pytest-split`,
    # from `.test_durations`. Together the groups run every test exactly once.
    durations = json.loads((ROOT / ".test_durations").read_text(encoding="utf-8"))
    assert durations and all(name.startswith("tests/") for name in durations)
    split = ["--splits", "2", "--splitting-algorithm", "least_duration"]
    first = _collected(*split, "--group", "1")
    second = _collected(*split, "--group", "2")
    assert first and second and not set(first) & set(second)
    assert sorted(first + second) == sorted(_collected())
