# Review 0

- Reviewed commit: `3e52c6c3995826318ba477dae83500ebab4f5c0a`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/flow.py:189`) Initial setup can poison the instruction-file baseline

  The order is: run setup (which can write external instruction files), create the ticket records, write metrics and journal/status, commit the records, then take the guard snapshot. A setup that writes ../CLAUDE.md or the reviewer's user-level CLAUDE.md is therefore accepted into the baseline and reaches review undetected. This contradicts the README and ADR guarantee that setup-written instructions stop the ticket. Snapshot instructions before setup and compare immediately afterwards; add a setup-specific regression test.

- **blocking** (`src/ariane/verify.py:198`) Failure and interruption paths skip survivor cleanup

  A verify setup can spawn a detached child and exit nonzero. _setup raises Refused before _unchanged runs; replay_each then removes the worktree and verification exits without killing the child or recording it. Successful setup also runs the check before its survivors are inspected, letting a background setup process modify files concurrently with the check. Likewise, KeyboardInterrupt during an agent or check bypasses the normal post-session callback; process._execute only kills the original process group. Put survivor cleanup in guaranteed teardown after each setup, check and session, including failures and interruptions, before further commands or tree removal. Cover these paths with tests.

- **blocking** (`src/ariane/process.py:134`) A descendant can fork between enumeration and killing

  kill_survivors takes one process snapshot, then sends SIGKILL only to those PIDs. A detached process P can fork C after enumeration but before P receives SIGKILL. C is reparented to Ariane and survives: _reap scans again but only reaps zombies and waits for the original killed set, never killing newly discovered running descendants. The ticket stops, but C remains able to write files after cleanup. Cleanup must account for descendants created during enumeration/killing and verify that none remain; add a regression test for this interleaving.

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

  The new integrity tests exercise external instruction changes, complete changed-path lists and truncation reporting, and detached-process killing with metrics. These assertions depend on the new behavior. Failure, setup and concurrent-fork coverage is missing as described above. Reported checks passed; I did not rerun tests in the read-only review.

- met: The documentation the change affects is updated (C25).

  README, ADR 0031, affected workflow/module documentation and the generated log catalogue were updated. The unchanged logs module page still accurately describes the declaration mechanism and links to that catalogue. Some documented guarantees are not fulfilled by the implementation, as detailed in the findings.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0031's amendment records the snapshot scope, additional Codex files, truncation behavior, descendant baseline, background git-process treatment and platform residuals.

## Proposed learnings (not decided)

- Proposed: Capture security baselines before setup executes untrusted code.
- Proposed: Test security cleanup on failure and interruption paths, not only normal returns.
- Proposed: Process cleanup must handle descendants created between enumeration and termination.
