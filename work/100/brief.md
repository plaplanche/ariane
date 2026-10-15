# Product brief: README: how a second user measures Ariane in shadow mode on macOS (C19, ADR 0021, slice 4)

- Source: issue #100 (https://github.com/plaplanche/ariane/issues/100)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Slice 4's gate: a second user installs Ariane on macOS and their first tickets are measured in shadow mode. ADR 0021 fixes the installation (`uv tool install git+https://github.com/plaplanche/ariane`). This ticket gives that user a complete path in the README, after the shadow, judge and report tickets of slice 4 are merged. Spec: roadmap slice 4, "Adopting Ariane on an existing project", ADR 0021.

## Current state

- `README.md`: "Try it" is written for this repository; shadow mode, `ariane judge` and `ariane report` are described where each ticket added them.
- `docs/ariane.example.toml`: the commented example configuration for another project.

## Decided spec

- A README section "Measure Ariane on your project (shadow mode)", every command in bash (macOS, Linux) and PowerShell: prerequisites (uv, git, Claude Code logged in, a GitHub token with read access to issues), installation (ADR 0021), `ariane.toml` from the example, then per ticket `ariane start --shadow <n>`, read the clone's `work/<n>/`, `ariane judge <n> accept|reject --minutes N`, and `ariane report`.
- It states what shadow mode never does (push, pull request, status, comment, write to the user's repository) and the pass criteria over 10 tickets, and that the user keeps a short log of their current process for the comparison (spec "Measuring Ariane").
- The README status line says slice 4 is built and its gate is pending the second user's run.

## Release note

Docs: how a second user measures Ariane on their project in shadow mode.

## Acceptance criteria

- `tests/test_docs_*` (existing documentation checks) pass; a test named `test_c19_readme_shadow_*` checks that the section exists and names `--shadow`, `ariane judge`, `ariane report` in both bash and PowerShell blocks.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c19_readme_shadow` runs at least 1 test and it passes.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): README updated; no other document changes unless they contradict it.

## Out of scope

Running the gate with the second user (the owner's action).

## Related

ADR 0021, ADR 0030, spec roadmap slice 4.
