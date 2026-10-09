# 0005. Continuous integration matrix

- Status: accepted; the `check-statuses.yml` paragraph amended by 0018
- Date: 2026-10-06
- Capabilities: platform requirement ("each tested in CI from slice 1")

## Context
Windows (PowerShell 5.1 and 7), macOS and Linux are each tested in CI from slice 1.

## Decision
- GitHub Actions, one workflow `.github/workflows/ci.yml`, on pull requests and on pushes to
  `main` only, so a pull request branch is not tested twice for each push.
- Matrix: `ubuntu-latest`, `macos-latest`, `windows-latest` × Python `3.11` and `3.13`
  (oldest and newest supported), six jobs, `fail-fast: false`.
- Each job installs uv with the official `astral-sh/setup-uv` action (major version tag), runs
  `uv sync --locked`, then the five checks of ADR 0004. The workflow only reads the repository
  (`permissions: contents: read`).
- On Windows, a smoke step runs `ariane --version` and a configuration error case once under
  `shell: powershell` (5.1) and once under `shell: pwsh` (7).
- Pushing the workflow file is impossible from a cloud session (no `workflow` scope): it is
  left uncommitted there and the owner commits it from their machine.
- A second workflow, `.github/workflows/check-statuses.yml`, runs on pull requests from `ariane/*`
  branches of this repository, checks out the head commit without persisting credentials,
  installs the project without the token, runs the setup command and every check declared in
  `ariane.toml` through Ariane's own code, in an environment without the token, and publishes
  one `ariane/<check>` commit status per result, linked to the workflow run
  (`contents: read`, `statuses: write`). It never reads `work/<n>/checks.md`: a status comes
  from a replay, not from a file in the branch. Failing checks give failing statuses; the job
  itself fails only when the configuration cannot be read or a status is refused. It exists
  because a cloud session's GitHub proxy refuses the statuses endpoint, while a workflow runs on
  GitHub's side. Its limit: on `pull_request`, the workflow, the publishing script and
  `ariane.toml` come from the branch, and the branch's code runs as the same runner user as the
  publisher, so the statuses are as trustworthy as the human review of those files in the diff.
- The ruleset requires the six checks by name, so the workflow cannot be skipped (`[skip ci]`
  or a `paths` filter would leave them waiting forever). Instead, on pull requests a step after
  checkout lists the files changed between the base and head commits and runs
  `scripts/docs_only.py`; when every path is documentation (under `docs/`, or a `.md` file
  outside `work/`), all later steps are skipped and each job still ends green. Pushes to `main`
  always run everything.

## Consequences
Six jobs per pull request update or push to `main`, a few minutes each. Platform bugs (paths, encodings, process trees) show up
before merge.

## Alternatives considered
- One Python version: misses standard-library differences between 3.11 and 3.13.
- Only the latest Python: we would claim 3.11 without testing it.
