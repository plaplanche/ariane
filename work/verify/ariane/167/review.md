# Review 0

- Reviewed commit: `f17d813e73580c2a7b62fd060481dffcc6fc0cd5`
- Reviewer model: gpt-6-astra
- Verdict: **go**

## Findings

- **minor** (`src/ariane/review.py:238`) Quoted binary paths are malformed in the truncation list

  The header fallback assumes unquoted a/path b/path syntax. A binary diff for a filename containing a tab has quoted headers; a read-only reproduction returned '/a\\tb.bin"' instead of the correct quoted path. This affects the prompt's missing-hunks list and journal. The full name-status list still identifies the file, so this is nonblocking. Parse Git's quoted header syntax and add coverage for binary and mode-only changes with quoted filenames.

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

  New integration tests assert external instruction-file changes stop before review, large diffs retain every changed path and disclose truncation in delivery, and detached Linux descendants are killed and counted. Additional tests cover setup-before-check ordering, interruption, and subreaper failure. These assertions depend on the new behavior. Ariane reports all checks passing; I did not rerun the filesystem-writing suite in this read-only review.

- met: The documentation the change affects is updated (C25).

  README, ADR 0031, the affected architecture descriptions, and the log catalogue document the new guarantees and platform residuals. The untouched shadow.md remains accurate: shadow.py only relocates its existing error-description helper, and its documentation delegates the ticket flow to flow.md.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0031's amendment records snapshot scope and timing, Codex coverage, survivor teardown and its deadline, timeout handling, stopped-metrics locations, and verify's truncation record.

## Proposed learnings (not decided)

- Proposed: test Git path parsing with quoted filenames, binary changes, and mode-only changes rather than only ordinary text diffs.
- Proposed: preserve the tested ordering of baseline snapshot, setup execution, survivor cleanup and guard comparison, then check execution.
