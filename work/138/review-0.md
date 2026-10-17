# Review 0

- Reviewed commit: `ff412aacccf8037fe1f4e5ca64c1a83d06d76dc0`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`docs/architecture/modules/github.md:28`) Workflow diagram not updated for the events retry

  The ticket's documentation item asks for `docs/architecture/modules/github.md` (behaviour and workflow) to be updated. Only the 'Behaviour and errors' bullet changed. The mermaid Workflow still shows one decision `{label added by a writer, issue unchanged since?}` -> no -> raise IssueRefused. It has no loop that reads the events again after 1, 2, 4 and 8 s, and it doesn't show that only the two lag refusals are retried. This leaves an explicitly named item of the definition of done (C25, rule 11) unmet.

- **minor** (`tests/test_c21_issue_gate.py:306`) No test for the `github.label_event_retry` log record

  The spec requires an info log that says which read is retried and why. None of the four new tests checks that it is emitted (for example with caplog), how many times (4 when the event never comes, 0 for absent label or reader), or that it gives the reason. The log could be dropped or renamed without any test failing. The `docs: references` check only shows that the type is declared and catalogued.

- **minor** (`tests/test_c21_issue_gate.py:306`) Exhausted 'changed after the label' retry path not tested

  The tests cover exhausting the 'no event' refusal (5 reads, sleeps 1, 2, 4, 8) and recovering from 'changed after'. No test exhausts the 'changed after the label' path to check that the refusal text is unchanged after 5 reads. That is the more security-relevant branch: an edit after the label must still be refused.

- **minor** (`docs/adr/0032-issue-gate.md:61`) Amendment format inconsistent with the existing amendment

  The existing amendment has a heading with a date and ticket (`## Amendment (2026-10-14, #111): REST only`). The new line is a bare paragraph. It reads as part of the #111 amendment and gives no date or reference to #138. The ticket asked for a one-line amendment, so the content is fine, but a heading such as `## Amendment (…, #138): events lag` would keep the ADR traceable.

- **minor** (`docs/architecture/modules/github.md:45`) Constructor's new `sleep` parameter not in the module's public API or code view

  `GitHubTracker(..., sleep=time.sleep)` is a new injectable parameter of the public class. It appears only in the behaviour prose and not in the Public API table or the class diagram.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  These are updated: the README paragraph (waits up to 15 seconds), `docs/logs.md` (the `docs: references` check passes), the ADR 0032 amendment, and the behaviour bullet in `docs/architecture/modules/github.md`. The Workflow diagram in github.md, which the ticket names explicitly, is unchanged. `docs/architecture/modules/logs.md` needs no change: it lists no log types, only links the generated catalogue.

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

  There are four new `test_c21_issue_gate_retry_*` tests, one for each acceptance criterion. Without the change they all fail: `GitHubTracker` has no `sleep` parameter, so `gate(...)` raises TypeError, and without the retry the lag cases would be refused after one read. The tests check the sleeps [1, 2], [1, 2, 4, 8], [] and [1], as well as the number of events and issue reads. The log record is not tested (minor).

- **not met**: The documentation the change affects is updated (C25).

  These are updated: the README paragraph (waits up to 15 seconds), `docs/logs.md` (the `docs: references` check passes), the ADR 0032 amendment, and the behaviour bullet in `docs/architecture/modules/github.md`. The Workflow diagram in github.md, which the ticket names explicitly, is unchanged. `docs/architecture/modules/logs.md` needs no change: it lists no log types, only links the generated catalogue.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket fixes the delays, the retry conditions, the log, the injectable sleep and 'No ADR, a one-line amendment to ADR 0032'. That amendment is present. The remaining implementation details (an internal `_EventsLag` subclass, the `_read_events` and `_judge` split) don't change behaviour.

## Proposed learnings (not decided)

- When a ticket names a module doc section such as 'behaviour and workflow', check each named section: the mermaid workflow is often left stale while the prose is updated.
- A new technical log type required by the spec should have a test that it is emitted; catalogue checks only prove it is declared.
- Keep ADR amendments in the existing heading format (date, ticket, title) so they stay traceable.
