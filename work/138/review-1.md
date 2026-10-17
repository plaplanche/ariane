# Review 1

- Reviewed commit: `cffca86058627b0406adeb4ac8f98122054f91c5`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/logs.py:97`) Log catalogue meaning covers only one of the two retry reasons

  The declared meaning of `github.label_event_retry` is "The issue's label events are read again: not listed yet." The log is also emitted when a `labeled` event is listed but the issue's `updated_at` is later than it (reason "the issue changed after the last listed label event"). A neutral wording such as "The issue's label events are read again: they may lag behind the issue." would fit both cases. The record's message does give the actual reason, so this is only about how accurate the catalogue is.

- **minor** (`tests/test_c21_issue_gate.py:392`) Logging test checks the reason for only one of the two retry cases

  `test_c21_issue_gate_retry_logs_each_retried_read_with_its_reason` checks the message only for "no event lists the label". No test checks the "changed after" reason text. The behaviour is covered by `..._refuses_a_change_after_the_label_after_five_reads`, but its log message is not.

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

  tests/test_c21_issue_gate.py adds six `test_c21_issue_gate_retry_*` tests that use the fake server and a recording `sleep`. They cover: accepted from the third read with sleeps [1, 2]; refused with today's message after 5 events reads and sleeps [1, 2, 4, 8], with the issue read once; absent label or reader refused after one events read and no sleep; re-added label listed on the second read accepted; changed-after refused after 5 reads; one retry log per retried read. All of them fail on the base commit: `GitHubTracker` takes no `sleep` argument there, and the base code refuses on the first read.

- met: The documentation the change affects is updated (C25).

  docs/architecture/modules/github.md covers the behaviour, the workflow flowchart with the retry loop, the constructor and the class diagram. docs/logs.md lists `github.label_event_retry`, matching the logs.py declaration, and the docs: references check passes. The README label paragraph says Ariane waits up to 15 seconds. ADR 0032 has the one-line amendment. docs/architecture/modules/logs.md, flagged as untouched, needs no change: it describes the logs module API and points to the generated catalogue, and adding a declared type changes neither.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket fixes the delays (1, 2, 4, 8), which outcomes are retried, that the issue is not read again, the log type and level, and the injectable sleep. It explicitly asks for no new ADR, only an amendment to ADR 0032, and the diff adds that amendment. Implementation details such as the private `_EventsLag` subclass are not spec choices.

## Proposed learnings (not decided)

- When a log type is emitted for several reasons, write its catalogue meaning to cover all of them, not just the most common one.
- Retry loops over a lagging GitHub endpoint: re-read only the lagging resource, decide on the last read, and keep every other refusal on the first read. Tests should assert the read counts per path as well as the sleep sequence.
