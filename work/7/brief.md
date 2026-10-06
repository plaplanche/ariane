# Product brief: Rename checked_in to first_pushed in the delivery flow

- Status: draft
- Approved: not yet
- Source: issue #7 (https://github.com/plaplanche/ariane/issues/7)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

In `src/ariane/flow.py`, `_TicketRun._check_and_deliver` keeps two different commits in variables whose names can be confused:

- `checked` (line 302) is the commit the checks ran on;
- `checked_in` (line 319) is the commit pushed first: the checked commit plus Ariane's "record the checks" commit.

`checked_in` reads like "the checked commit". A reader can easily take it for `checked`, for example when deciding which commit gets the commit statuses (line 345).

## Current state

`src/ariane/flow.py`, lines 319 to 346: `checked_in = git.head(self.worktree)`, then `git.push(..., checked_in, ...)`, and `pushed = checked_in` when the second push fails.

## Decided spec

Rename `checked_in` to `first_pushed` in `_check_and_deliver`, everywhere it appears. Nothing else changes: same commits, same pushes, same statuses, same messages.

## Release note

None.

## Acceptance criteria

- `checked_in` no longer appears in `src/`; `first_pushed` is used instead, with the same value and the same uses.
- Behaviour is unchanged: the existing tests pass without any change to a test file.

## Acceptance checklist

- [ ] No test file is modified.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Any other change to `flow.py` or elsewhere.
