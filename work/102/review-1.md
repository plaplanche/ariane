# Review 1

- Reviewed commit: `5f867070e01d6d924aa68030876874f2a97ab6e7`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/verify.py:58`) `ariane verify` does not journal the interruption

  The decided spec says both `ariane start` and `ariane verify` record "interrupted by the user" in the ticket's journal and status.md when the ticket folder exists. Verify keeps its records in a temporary folder and commits nothing on any stop (it treats `Refused` the same way), so there is no ticket folder on the branch to record into. That makes the choice defensible, and verify.md documents it. Still, it is a reading of the spec rather than the spec's literal wording, and it is not recorded as an ADR or a note on the ticket.

- **minor** (`src/ariane/process.py:158`) Small window between Popen and the try/finally

  The `_Reader` threads and the stdin feeder start after `Popen` but before the `try`. A Ctrl-C landing in that window, or an exception while building a reader, would skip `kill_tree`. The ticket asked for the `finally` to cover the wait and the readers. In practice the window is tiny; moving the `try` to just after `Popen` would close it.

- **minor** (`src/ariane/flow.py:78`) Ctrl-C during _prepare can leave a half-created worktree or branch

  An interruption inside `_prepare` (after `git worktree add` but before the ticket folder exists) returns one line and exit 130. It does not remove the worktree or branch, so the next `start` on the same ticket may be refused. The next action, "check the working tree, then start the ticket again", covers this, and resuming is out of scope (slice 8).

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

  tests/test_c5_interrupt.py: (1) the tree test patches Popen.wait to raise KeyboardInterrupt once the parent and grandchild pids are written. It checks that the exception is re-raised and that both processes are gone. Without the `finally`, kill_tree is skipped and the sleeping processes survive, so the test fails. POSIX only, since Windows is skipped. (2) An interrupt in the agent session gives exit 130 and "interrupted by the user" in the line, the journal and status.md. Without the new `except KeyboardInterrupt` the exception propagates and the test fails. (3) An interrupt before the ticket folder exists, via git.fetch, gives exit 130 and one line. tests/test_verify.py adds verify's interrupt test: exit 130, replay tree removed, branch head unchanged, nothing pushed. `-k c5_interrupt` selects at least 4 tests, and the replayed test check passed.

- met: The documentation the change affects is updated (C25).

  docs/architecture/modules/process.md gains the C5 cleanup item. flow.md gains the interruption item: EXIT_INTERRUPTED 130, the record, and the case before the ticket folder exists. verify.md documents verify's exit 130 and line. No new log event is added (it reuses run.stopped and ticket.stopped), so the log catalogue does not need regenerating. The docs references check passed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket fixes the behaviour: a `finally` in _execute, re-raising, the "interrupted by the user" record, and exit 130. The only open point is that verify does not journal the interruption, and that follows verify's existing design (ADR 0028: records in a temporary folder, nothing committed on a stop). No new open choice needs an ADR; this point is noted as a minor finding.

## Proposed learnings (not decided)

- When a test monkeypatches Popen.wait to inject KeyboardInterrupt, it has to let the drain wait (a distinct timeout) through, or the cleanup path is never exercised.
- A KeyboardInterrupt-safe cleanup should cover everything from right after Popen, not only the wait, so no window lets a process escape.
