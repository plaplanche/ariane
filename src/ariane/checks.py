"""Deterministic checks (C9): Ariane runs them itself and never believes an agent."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ariane import process
from ariane.config import CONFIG_FILE, CheckConfig, matching_paths
from ariane.ticket import fenced

PASSING_OUTPUT_LINES = 20
CHANGED_FILES_VARIABLE = "ARIANE_CHANGED_FILES"
CHANGED_FILES = "changed-files.txt"  # in the replay tree's ticket folder, while a check runs
SKIPPED = "no changed file matches `paths`"


@dataclass(frozen=True)
class CheckResult:
    name: str
    command: tuple[str, ...]
    blocking: bool
    passed: bool
    detail: str  # "exit 0", "exit 1", "timed out after 900 s", "command not found on PATH: x"
    output: str
    duration_s: float
    not_run_locally: tuple[str, ...] = ()  # globs of the tests this replay did not run
    skipped: bool = False  # not selected: no changed file matches its `paths` (passed is True)


def changed_files(name_status: str) -> list[str]:
    """The paths of a `git diff --name-status` listing; a rename or copy counts on both sides."""
    found: list[str] = []
    for line in name_status.splitlines():
        found += [p for p in line.split("\t")[1:] if p and p not in found]
    return found


def selected(
    all_checks: Sequence[CheckConfig], changed: Sequence[str], check_all_paths: Sequence[str]
) -> list[CheckConfig]:
    """The checks a change selects: all of them when it touches `ariane.toml` or a
    `check_all_paths` file; else each check without `paths` (`always`, the documentation
    checks) and each with a changed file matching its `paths`."""
    if CONFIG_FILE in changed or matching_paths(check_all_paths, changed):
        return list(all_checks)
    return [c for c in all_checks if not c.paths or matching_paths(c.paths, changed)]


def skipped_result(check: CheckConfig) -> CheckResult:
    """The result of a check the change did not select: not run, so it blocks nothing."""
    return CheckResult(
        check.name,
        check.command,
        check.blocking,
        True,
        SKIPPED,
        "",
        0.0,
        check.not_run_locally,
        True,
    )


def skipped_names(results: Sequence[CheckResult]) -> list[str]:
    return [r.name for r in results if r.skipped]


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
        return CheckResult(
            check.name,
            check.command,
            check.blocking,
            False,
            str(exc),
            "",
            0.0,
            check.not_run_locally,
        )
    detail = f"timed out after {timeout_s:g} s" if done.timed_out else f"exit {done.returncode}"
    return CheckResult(
        check.name,
        check.command,
        check.blocking,
        done.ok,
        detail,
        done.stdout,
        done.duration_s,
        check.not_run_locally,
    )


def blocking_failures(results: Sequence[CheckResult]) -> list[CheckResult]:
    return [r for r in results if r.blocking and not r.passed]


def summary_line(results: Sequence[CheckResult]) -> str:
    failed = [r for r in results if not r.passed]
    blocking = blocking_failures(results)
    skipped = len(skipped_names(results))
    shown = f", {skipped} skipped ({SKIPPED})" if skipped else ""
    return (
        f"Summary: {len(results) - len(failed) - skipped} passed, {len(failed)} failed"
        f" ({len(blocking)} blocking){shown}."
    )


def summary_table(results: Sequence[CheckResult]) -> str:
    lines = ["| Check | Blocking | Result | Duration |", "| --- | --- | --- | --- |"]
    for r in results:
        verdict = "skipped" if r.skipped else "pass" if r.passed else f"**fail** ({r.detail})"
        blocking = "yes" if r.blocking else "no"
        lines.append(f"| {r.name} | {blocking} | {verdict} | {r.duration_s:.1f} s |")
    return "\n".join(lines)


def _shown_output(r: CheckResult) -> str:
    """A passing check keeps its last lines only; a failing check keeps everything."""
    lines = r.output.splitlines()
    if not r.passed or len(lines) <= PASSING_OUTPUT_LINES:
        return r.output
    omitted = len(lines) - PASSING_OUTPUT_LINES
    kept = lines[-PASSING_OUTPUT_LINES:]
    return "\n".join([f"({omitted} earlier lines omitted)", *kept])


def unrun_files(results: Sequence[CheckResult], changed: Sequence[str]) -> list[str]:
    """The changed files that hold tests no replayed check ran (declared `not_run_locally`)."""
    found: list[str] = []
    for r in results:
        found += [p for p in matching_paths(r.not_run_locally, changed) if p not in found]
    return found


def _not_run_lines(r: CheckResult, changed: Sequence[str]) -> list[str]:
    if not r.not_run_locally:
        return []
    globs = ", ".join(f"`{g}`" for g in r.not_run_locally)
    matches = matching_paths(r.not_run_locally, changed)
    files = ", ".join(f"`{p}`" for p in matches) if matches else "no changed file matches"
    return [f"- Not run by this replay (CI only): {globs}", f"- Changed files it skips: {files}"]


def report(results: Sequence[CheckResult], commit: str, changed: Sequence[str] = ()) -> str:
    """The full report: one section per check with its complete output, then a summary line."""
    parts = [
        f"# Checks\n\nReplayed by Ariane on commit `{commit}`.\n\n"
        f"Each check was replayed in its own clean working tree at `{commit}`, after the setup.\n",
        summary_table(results),
        "",
    ]
    for r in results:
        if r.skipped:
            parts += [
                f"## {r.name}\n",
                f"- Command: `{' '.join(r.command)}`",
                f"- Skipped: {SKIPPED}",
                "",
            ]
            continue
        verdict = "passed" if r.passed else "failed"
        parts += [
            f"## {r.name}\n",
            f"- Command: `{' '.join(r.command)}`",
            f"- Blocking: {'yes' if r.blocking else 'no'}",
            f"- Result: {verdict} ({r.detail}, {r.duration_s:.1f} s)",
            *_not_run_lines(r, changed),
            "",
            fenced(_shown_output(r)) + "\n",
        ]
    parts.append(summary_line(results))
    return "\n".join(parts) + "\n"


def parse_summary_table(text: str) -> list[tuple[str, bool, str]]:
    """Read the first table of a `checks.md` text: (name, passed, description) per check."""
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if rows:
                break
            continue
        rows.append([cell.strip() for cell in stripped.strip("|").split("|")])
    if len(rows) < 2 or [c.lower() for c in rows[0]] != ["check", "blocking", "result", "duration"]:
        return []
    parsed = []
    for cells in rows[2:]:
        if len(cells) != 4:
            continue
        name, _, result, duration = cells
        plain = result.replace("**", "")
        if plain.startswith("fail (") and plain.endswith(")"):
            plain = plain[len("fail (") : -1]
        parsed.append((name, result in ("pass", "skipped"), f"{plain}, {duration}"))
    return parsed
