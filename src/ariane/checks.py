"""Deterministic checks (C9): Ariane runs them itself and never believes an agent."""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ariane import process
from ariane.config import CONFIG_FILE, CheckConfig, matching_paths
from ariane.risk import FULL_SUITE_VARIABLE, HIGH, LOW, UNMEASURED, ChecksPolicy, Tier
from ariane.stop import Stop
from ariane.ticket import fenced

PASSING_OUTPUT_LINES = 20
CHANGED_FILES_VARIABLE = "ARIANE_CHANGED_FILES"
CHANGED_FILES = "changed-files.txt"  # in the replay tree's ticket folder, while a check runs
SKIPPED = "no changed file matches `paths`"
# Folders opened by handle, the listing made relative to the last one (POSIX); Windows has no
# such call in Python's standard library and goes by path (ADR 0056).
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_BY_HANDLE = {os.open, os.mkdir} <= os.supports_dir_fd and _NOFOLLOW != 0
_FOLDER = getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0) | os.O_RDONLY
# The escapes of a path git quotes (a double quote, a backslash or a control character in it),
# even with core.quotepath=off; any other byte is written as three octal digits.
_ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}


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
    """The paths of a `git diff --name-status` listing; a rename or copy counts on both sides.
    Records end at a line feed only, as git writes them: a name holding another line separator
    (U+2028, a form feed) stays whole, for `unlistable` to refuse."""
    found: list[str] = []
    for line in filter(None, name_status.split("\n")):
        paths = [git_path(p) for p in line.split("\t")[1:] if p]
        found += [p for p in paths if p not in found]
    return found


def git_path(name: str) -> str:
    """The real path behind a path as git prints it: a quoted one is decoded, byte by byte."""
    if len(name) < 2 or not (name.startswith('"') and name.endswith('"')):
        return name
    body, decoded, i = name[1:-1], bytearray(), 0
    while i < len(body):
        if body[i] != "\\" or i + 1 == len(body):
            decoded += body[i].encode("utf-8", "surrogateescape")
            i += 1
        elif body[i + 1] in _ESCAPES:
            decoded.append(_ESCAPES[body[i + 1]])
            i += 2
        else:
            decoded.append(int(body[i + 1 : i + 4], 8) & 0xFF)
            i += 4
    return decoded.decode("utf-8", "surrogateescape")


def unlistable(changed: Sequence[str]) -> list[str]:
    """The changed paths the listing cannot hold on one line: a line break in their name."""
    return [p for p in changed if p.splitlines() != [p]]


@contextlib.contextmanager
def changed_files_listing(tree: Path, records: str, changed: Sequence[str]) -> Iterator[Path]:
    """`records/changed-files.txt` in `tree`, listing the `changed` paths one per line, for the
    block: made new, never over a file of the commit. Ariane never removes it by name: what is
    there after the check may not be the file it wrote, and the whole replay tree is removed after
    each check; the replay's verification leaves that one path out (`without_listing`).

    On POSIX each folder is opened by handle without following a link and the listing is made
    relative to the last one, so another check moving or replacing a folder on the way meanwhile
    never makes Ariane write a file outside the tree."""
    if unlistable(changed):  # `replay_each` refuses them first; never an ambiguous list
        raise ValueError("a changed path holds a line break")
    text = "".join(f"{path}\n" for path in changed).encode("utf-8", "surrogateescape")
    if not _BY_HANDLE:
        with _listing_by_path(tree, records, text) as listing:
            yield listing
        return
    folder = _open_records(tree, records)
    try:
        try:
            fd = os.open(
                CHANGED_FILES,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
                0o644,
                dir_fd=folder,
            )
        except OSError as exc:
            raise _refused(records) from exc
        with os.fdopen(fd, "wb") as out:
            out.write(text)
    finally:
        os.close(folder)
    yield tree / records / CHANGED_FILES


def _open_records(tree: Path, records: str) -> int:
    """A handle on `tree/records`, each folder made if missing and opened without following a
    link: a link on the way refuses the listing."""
    fd = os.open(tree, _FOLDER)
    try:
        for part in PurePosixPath(records).parts:
            with contextlib.suppress(FileExistsError):
                os.mkdir(part, dir_fd=fd)
            try:
                inner = os.open(part, _FOLDER, dir_fd=fd)
            except OSError as exc:
                raise _refused(records) from exc
            os.close(fd)
            fd = inner
    except BaseException:
        os.close(fd)
        raise
    return fd


@contextlib.contextmanager
def _listing_by_path(tree: Path, records: str, text: bytes) -> Iterator[Path]:
    """Windows: the same listing by path, its folder checked inside the tree before it is made."""
    listing = tree / records / CHANGED_FILES
    inside = listing.parent.resolve().is_relative_to(tree.resolve())  # before any folder is made
    if inside:
        listing.parent.mkdir(parents=True, exist_ok=True)
    if not inside or os.path.lexists(listing):
        raise _refused(records)
    with listing.open("xb") as out:
        out.write(text)
    yield listing


def without_listing(status: str, records: str) -> str:
    """`git status --porcelain` of a replay tree without the listing Ariane wrote there, nor
    whatever a check left in its place: the tree is removed after the check, the listing with it."""
    listing = f"{records}/{CHANGED_FILES}"
    kept = [
        line
        for line in status.split("\n")
        if line[3:] != listing and not line[3:].startswith(f"{listing}/")
    ]
    return "\n".join(kept)


def _refused(records: str) -> Stop:
    return Stop(
        f"the replayed commit holds {records}/{CHANGED_FILES}, or its folder leads"
        " outside the replay tree",
        "remove it from the branch, then retry",
    )


def selected(
    all_checks: Sequence[CheckConfig], changed: Sequence[str], check_all_paths: Sequence[str]
) -> list[CheckConfig]:
    """The checks a change selects: all of them when it touches `ariane.toml` or a
    `check_all_paths` file; else each check without `paths` (`always`, the documentation
    checks) and each with a changed file matching its `paths`."""
    if CONFIG_FILE in changed or matching_paths(check_all_paths, changed):
        return list(all_checks)
    return [c for c in all_checks if not c.paths or matching_paths(c.paths, changed)]


def risk_tier(
    policy: ChecksPolicy | None,
    changed: Sequence[str],
    changed_lines: int,
    check_all_paths: Sequence[str] = (),
    failed_before: bool = False,
) -> Tier:
    """The round's tier from its diff (ADR 0056): `high` for each reason found, else `low`;
    always `high`, and not `measured`, without `[checks_policy]`."""
    if policy is None:
        return UNMEASURED
    reasons = []
    if changed_lines > policy.max_changed_lines:
        reasons.append(f"{changed_lines} changed lines (more than {policy.max_changed_lines})")
    touched = modules(changed, policy.module_roots)
    if len(touched) > policy.max_modules:
        names = ", ".join(f"`{m}`" for m in touched)
        reasons.append(f"{len(touched)} modules (more than {policy.max_modules}): {names}")
    for glob in policy.critical_paths:
        if matching_paths([glob], changed):
            reasons.append(f"touches `critical_paths` `{glob}`")
    if CONFIG_FILE in changed:
        reasons.append(f"touches `{CONFIG_FILE}`")
    for glob in check_all_paths:
        if matching_paths([glob], changed):
            reasons.append(f"touches `check_all_paths` `{glob}`")
    if failed_before:
        reasons.append("a previous round failed a check")
    if reasons:
        return Tier(HIGH, tuple(reasons))
    lines = f"{changed_lines} changed line{'s' if changed_lines != 1 else ''}"
    return Tier(LOW, (f"{lines}, {len(touched)} module{'s' if len(touched) != 1 else ''}",))


def modules(changed: Sequence[str], roots: Sequence[str] = ()) -> list[str]:
    """The modules the `changed` paths touch: under the deepest folder matching one of the
    `roots` globs, the root and the path's first segment below it; a path under no root counts
    none. Without `roots`, the repository root is the only one: the first segment."""
    found: list[str] = []
    for path in changed:
        parts = path.split("/")
        module = parts[0] if not roots else None
        for depth in range(1, len(parts)):  # each folder above the file, outermost first
            folder = "/".join(parts[:depth])
            if roots and matching_paths([r.rstrip("/") for r in roots], [folder]):
                module = "/".join(parts[: depth + 1])
        if module is not None and module not in found:
            found.append(module)
    return found


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


def partial_names(chosen: Sequence[CheckConfig], tier: Tier) -> list[str]:
    """The selected checks the round's `tier` runs with `ARIANE_FULL_SUITE=0` (ADR 0056)."""
    return [c.name for c in chosen if tier.variables(c.full_when)[FULL_SUITE_VARIABLE] == "0"]


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


def report(
    results: Sequence[CheckResult],
    commit: str,
    changed: Sequence[str] = (),
    tier: Tier | None = None,
) -> str:
    """The full report: the round's risk tier, one section per check with its complete output,
    then a summary line."""
    shown = f"Risk tier: {tier.text()}.\n\n" if tier is not None else ""
    parts = [
        f"# Checks\n\n{shown}Replayed by Ariane on commit `{commit}`.\n\n"
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
