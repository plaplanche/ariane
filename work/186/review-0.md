# Review 0

- Reviewed commit: `aac294267d680e81e9c212840901465b7220bafe`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/report.py:35`) The report cannot discover completed full replay measurements

  Delivery pushes first; after_delivery then writes full_replay metrics and commits them only in the ticket worktree. report.build scans root/work and shadow clones, but never the normal ticket worktrees. Consequently, running ariane report from the main checkout cannot count these full replays or escapes. Merging the PR does not fix this: the pushed metrics predate the full replay. Read the authoritative local ticket records, deduplicating against merged records, and add an integration test that reports from the main checkout after a sampled delivery. The current report tests place synthetic completed metrics directly where the report expects them, masking this gap.

- **blocking** (`src/ariane/full_replay.py:120`) Post-replay interruptions can overwrite the delivered outcome

  The exception boundary covers replay execution only. Metrics/report/journal writes, status and comment publication, and the final record commit occur outside it. Ctrl-C during _publish, or an OSError/GitError while recording, propagates to execute's general exception handler. That calls _stopped, writes outcome/status 'stopped', and returns a stopped or interrupted result despite the completed delivery. An in-memory probe confirmed KeyboardInterrupt escapes from _publish. Protect the entire post-delivery operation, including failure recording, so its failures cannot overwrite the delivery outcome; test interruption during publication and failure of the final commit.

- **minor** (`src/ariane/measures.py:173`) Malformed escape metrics crash the report

  The new fields are not validated by report._read, and selective_lines calls len() on any truthy escapes value. A full_replay object with ran=true and escapes=1 raises TypeError outside the report's per-file error handler. This contradicts the documented handling of wrongly typed fields. Validate escapes as a list of check names and handle malformed records consistently. An in-memory probe reproduced the exception.

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

  The new tests exercise sampling, skipped and partial checks, escape recording/redaction, publication, unchanged pushed commits, configuration and report calculations. These depend on the added behavior. Coverage misses report discovery after a real delivery and post-replay interruption handling. The supplied check results report passing tests; filesystem-writing tests were not rerun during this read-only review.

- met: The documentation the change affects is updated (C25).

  README, example configuration, affected module documentation, component sequence, schema reference and log catalogue are updated. The supplied docs-reference check passed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0056's amendment records deterministic sampling, defaults, post-delivery execution, local-only records, escape counting, stopped replay treatment and how the owner uses the rate.

## Proposed learnings (not decided)

- Proposed: Test measurement producers and report discovery together from the normal user checkout, especially when records are committed after the final push.
- Proposed: Failure isolation for post-delivery work must cover publication and persistence as well as computation.
