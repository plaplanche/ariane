# Review 0

- Reviewed commit: `8d1ffe4aa01a8c25023b36ae81c4fcb4f65dd99e`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/review_history.py:220`) An explicitly unresolved blocker can pass review

  Reproduced with a round-1 answer containing verdict='go', findings=[], and earlier=[{finding:'0.1', answer:'still open'}]. Validation returns no errors, and settled_round returns go=True with recurring_findings=1. The unresolved blocker never enters settled.findings or changes the verdict. Consequently flow ends the fix rounds and Delivery opens a non-draft PR, omitting both circled notices. This makes the review check pass wrongly. After accepting the answer, the path writes the review record and verdict journal, writes delivery metrics, logs delivery and writes status, restores and commits records, checks the replay and delivery guards, pushes, logs the push, opens the non-draft PR, logs delivery, optionally labels it, publishes check statuses, and writes and commits the final status. None of those guards checks the unresolved earlier blocker. Reject the contradictory answer or carry the unresolved finding into settlement before deciding whether to continue or deliver; add a regression test.

- **blocking** (`src/ariane/review_history.py:207`) Repeated observations of one blocker inflate recurring_findings

  Reproduced one unchanged blocking finding reported in rounds 0, 1 and 2. Round 1 marks 0.1 'still open'; round 2 marks both 0.1 and 1.1 'still open' and reports the same single current blocker. settled_round produces count=2 and two separate chains because ends is keyed by historical finding ID. The ticket requires the count of recurring blocking findings in the last round, not the number of historical observations. The incorrect count flows into metrics.json, ariane report and the draft body. Associate still-open answers with current blocking findings and deduplicate by those findings, preserving their history as a chain. Test one blocker persisting through all three rounds.

## Definition of done

- met: check lint passes

  Replayed by Ariane: exit 0.

- met: check format passes

  Replayed by Ariane: exit 0.

- met: check types passes

  Replayed by Ariane: exit 0.

- met: check tests passes

  Replayed by Ariane: exit 0.

- met: check file length passes

  Replayed by Ariane: exit 0.

- met: The change is covered by tests that fail without it.

  Seven named test functions, including six validation parameter cases, cover prompt history, parsing, draft/journal reporting, metrics and report output. Their new-behavior assertions fail without this change. Ariane reports the suite passed; I inspected the tests and ran read-only in-memory reproductions, rather than rerunning filesystem-writing integration tests. The two findings identify missing regression cases.

- met: The documentation the change affects is updated (C25).

  README, all requested module documents, the new review_history module document, component diagrams, review-answer schema and log catalogue are updated. Ariane reports the generated-reference check passed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0059 records history for both sessions, identifiers, the three answers and caused indexes, validation, recurrence reporting, run-local history, and retaining the existing round limit and hand-over rule.

## Proposed learnings (not decided)

- Proposed: Every structured field that asserts an unresolved blocker must participate in verdict settlement.
- Proposed: Count distinct current findings rather than historical observations; test one finding persisting across every round.
