# 0005. Continuous integration matrix

- Status: accepted
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

## Consequences
Six jobs per pull request update or push to `main`, a few minutes each. Platform bugs (paths, encodings, process trees) show up
before merge.

## Alternatives considered
- One Python version: misses standard-library differences between 3.11 and 3.13.
- Only the latest Python: we would claim 3.11 without testing it.
