# Review 0

- Reviewed commit: `9cdc6910dc814b011bbf853c5d6d8f047a9a2035`
- Reviewer model: gpt-6-astra
- Verdict: **go**

## Findings

None.

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

  Eleven test_c11_run_slot_* tests cover environment propagation, journal and verify records, contention with a child process, exhaustion before branch/tree creation, release on completion/stop/KeyboardInterrupt, and directory creation. The propagation and contention assertions require this implementation. Ariane reports all blocking checks passed; I did not rerun tests because this review permits reads only. Ordering traced: start creates/acquires the ticket lock, creates/acquires a slot lock, writes the run registration, fetches, optionally saves restart objects/refs and removes old trees, creates the branch/tree, runs setup, writes journal/status/metrics and commits, runs agents and replay/review trees, writes check/review records, then commits delivery records, pushes, opens the PR, publishes statuses and commits local final records. Registry cleanup precedes slot release. Shadow acquires the slot before clone/config/ref/checkout writes, then follows the shared execution path and commits its local outcome before release. Verify acquires the slot before temporary directories or worktrees, runs setup/checks/review, writes and commits records, removes temporary trees/files and handles survivor/stopped-metrics cleanup before release. Stop recording and interruption cleanup also occur while held. Slot selection uses the OS lock itself as the atomic availability check; concurrent contenders cannot both acquire the same lock.

- met: The documentation the change affects is updated (C25).

  README documents ARIANE_SLOT, exhaustion and PowerShell/bash port examples. Architecture documents cover slots, context, flow, restart, shadow, verify, collaborations and the outside-repository lock files. Existing ticket.started gains slot detail without introducing a new log type. Setup, checks, runtime sessions and commit calls retain the injected environment value.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0050 records the slot range, lock location and primitives, acquisition/lifetime ordering, environment injection, verify record format, per-user home scope and rejected resource-lock alternative. No additional undocumented behavioral choice was identified.

## Proposed learnings (not decided)

- Use the OS lock acquisition itself to decide availability, and retain the descriptor through final records and cleanup.
- Inject run-owned environment values after filtering inherited variables; test both inherited-value replacement and contention from another process.
