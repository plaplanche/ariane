# Review 1

- Reviewed commit: `57814f85d90bc29958f520f9bb81399b96e504c2`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/process.py:328`) Process-group cleanup hides surviving children from the guard

  The order is: the command exits, kill_tree kills its remaining process-group children, kill_survivors scans, then the caller consumes take_killed. Children killed by kill_tree are never counted, so leaving an ordinary background process does not stop the ticket. A read-only probe starting sleep without start_new_session returned exit 0, counted {}, and no remaining descendants. Record surviving descendants before group cleanup and include them in the metrics and guard decision. The tests cover detached children but miss this path.

- **blocking** (`src/ariane/flow.py:241`) Replay setups are not instruction-checked before checks execute

  Only the initial setup gets an immediate instruction comparison. For replay setups, setup writes files, process cleanup runs, setup checks survivors and untracked files, then replay_each executes the check and only afterwards compares instruction digests. verify._setup has the same gap. A setup can overwrite an external instruction file, the check can consume it and write results, then restore its original contents before verification; the guard accepts the run. This contradicts ADR 0031's comparison after every setup. Compare instruction snapshots immediately after each setup, before any check executes.

- **blocking** (`src/ariane/verify.py:178`) Verify discards survivor metrics on the paths that detect survivors

  The order is: command teardown kills descendants, _survivors consumes the killed list and increments an in-memory counter, then raises Refused. Metrics uses a no-op write callback, and rendering and committing metrics.json occurs only after successful replay and review. The finally block deletes the temporary records; on interruption it also consumes additional killed processes without counting them. Consequently a verify setup, check or reviewer that leaves descendants produces no persisted survivor metrics or guard-violation count. Persist stopped-run metrics before deleting records, including interruption cleanup.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  README, ADR 0031, architecture modules and the log catalogue were updated, but their promises of comparison after every setup and persisted survivor counts do not match the replay and verify paths. The untouched logs module documentation remains accurate and links to the updated catalogue.

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

  The new integrity tests exercise external instruction mutation, complete changed-file listings and truncation disclosure, and detached-process cleanup. These assertions require the change. Ariane reports the suite green; the uncovered paths are identified above.

- **not met**: The documentation the change affects is updated (C25).

  README, ADR 0031, architecture modules and the log catalogue were updated, but their promises of comparison after every setup and persisted survivor counts do not match the replay and verify paths. The untouched logs module documentation remains accurate and links to the updated catalogue.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0031's amendment records runtime-specific snapshot coverage, absent-file handling, teardown timing, survivor scanning and timeout, background git processes, and platform residuals.

## Proposed learnings (not decided)

- Proposed: inventory surviving descendants before destructive cleanup removes the evidence needed by guard decisions.
- Proposed: verify guards between separately executable setup and check stages; a final snapshot cannot detect changes restored between them.
- Proposed: test persisted metrics on refusal and interruption paths, not only successful completion.
