# Product brief: Report human time, gates bypassed and shadow results (C19, slice 4)

- Source: issue #99 (https://github.com/plaplanche/ariane/issues/99)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

ADR 0030 items 2, 6 and 7: the report gives the two numbers of the success measure (human time per merged pull request, steps skipped or gates bypassed) and the shadow pass criteria. Needs the report, shadow mode and judge tickets of slice 4 merged first. Spec: C19, "Measuring Ariane".

## Current state

- `ariane report` (after its ticket) reads `work/*/metrics.json` of the checkout: cost, agent time, rounds, first-pass verdict.
- Shadow tickets' metrics live in `<repo>.ariane/shadow/<n>/work/<n>/metrics.json`, with attempts and the human's judgement.
- `src/ariane/github.py` reads issues and opens pull requests; the token is `tracker.token_env`.

## Decided spec

- The report also reads the shadow clones' metrics and shows them as `shadow` lines with the judgement.
- **Human time**: for a delivered ticket, the waiting time from its pull request's opening to its merge or close, read from the tracker, plus each stop to the next `start` or `verify` of the same ticket (from `steps`); for a shadow ticket, the judged minutes. Without a token or network: "not available" for the tracker part, and the report still prints the rest.
- **Gates bypassed**, per ticket and in total: hand takeovers (`verify` metrics for its branch), blocking checks red at delivery, a pull request merged while the last review on its head is no-go (the last `go` from `ariane verify` counts).
- **Shadow totals**: tickets, accept rate (accepted / judged), not yet judged, agent push and pull-request attempts, guard violations; the line "shadow pass: yes|no" applies the spec's criteria over the last 10 shadow tickets (no attempt, no violation, at least 8 accepted).

## Release note

New: `ariane report` shows human time, gates bypassed and shadow results.

## Acceptance criteria

- Tests named `test_c19_report_human_*`, `test_c19_report_gates_*` and `test_c19_report_shadow_*` show: waiting time from a fake tracker; offline "not available"; stop to restart time; a hand takeover counted; a merged no-go counted and a later verify go not counted; shadow accept rate and the pass line for passing and failing sets.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k "c19_report_human or c19_report_gates or c19_report_shadow"` runs at least 7 tests and they pass.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `report.md` module doc and `docs/reference/cli.md` updated, README describes the report's numbers.

## Out of scope

Mastery score (slice 7), failure causes and incidents (later C19 items).

## Related

ADR 0030 (items 2, 6, 7), ADR 0020, spec C19, "Measuring Ariane".
