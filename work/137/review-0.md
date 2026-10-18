# Review 0

- Reviewed commit: `efef3787b04c79f1c6b0a04c8fca6a3097ed274a`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`docs/architecture/modules/replay.md:21`) C25 documentation is incomplete for replay and verify

  Both this page and docs/architecture/modules/verify.md remain unchanged despite new behavior in their modules. Document that each review counts the reviewed commit range excluding work/, passes that count into reviewer selection and metrics, and records the selected model. For replay, explain that the count is recomputed each round. Rule 11 explicitly requires updating every touched module's documentation; coverage in review_session.md does not complete this requirement.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  README, example configuration, schema, ADR and six module pages were updated, but the affected replay and verify module pages omit their new responsibilities.

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

  The new test_c10_small_review tests exercise small versus large selection, model/budget/timeout overrides, prompt narrowing, configuration rejection, work/ and binary exclusions, metrics, and verify. These exercise behavior absent before this change. Ariane reports the suite passed; I did not rerun tests because their fixtures write files and create commits.

- **not met**: The documentation the change affects is updated (C25).

  README, example configuration, schema, ADR and six module pages were updated, but the affected replay and verify module pages omit their new responsibilities.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0046 records the threshold mechanism, different-model requirement, inherited settings, idle-timeout handling, cap-key attribution and selected-model records.

## Proposed learnings (not decided)

- Proposed: add a regression test where a fix round crosses max_lines, proving that reviewer settings and recorded model switch on the next round.
