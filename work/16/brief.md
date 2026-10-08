# Product brief: Move the delivery out of the ticket flow into its own module (pure move)

- Status: draft
- Approved: not yet
- Source: issue #16 (https://github.com/plaplanche/ariane/issues/16)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Slice 2 adds a reviewer, fix rounds and a learnings checkpoint to the ticket flow (ADR 0009). `src/ariane/flow.py` is 403 lines and the limit is 600 (ADR 0004); the review loop will not fit. The spec asks for refactors done as pure moves first, behaviour changes after.

## Current state

- `src/ariane/flow.py:299` `_TicketRun._check_and_deliver` replays the checks, records them, pushes, opens the pull request, records the delivery, pushes again and publishes the statuses.
- `src/ariane/flow.py:353` `_publish_statuses` and `src/ariane/flow.py:377` `_pull_request_body` are only used by that delivery.
- `src/ariane/flow.py:387` `_commit_record` is used by both the flow and the delivery.

## Decided spec

Move the delivery out of `src/ariane/flow.py` into a new module `src/ariane/delivery.py`, as a pure move:

- `delivery.py` holds the part of `_check_and_deliver` that starts after the blocking checks passed (status `delivering`, record commit, push, pull request, delivery record, second push, statuses) and the code of `_publish_statuses` and `_pull_request_body`.
- `flow.py` keeps the check replay and the stop on blocking failures, then calls the delivery and returns its `Outcome`.
- What the delivery needs from the run is passed explicitly (for example a small object or arguments); no import cycle (`delivery.py` must not import `flow.py`'s `_TicketRun`).
- No behaviour change: same commits, same pushes, same messages, same journal text, same exit codes.

## Release note

None (internal refactor).

## Acceptance criteria

- `src/ariane/delivery.py` exists and `python -c "import ariane.delivery"` succeeds.
- `src/ariane/flow.py` no longer defines `_publish_statuses` or `_pull_request_body`.
- No file under `tests/` is changed, and the whole test suite passes.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `src/ariane/delivery.py` exists.
- [ ] `src/ariane/flow.py` has no `def _publish_statuses` and no `def _pull_request_body`.
- [ ] `git diff --stat` shows no change under `tests/`.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Any behaviour change, including the single push (a later issue), and any other part of `flow.py`.

## Related

ADR 0009 (issue 1 of slice 2), ADR 0006.
