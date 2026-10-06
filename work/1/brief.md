# Product brief: ariane --version shows the Python version and platform

- Status: draft
- Approved: not yet
- Source: issue #1 (https://github.com/plaplanche/ariane/issues/1)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Bug reports about Ariane will come from Windows, macOS and Linux. Knowing the exact Python version and platform behind a report saves a round trip.

## Current state

`ariane --version` prints only `ariane <version>` (`src/ariane/cli.py`, the `--version` argument of `_parser`).

## Decided spec

`ariane --version` prints one line: `ariane <version> (Python <major.minor.micro>, <platform>)`, where the platform is `sys.platform` (for example `win32`, `darwin`, `linux`). The exit code stays 0.

## Release note

Changed: `ariane --version` also shows the Python version and platform.

## Acceptance criteria

- The output is exactly one line matching `ariane <version> (Python X.Y.Z, <sys.platform>)`.
- A test in `tests/test_cli.py` checks it through `python -m ariane --version`.

## Acceptance checklist

- [ ] `tests/test_cli.py` covers the new format.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Any other command or output.
