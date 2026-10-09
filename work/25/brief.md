# Product brief: Publish ariane/* statuses from a replay in CI, never from checks.md (C9)

- Status: draft
- Approved: not yet
- Source: issue #25 (https://github.com/plaplanche/ariane/issues/25)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

`.github/workflows/check-statuses.yml` publishes the `ariane/*` commit statuses from the committed `work/<n>/checks.md`: whoever writes that file on an `ariane/*` branch sets the statuses, and branch protection may require them (C9). A status must come from a replay, never from a file in the branch. Decision: ADR 0018.

## Current state

- `.github/workflows/check-statuses.yml` checks out the pull request's head and runs `scripts/publish_check_statuses.py`.
- `scripts/publish_check_statuses.py:25` reads `work/{number}/checks.md` and publishes one status per row.
- `ariane.toml` declares the checks; `src/ariane/config.py:54` `load` parses it; `src/ariane/checks.py:25` `run_checks` runs them.

## Decided spec

- The workflow checks out the pull request's head commit, installs uv, runs the setup command declared in `ariane.toml`, then every declared check through Ariane's own code (`config.load` and `checks.run_checks`), and publishes one `ariane/<check>` status per check from those results (`success` or `failure`, description with the result and duration). It no longer reads `work/<n>/checks.md`.
- The target URL of each status is the workflow run's page.
- Its trigger and permissions stay (`ariane/*` branches of this repository; `contents: read`, `statuses: write`).
- `docs/adr/0005-ci-matrix.md`'s paragraph on the workflow says what it does now.

## Release note

Security: `ariane/*` statuses come from a replay in CI, never from a report file in the branch.

## Acceptance criteria

- Tests named `test_c9_statuses_from_replay_*` (on the publishing script with a fake tracker) show that the published statuses follow the checks' real results, and that a forged `work/<n>/checks.md` claiming success has no effect on them.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `scripts/publish_check_statuses.py` no longer reads `work/`.
- [ ] `uv run pytest -k c9_statuses_from_replay` runs at least 2 tests and they pass.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Statuses published by Ariane itself from a local run (unchanged), the CI matrix.

## Related

ADR 0018, ADR 0005. The workflow file cannot be pushed from a cloud session: the owner pushes the branch.
