# Product brief: Run up to two fix rounds after a negative review, then open a draft pull request (C10)

- Source: issue #34 (https://github.com/plaplanche/ariane/issues/34)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

C10: at most two automatic fix rounds after a negative review, then the ticket goes to the human. ADR 0010 (kept by ADR 0016): after the second fix round, a draft pull request carries the findings with status `needs a human`.

## Current state

After the reviewer issue, a `no-go` stops the ticket with status `needs a human` and nothing is pushed.

## Decided spec

- On `no-go`, a fresh implementer session gets the issue and the review's findings (untrusted data) and fixes them in the ticket's working tree; Ariane commits its work, replays the checks in a clean tree and reviews again (`review-1.md`, `review-2.md`).
- At most two fix rounds (three reviews in all). Blocking checks failing after a fix round count as a negative round.
- If the last review is still `no-go`, Ariane pushes the branch once and opens a draft pull request whose body carries the last verdict and findings, with status `needs a human` and next action "finish by hand, then run `ariane verify`".
- The journal records each round's sessions and verdict.

## Release note

Added: up to two automatic fix rounds after a negative review, then a draft pull request.

## Acceptance criteria

- Tests named `test_c10_fix_round_*` with a fake runtime show: `no-go` then `go` delivers a normal pull request after one fix round; three `no-go` give a draft pull request with the findings and exactly three reviews; the fix session receives the findings; the branch is pushed once in both cases.
- `InMemoryTracker` records whether a pull request is a draft.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c10_fix_round` runs at least 3 tests and they pass.
- [ ] All checks in CLAUDE.md pass.
- [ ] CLAUDE.md's "Developing Ariane with Ariane" no longer says "no fix rounds yet" for the review enforced by Ariane (C10).
- [ ] Definition of done, documentation (C25): `docs/architecture/` updated (`flow`, `review`, `delivery`, `tracker` and `github` modules as touched, the level 3 sequence diagram with the fix rounds); the log catalogue and `docs/reference/` regenerated.

## Out of scope

`ariane verify` (next issue), the learnings checkpoint (C18).

## Related

ADR 0016, ADR 0010, spec C10.
