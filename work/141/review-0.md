# Review 0

- Reviewed commit: `52d7217d4563c69e3c8482aacd9aa0e76224b73d`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/claude_code.py:116`) Idle stops discard usage already reported by Claude Code

  The new idle branch calls SessionResult.failed(), which sets every token field to None despite TokenTally having counted streamed usage. An in-memory probe supplied 123 input, 45 output, 6 cache-read and 7 cache-write tokens before an idle stop; the result reported every category as 'not reported'. Metrics then writes those null values, followed by the journal recording the same incorrect usage. This violates C5's requirement to record reported tokens and affects sessions newly stopped by the default idle limit. Preserve tally.parts in the timeout result, leaving unreported cost unset, and add assertions for usage to the idle-session tests.

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

  The new tests exercise idle tree termination, continuing activity, configuration validation, and both requested runtimes' journal and stop summaries. These rely on APIs and behavior absent before the change. Ariane reports the suite passing; usage preservation remains untested.

- met: The documentation the change affects is updated (C25).

  README, example configuration, generated schema, and architecture documentation for every changed module are updated. Ariane reports the documentation-reference check passing.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0045 records the default and short-total-limit exception, event-stream activity measurement, timeout classification, summary format, owner configuration, and the reported installed Claude Code version supporting the shell-timeout rationale.

## Proposed learnings (not decided)

- Test interrupted sessions with usage events before the interruption, asserting that reported tokens survive into the result, metrics and journal.
