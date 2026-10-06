# Product brief: Publish Ariane's check results as commit statuses from a GitHub Actions workflow (C9)

- Status: draft
- Approved: not yet
- Source: issue #8 (https://github.com/plaplanche/ariane/issues/8)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

C9 asks Ariane to publish each check's result as a commit status on the pull request (issue #5, merged). When Ariane runs in a cloud session, the platform's GitHub proxy refuses `POST /repos/{owner}/{repo}/statuses/{sha}` with HTTP 403 ("not permitted through this proxy"). Ariane then journals a warning and delivers without statuses. A GitHub Actions workflow runs on GitHub's side, so it can publish the same statuses from the report Ariane commits, whatever machine Ariane ran on.

## Current state

- `src/ariane/checks.py`: `summary_table` writes the table at the top of `work/<n>/checks.md`. It has a header row `| Check | Blocking | Result | Duration |`, then one row per check, for example `| lint | yes | pass | 0.1 s |` or `| tests | yes | **fail** (exit 1) | 33.7 s |`.
- `src/ariane/github.py`: `GitHubTracker.set_commit_status(sha, context, state, description, target_url)` and `file_url(branch, path)`.
- `.github/workflows/ci.yml`: the only workflow.

## Decided spec

1. `src/ariane/checks.py` gains `parse_summary_table(text: str) -> list[tuple[str, bool, str]]`. It reads the first table of a `checks.md` text and returns, per check, its name, whether it passed (the Result cell is exactly `pass`), and a description made of the Result and Duration cells without Markdown markup (for example `exit 1, 33.7 s` or `pass, 0.1 s`). Text without that table gives an empty list.
2. New script `scripts/publish_check_statuses.py`, run as `uv run python scripts/publish_check_statuses.py`. It reads these environment variables: `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_API_URL`, `HEAD_SHA` and `HEAD_REF`.
   - If `HEAD_REF` is not `ariane/<number>`, it prints one line saying so and exits 0.
   - It reads `work/<number>/checks.md`. If the file is missing, it prints one line saying so and exits 0.
   - Otherwise it publishes one status per row with `GitHubTracker.set_commit_status`: context `ariane/<name>`, state `success` or `failure`, the description cut to 140 characters, and `target_url` = `file_url(HEAD_REF, "work/<number>/checks.md")`. It prints one line per status and exits 1 if any status was refused.
3. New workflow `.github/workflows/check-statuses.yml`:
   - It runs on `pull_request` (types `opened`, `synchronize`, `reopened`).
   - It runs only when the head branch starts with `ariane/` and the pull request comes from this repository, not a fork.
   - Permissions: `contents: read` and `statuses: write`.
   - It checks out the pull request's head commit, installs uv with `astral-sh/setup-uv@v6`, and runs the script with `GITHUB_TOKEN` from `secrets.GITHUB_TOKEN`, plus `HEAD_SHA` and `HEAD_REF` from the pull request event.
4. `docs/adr/0005-ci-matrix.md` gets a short paragraph naming this second workflow and why it exists. The README's paragraph on commit statuses says that the workflow also publishes them, including when Ariane cannot (for example from a cloud session).

## Release note

Added: a GitHub Actions workflow publishes Ariane's check results as commit statuses on its pull requests, wherever Ariane ran.

## Acceptance criteria

- `parse_summary_table` returns the expected tuples for a report with a passing and a failing check, and an empty list for text without the table (table-driven test in `tests/test_checks.py`).
- The script, run against the local HTTP stub of `tests/test_github.py` with a temporary `work/<n>/checks.md`, sends one documented request per check. It exits 0 without any request for a branch that is not `ariane/<n>` or a missing report, and exits 1 when a status is refused.
- A test reads the workflow file as text and finds the trigger, the `ariane/` and same-repository condition, and the two permissions above (no YAML dependency is added).
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `tests/test_checks.py` covers `parse_summary_table`.
- [ ] A new `tests/test_publish_check_statuses.py` covers the script's three paths.
- [ ] `.github/workflows/check-statuses.yml` exists, and ADR 0005 and the README mention it.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

- Re-running the checks in the workflow: it reports what Ariane replayed.
- Pull requests from forks.
- Any change to how Ariane itself publishes statuses.
