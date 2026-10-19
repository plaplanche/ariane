# Review 1

- Reviewed commit: `db724b9198fa3103d1fbd8d260a2f6d7ab332fb2`
- Reviewer model: gpt-6-astra
- Verdict: **go**

## Findings

- **minor** (`tests/test_c11_tracking_ref.py:157`) Negative tests do not isolate the ancestry requirement

  The backwards and sibling cases leave the remote base unchanged, so remote equality rejects them before is_ancestor runs. Removing the ancestry condition could therefore leave these tests green. Add a case that first accepts A→B, then moves both the remote base and tracking ref to C, where C descends from A but is a sibling of B. The existing remote check against A permits C; the tracking guard must reject B→C.

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

  Ten parametrized cases cover successful fetches, repeated advances, rejected moves, unchanged review diffs and delivered ranges, and parallel verification. The successful-fetch cases would stop under the original guard. Ariane reports the full test suite passing; I did not rerun tests because their fixtures write files. Ordering inspected: verification performs survivor cleanup and any associated metrics/log writes; under guard_lock it reads the snapshot, checks branch/history, performs registry reclamation (append ended history before deleting stale entries), filters permitted foreign changes, reads the remote witness, checks ancestry, then updates the in-memory guard. The subsequent remote check may fetch objects and write FETCH_HEAD; successful verification then writes its logs and journal. Git subprocesses emit command/start/exit logs throughout. Setup uses the same locked comparison before returning success. Delivery writes status/journal and a local record commit, checks replay equivalence, runs the final guard and URL checks, pushes, records the push, opens the pull request, publishes statuses, then writes and commits the local pull-request record. No newly introduced ordering violation was found.

- met: The documentation the change affects is updated (C25).

  README, ADR 0017, and the flow, git, runs and shadow module documentation describe the tolerance, remote witness, lock, preserved start base and shadow behavior. No event definitions changed, so the log catalogue requires no update. Ariane reports documentation reference checks passing.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0055 records the fresh remote witness, advancing the guard baseline, serialization of snapshot reads and updates, rejection of other changes, preservation of the start base, and unchanged shadow/verify behavior. It also records alternatives and tradeoffs.

## Proposed learnings (not decided)

- Proposed: Test remote equality and ancestry independently; mismatched remote commits can mask a missing ancestry check.
- Proposed: When verification advances a shared baseline, serialize the snapshot read together with comparison and baseline update.
