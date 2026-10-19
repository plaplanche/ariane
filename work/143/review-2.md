# Review 2

- Reviewed commit: `7fd19a0a2de536592da7c5592c7e62afdaa8676e`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/replay.py:121`) Worker startup failure releases slots while earlier workers still run

  If a later Thread.start() raises RuntimeError (for example, thread exhaustion), the exception bypasses cancellation and waiting: only KeyboardInterrupt receives that cleanup. The order becomes: acquire slots; start worker A; A creates its tree and starts setup; starting worker B fails; replay_each resumes threads and raises; slots.several releases the slots; A continues running setup/checks and creating further trees. Another run can acquire A's slot while A still uses its resources. A read-only, in-memory reproduction confirmed worker_alive_on_return=True and no removal at return; the surviving worker subsequently processed both queued checks. Cancel and await all successfully launched workers on every startup exception before propagating it, and add a regression test.

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

  New tests cover timing, declared report order, distinct slots, interruption, setup failure, slot scarcity, configuration, and verify integration. These depend on the new behavior and APIs. Ariane reports the suite passing; worker startup failure is an uncovered case. I did not rerun the filesystem-writing suite in this read-only review.

- met: The documentation the change affects is updated (C25).

  The README, requested module documents, component sequences, commented example configuration, schema reference, and log catalogue are updated. The documented cleanup guarantee needs the blocking fix.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0052 records the configuration default, threads versus processes, worker scheduling, slot allocation and scarcity, ordered results, process coordination, cancellation, and cleanup waiting.

## Proposed learnings (not decided)

- Proposed: Test partial worker-pool startup failure, not only failures after every worker has started.
- Proposed: Release resource leases only after all successfully launched workers have completed cleanup, on every exception path.
