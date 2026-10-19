# Review 1

- Reviewed commit: `6cea7b3eeedcf5b48c77e2e2ae85ba076bc7ddad`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/replay.py:127`) Ctrl-C can release slots before workers finish cleanup on Python 3.11

  On supported CPython 3.11, KeyboardInterrupt during Thread.join can mark the thread stopped even though its target is still running. The subsequent is_alive-based join therefore skips it. I reproduced this with in-memory replay callbacks on Python 3.11.17: replay_each raised KeyboardInterrupt before the first worker's remove callback ran; cleanup completed later. The same reproduction waited correctly on Python 3.13.16. The failing order is: worker runs; Ctrl-C interrupts join; stop_all cancels commands; the second join incorrectly considers the worker finished; process.resume clears cancellation; the caller releases slot locks and writes the replay journal; the worker subsequently verifies/removes its tree. Another run can acquire that slot before cleanup finishes, and process exit can terminate the daemon worker with its tree still present. Wait for an explicit worker-completion signal set after cleanup, rather than relying solely on interruptible Thread.join/is_alive, and add a regression test on Python 3.11 that delays cleanup across Ctrl-C.

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

  The new test_c9_parallel_checks tests exercise concurrency, declared result order, distinct slots, reduced capacity, cancellation, configuration validation, and verify integration. These depend on the new behavior. The reported checks passed; the reproduced Python 3.11 cleanup race remains uncovered.

- met: The documentation the change affects is updated (C25).

  README, the requested module documentation and component sequences, additional affected module pages, the example configuration, generated schema, and log catalogue are updated.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0052 records the configuration key, threads versus processes, worker allocation, slot sharing, result ordering, serialized tree operations, process protection, and cancellation design; ADR 0050 references the extension.

## Proposed learnings (not decided)

- Proposed: test interruption and cleanup on the minimum supported Python version; an interrupted Thread.join is not reliable proof of worker completion on Python 3.11.
- Proposed: release worker resource leases only after explicit confirmation that each worker's cleanup has completed.
