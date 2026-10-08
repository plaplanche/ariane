# Product brief: CI skips the checks for pull requests that change only documentation

- Status: draft
- Approved: not yet
- Source: issue #18 (https://github.com/plaplanche/ariane/issues/18)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Every pull request runs the six CI jobs of ADR 0005 (about 4 minutes on Windows), including pull requests that change only documentation (ADRs, learnings). The repository's ruleset requires the six checks by name, so the workflow cannot be skipped (`[skip ci]` or a `paths` filter would leave the required checks waiting forever and the pull request unmergeable). The owner decided: keep the jobs, skip their heavy steps when a pull request changes only documentation.

## Current state

- `.github/workflows/ci.yml` runs, in every job: checkout, setup-uv, `uv sync --locked`, the five checks of ADR 0004 and, on Windows, two PowerShell smoke steps.
- `docs/adr/0005-ci-matrix.md` describes that workflow.

## Decided spec

- A new script `scripts/docs_only.py` reads changed paths (one per line on standard input) and prints `docs_only=true` when every path is documentation, `docs_only=false` otherwise (including when the list is empty). Documentation is: any path under `docs/`, and any path ending in `.md` that is not under `work/`. Exit code 0 in both cases. Its decision is a function `is_docs_only(paths)` that tests import.
- In `.github/workflows/ci.yml`, for `pull_request` events only, a step right after checkout lists the files changed between the pull request's base and head commits and runs the script, writing its output to `$GITHUB_OUTPUT`; the checkout fetches enough history for that diff. For `push` events the step reports `docs_only=false`.
- When `docs_only=true`, every later step of the job (install, lint, format, types, tests, file length, both smoke steps) is skipped, so each job ends green in well under a minute and the six required checks are still reported.
- `docs/adr/0005-ci-matrix.md` gains a paragraph stating this rule and why (required checks by name).
- The script runs with Python from setup-uv without the project environment, on all three operating systems.

## Release note

Changed: CI skips the checks for pull requests that change only documentation.

## Acceptance criteria

- Tests named `test_ci_docs_only_*` in `tests/test_docs_only.py` cover: only `docs/` paths (true), only `README.md` and `CLAUDE.md` (true), a `.md` under `work/` (false), one `src/` path among docs (false), `.github/workflows/ci.yml` (false), an empty list (false).
- `ci.yml` skips the heavy steps only when the step's output is `docs_only=true`.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `scripts/docs_only.py` exists and is under 600 lines.
- [ ] `uv run pytest -k ci_docs_only` runs at least 6 tests and they pass.
- [ ] `docs/adr/0005-ci-matrix.md` describes the documentation-only rule.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Skipping CI on pushes to `main`, any other path rule, the `check-statuses.yml` workflow.

## Related

ADR 0005, ADR 0004.
