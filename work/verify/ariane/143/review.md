# Review 0

- Reviewed commit: `05997e1ef16d5c6af2c9a01e63ff13e385472b4c`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/replay.py:118`) Ctrl-C before a worker starts causes an indefinite cleanup wait

  The completion event is appended to started before thread.start(). If Ctrl-C arrives after that append but before the native thread is launched, KeyboardInterrupt bypasses except Exception. The outer handler cancels existing workers and calls _wait(started, interruptible=False), but no worker exists to set this event. Replay hangs indefinitely and ignores subsequent Ctrl-C. The ordering is: acquire slot locks, write the parallel journal entry for start, register the completion event, interrupt before launching its worker, cancel existing workers, wait forever; slot release and outer cleanup are never reached. A read-only fault-injection probe making Thread.start raise KeyboardInterrupt confirmed that cleanup receives an unset event with interruptible=False. Track whether a worker actually launched without losing protection for interruption after launch, and add a regression test for interruption before launch.

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

  The new tests exercise timing, declared report order, distinct slots, reduced slot availability, setup failure, interruption, configuration validation and verify integration. These depend on the new functionality. Ariane reports passing checks; I did not rerun the filesystem-writing suite. The startup interruption case identified above is missing.

- met: The documentation the change affects is updated (C25).

  README, the example configuration, component sequences, affected module documentation, generated configuration schema and log catalogue are updated. The supplied docs-reference check passed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0052 records the configuration default, threads versus processes, slot allocation and fallback, ordered results, serialized tree operations, process protection and cancellation strategy. ADR 0050 identifies the extension to its slot policy.

## Proposed learnings (not decided)

- Proposed: Test interruption at worker-launch boundaries as well as during execution; every completion event awaited during cleanup must have a guaranteed producer.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
