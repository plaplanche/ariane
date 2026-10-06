"""Deterministic checks (C9): Ariane runs them itself and never believes an agent."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ariane import process
from ariane.config import CheckConfig
from ariane.ticket import fenced


@dataclass(frozen=True)
class CheckResult:
    name: str
    command: tuple[str, ...]
    blocking: bool
    passed: bool
    detail: str  # "exit 0", "exit 1", "timed out after 900 s", "command not found on PATH: x"
    output: str
    duration_s: float


def run_checks(
    checks: Sequence[CheckConfig], cwd: Path, env: Mapping[str, str] | None = None
) -> list[CheckResult]:
    """Run every check, even after a failure, in environment `env`."""
    return [run_check(check, cwd, env) for check in checks]


def run_check(check: CheckConfig, cwd: Path, env: Mapping[str, str] | None = None) -> CheckResult:
    timeout_s = check.timeout_minutes * 60
    try:
        done = process.run(check.command, cwd=cwd, timeout_s=timeout_s, env=env, merge_stderr=True)
    except process.CommandNotFoundError as exc:
        return CheckResult(check.name, check.command, check.blocking, False, str(exc), "", 0.0)
    detail = f"timed out after {timeout_s:g} s" if done.timed_out else f"exit {done.returncode}"
    return CheckResult(
        check.name, check.command, check.blocking, done.ok, detail, done.stdout, done.duration_s
    )


def blocking_failures(results: Sequence[CheckResult]) -> list[CheckResult]:
    return [r for r in results if r.blocking and not r.passed]


def summary_line(results: Sequence[CheckResult]) -> str:
    failed = [r for r in results if not r.passed]
    blocking = blocking_failures(results)
    return (
        f"Summary: {len(results) - len(failed)} passed, {len(failed)} failed"
        f" ({len(blocking)} blocking)."
    )


def summary_table(results: Sequence[CheckResult]) -> str:
    lines = ["| Check | Blocking | Result | Duration |", "| --- | --- | --- | --- |"]
    for r in results:
        verdict = "pass" if r.passed else f"**fail** ({r.detail})"
        blocking = "yes" if r.blocking else "no"
        lines.append(f"| {r.name} | {blocking} | {verdict} | {r.duration_s:.1f} s |")
    return "\n".join(lines)


def report(results: Sequence[CheckResult], commit: str) -> str:
    """The full report: one section per check with its complete output, then a summary line."""
    parts = [f"# Checks\n\nReplayed by Ariane on commit `{commit}`.\n", summary_table(results), ""]
    for r in results:
        verdict = "passed" if r.passed else "failed"
        parts += [
            f"## {r.name}\n",
            f"- Command: `{' '.join(r.command)}`",
            f"- Blocking: {'yes' if r.blocking else 'no'}",
            f"- Result: {verdict} ({r.detail}, {r.duration_s:.1f} s)\n",
            fenced(r.output) + "\n",
        ]
    parts.append(summary_line(results))
    return "\n".join(parts) + "\n"
