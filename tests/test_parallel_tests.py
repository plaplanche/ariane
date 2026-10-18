"""The tests run in parallel by default, and serially with `-n 0` (C9, ADR 0048)."""

from __future__ import annotations

import os
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
