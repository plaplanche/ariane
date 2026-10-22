# Product brief: ADR numbers stay unique when tickets run in parallel: a test, and the collision rule (C25)

- Source: issue #238 (https://github.com/plaplanche/ariane/issues/238)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

On 21 October two tickets ran in parallel and each added an ADR with the "next free number": #199 (`0059-review-history-and-recurring-findings.md`) and #223 (`0059-next-ticket-proposal.md`). Each branch alone was consistent, so neither replay saw it; the duplicate was found by hand during #223's takeover and renumbered 0060 (pull request #237). With `ariane next` (#223) starting tickets side by side, this will happen again. Spec: C25 (documentation), CLAUDE.md rule 2 (ADRs), C11 (parallel tickets).

## Current state

- `docs/adr/README.md` says ADRs are "numbered in order"; nothing checks that two files do not share a number.
- The CI runs on a pull request's merge with the base branch (`pull_request` event), so a check that sees `docs/adr/` would see both files once the first pull request is merged; `ariane update` replays the checks on the merge too.

## Decided spec

- **A test.** `tests/` gets a test that fails when two files in `docs/adr/` share their four-digit number, naming both files, and when a file there does not start with four digits and a dash (the README excepted). It runs in the normal `pytest` check, so the second pull request's CI (on the merge with the base) and an `ariane update` replay fail on a collision.
- **The rule.** `docs/adr/README.md` says how a collision found at merge is resolved: the ADR of the later pull request takes the next free number, and every reference that pull request added to its old number is renumbered; the earlier ADR keeps its number.
- No change to `ariane next` (treating `docs/adr/` as shared would stop any two tickets that each add an ADR from running side by side).

## Release note

None (repository check).

## Acceptance criteria

- Tests named `test_c25_adr_numbers_*` show: the repository's `docs/adr/` passes; a folder with two `0059-*.md` files fails and names both; a misnamed file fails.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c25_adr_numbers` runs at least 3 tests and they pass.
- [ ] `docs/adr/README.md` states the collision rule.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/adr/README.md`; no module documentation affected (tests only).

## Out of scope

- Reserving ADR numbers across running tickets.

## Related

#199, #223, pull request #237 (where the collision was found); spec C25.
