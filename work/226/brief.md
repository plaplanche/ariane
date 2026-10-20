# Product brief: Flaky tests: parallel-checks helpers append to one shared file, the template project is copied during a background git maintenance (C9, tests only)

- Source: issue #226 (https://github.com/plaplanche/ariane/issues/226)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Two tests fail now and then in CI for a reason in the tests themselves, not in the code under test; a re-run of the same commit was green each time:

1. `tests/test_c9_parallel_checks.py::test_c9_parallel_checks_running_at_once_see_different_slots` failed on `windows-latest / Python 3.13 / shard 1` (pull request #225) with `JSONDecodeError` on an empty line of its record file. Its three recording checks run at the same moment and append one line each to the same file; concurrent appends from separate processes are not atomic on Windows, so their writes can interleave.
2. The set-up of `tests/test_c19_attempts.py::test_c19_attempts_reach_metrics_json` errored on `ubuntu-latest / Python 3.13` (pull request #227): copying the per-worker template project (`project_template` in `tests/conftest.py`, #206, ADR 0049) met `origin.git/objects/maintenance.lock`, which a background git maintenance started by an earlier git command in the template removed during the copy (`shutil.Error`, no such file). Any test using `project` can hit it.

Spec: C9 (parallel replay, ADR 0052); CLAUDE.md rule 6 (CI on Windows, macOS and Linux); ADR 0049 (template project).

## Current state

- `RECORD` in `tests/test_c9_parallel_checks.py` opens `sys.argv[1]` in append mode and writes one JSON line; `recording()` gives every check the same path; `records()` parses each line of that one file.
- `project_template` builds the bare remote and its clone with git commands that may start an automatic background maintenance (`gc --auto`, `maintenance run --auto`); `project` then copies both folders with `shutil.copytree` while it may still run.

## Decided spec

- **One file per recording check.** `RECORD` writes `<out>.<pid>` (one JSON object, one line), and `records(out)` reads every `<out>.*` file next to `out`, sorted by name. No two processes write to the same file.
- **No background maintenance in the template.** The template's isolated git configuration (the file its `GIT_CONFIG_GLOBAL` points to) sets `gc.auto = 0`, `maintenance.auto = false` and `gc.autoDetach = false` before the first git command, so no git process keeps changing the template's folders after it returns. The copies keep that configuration only as the template's own repositories do today (nothing else changes for a test).
- The tests that use these helpers keep their assertions unchanged.

## Release note

None (tests only).

## Acceptance criteria

- No helper in `tests/test_c9_parallel_checks.py` has two check processes write to one file.
- A test shows that the template's git configuration disables automatic maintenance (`git config --get gc.auto` is `0` and `maintenance.auto` is `false` with the template's environment).
- `uv run pytest` passes, and the CI's five required jobs are green on the pull request.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k "c9_parallel_checks or c9_project_template"` passes.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): ADR 0049's template paragraph mentions the disabled maintenance; no module documentation affected (tests only).

## Out of scope

- Any change to `src/`.

## Related

#143 (parallel replay, ADR 0052), #206 (template project, ADR 0049), pull requests #225 and #227 (where they failed); spec C9.
