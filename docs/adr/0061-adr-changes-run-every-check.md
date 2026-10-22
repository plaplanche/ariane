# 0061. A pull request that changes an ADR runs every check

- Status: accepted
- Date: 2026-10-21
- Capabilities: C25, C11; amends the documentation-only rule of 0005

## Context
Tickets running side by side can each add an ADR with the same next free number.
`tests/test_c25_adr_numbers.py` finds the collision on the second pull request's merge with the
base, but only if pytest runs there. Under 0005, CI skips every check for a pull request whose
changed paths are all documentation, and `docs/adr/` counted as documentation, so a
documentation-only pull request adding a colliding ADR passed without the test.

## Decision
`scripts/docs_only.py` no longer counts a file under `docs/adr/` as documentation, except
`docs/adr/README.md`. A pull request that adds, changes or removes an ADR therefore runs every
check, the ADR number test included. The workflow itself is unchanged.

## Consequences
An ADR-only pull request takes the few minutes of a full CI run. Every other documentation-only
pull request still skips the checks.

## Alternatives considered
- A separate workflow step running only the ADR check on documentation-only pull requests:
  faster, but it changes `.github/workflows/ci.yml`, which a cloud session cannot push, and
  adds a second way to run one test.
- Leaving it to `ariane update`: a pull request merged by hand would not go through it.
