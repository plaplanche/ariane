# Review 0

- Reviewed commit: `daac118c130cfd7c87443bab8ef78010858e32b9`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/process.py:215`) Concurrent workers can erase a survivor violation before either guard sees it

  take_killed() copies and clears _killed without the lock now protecting survivor scans. Interleaving: worker A copies an empty _killed; worker B kills a surviving child, emits process.survivors_killed and updates _killed under _lock; A clears that new entry and returns empty; B's subsequent take_killed() also returns empty. Both flow.survivors() and verify._survivors() decide whether to stop from these returned records, so the replay can proceed despite a guard violation. A controlled in-memory interleaving reproduced both empty results. Protect the copy-and-clear operation with the same lock and add a regression test that inserts a survivor record between those steps.

- **minor** (`docs/architecture/modules/logs.md:27`) The touched logs module's architecture documentation was not updated

  The change adds ticket.checks.parallel and regenerates docs/logs.md, but leaves the mapped module document unchanged. Project rule 11 explicitly requires updating the module documentation for each touched module. Describe the new replay journal entry and reference ADR 0052.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  README, the requested architecture documents, example configuration, generated schema and log catalogue are updated. The mapped docs/architecture/modules/logs.md is unchanged.

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

  The new test_c9_parallel_checks tests exercise configuration, timing, result order, distinct slots, cancellation, slot exhaustion and verify integration; these depend on the new behavior. Ariane reports the suite passing. The survivor-accounting interleaving identified above lacks coverage. I did not rerun filesystem-writing tests in this read-only review.

- **not met**: The documentation the change affects is updated (C25).

  README, the requested architecture documents, example configuration, generated schema and log catalogue are updated. The mapped docs/architecture/modules/logs.md is unchanged.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0052 records the configuration default, threads rather than processes, slot allocation and fallback, result ordering, serialized tree mutations, and cancellation design.

## Proposed learnings (not decided)

- Proposed: When introducing worker threads, make shared guard-record consumption atomic with record production; locking producers alone does not prevent lost violations.
- Proposed: Test safety-critical interleavings with synchronization barriers, alongside elapsed-time and happy-path concurrency tests.
