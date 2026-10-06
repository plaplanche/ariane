"""C9: Ariane runs every check itself and reports each one."""

from __future__ import annotations

from pathlib import Path

from ariane import checks
from ariane.config import CheckConfig

from conftest import PY


def test_c9_all_checks_run_even_after_a_failure_with_one_section_each(tmp_path: Path) -> None:
    results = checks.run_checks(
        [
            CheckConfig("first", (PY, "-c", "print('```'); raise SystemExit(2)"), True, 1),
            CheckConfig("missing", ("no-such-checker-for-ariane",), False, 1),
            CheckConfig("last", (PY, "-c", "print('all good')"), True, 1),
        ],
        tmp_path,
    )
    assert [(r.name, r.passed, r.detail) for r in results] == [
        ("first", False, "exit 2"),
        ("missing", False, "command not found on PATH: no-such-checker-for-ariane"),
        ("last", True, "exit 0"),
    ]
    report = checks.report(results, "abc123")
    assert report.count("\n## ") == 3
    assert "````text\n```\n````" in report  # output with a fence stays inside the section
    assert report.rstrip().endswith("Summary: 1 passed, 2 failed (1 blocking).")
    assert [r.name for r in checks.blocking_failures(results)] == ["first"]


def test_c9_a_check_over_its_time_limit_fails(tmp_path: Path) -> None:
    slow = CheckConfig("slow", (PY, "-c", "import time; time.sleep(30)"), True, 1 / 30)
    result = checks.run_check(slow, tmp_path)
    assert not result.passed and result.detail == "timed out after 2 s"


def test_c9_summary_table_marks_failures() -> None:
    result = checks.CheckResult("lint", ("ruff",), False, False, "exit 1", "", 1.25)
    table = checks.summary_table([result])
    assert "| lint | no | **fail** (exit 1) | 1.2 s |" in table
