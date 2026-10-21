# Product brief: Fix rounds see the earlier rounds, and a draft says when the review circled on one problem (C10, C19)

- Source: issue #199 (https://github.com/plaplanche/ariane/issues/199)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

A fix round today is a fresh implementer session that sees only the last review's findings (`review.py`, `context.implementer_prompt(fix_round=…)`), and the reviewer of the next round sees only the new head. On a benchmark ticket about concurrent writes (results, releases and revocation racing on the same lease), the review was `no-go` on all three rounds, each time on a race in the same file: round 0 found a check-then-write split, round 1's fix moved the write but left the race, round 2's fix added an intermediate state that broke the other conditional writes that relied on the old invariant. Every finding was real and the final fix was small, but neither session saw the history: the implementer did not know its previous fix had caused the new finding, and the reviewer did not say "same problem, third time". The ticket ended as a draft pull request after two rounds with nothing telling the human that the rounds had circled on one design question. Spec: C10 (review, at most two fix rounds), C19 (measurement).

## Current state

- `flow.py` runs up to `MAX_FIX_ROUNDS = 2`; each fix session gets the last `Settled` findings and the blocking checks still red.
- The reviewer prompt holds the diff, the ticket and the definition of done; no earlier review.
- `work/<n>/review-<round>.md` keeps every round, but nothing reads them back.
- `metrics.json` has `rounds` and the first-pass verdict; the pull request body shows only the last review.

## Decided spec

- **History to the fix session.** A fix round's prompt lists the blocking findings of every earlier round of this ticket (round number, file, title), then the current ones in full, inside the same untrusted-data envelope. It adds one rule: when a fix changes a design (a new state, a moved write, a changed invariant), re-check every place that relied on the old one, and say in the summary which places were checked.
- **History to the reviewer.** From round 1 on, the reviewer prompt lists the earlier rounds' blocking findings, and the reviewer answers, for each, `fixed`, `still open` or `replaced` (fixed, but the fix caused a new blocking finding) in a new optional `earlier` array of the review answer (`review-answer.schema.json` and the parser in `review.py`). A blocking finding the reviewer marks `still open` or that it ties to a `replaced` one is **recurring**.
- **Recurring rounds are said, not acted on.** When the last round has a recurring blocking finding, the journal records `Review circled on <file>` and the draft pull request body says, above the review table, that the rounds circled on the same design question and lists the chain (round, finding). `metrics.json` records `recurring_findings` (count) per ticket and `ariane report` shows it. The number of rounds and the hand-over rule do not change.
- ADR (next free number): why history is given to both sessions, the three answers, and why recurrence is reported instead of stopping earlier or adding rounds.

## Release note

Changed: a fix round and the next review see the earlier rounds' findings; when the rounds circle on the same problem, the draft pull request and `ariane report` say so.

## Acceptance criteria

- Tests named `test_c10_fix_history_*` show:
  - a round-2 fix prompt lists the round-0 and round-1 blocking findings and the re-check rule, inside the untrusted envelope;
  - the round-1 reviewer prompt lists round 0's blocking findings, and an answer with `earlier` entries is parsed; an unknown value or a missing entry is refused like any other malformed answer;
  - an answer without `earlier` on round 0 is accepted;
  - a `still open` or `replaced` entry on the last round puts the "circled" line in the draft pull request body and the journal, and `recurring_findings` in `metrics.json`; a ticket whose rounds fixed everything has none;
  - `ariane report` shows `recurring_findings`.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c10_fix_history` runs at least 5 tests and they pass.
- [ ] A new ADR records the decision.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/review.md`, `context.md`, `flow.md`, `delivery.md`, `metrics.md`, `report.md`; `docs/reference/review-answer.schema.json` and `docs/logs.md` regenerated; README where it describes the fix rounds.

## Out of scope

- Changing `MAX_FIX_ROUNDS` or handing over before the second round.
- The reviewer writing the fix itself (it stays read-only).
- Escape rates per model pair (#196).

## Related

#196 (review escapes and stop categories), #193 (richer pull request body), #162 (one review round refactor); spec C10, C19.
