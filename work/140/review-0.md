# Review 0

- Reviewed commit: `3828b0c86b97eb83fbd204de895dbfb7bac7251f`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/restart.py:151`) Restarting one ticket stops another concurrently running ticket

  Interleaving: ticket 8 snapshots git; ticket 7 registers, removes its trees, prunes, renames ariane/7 to ariane-restarted/7-<time>, and creates its new branch; ticket 8 then checks its snapshot. runs.foreign_changes permits only refs/heads/ariane/7, not the newly archived ref, so ticket 8 stops with 'changed git configuration, hooks or local branches'. A read-only invocation of foreign_changes confirmed that the archived ref remains a violation even with ticket 7 explicitly allowed. Extend the trusted bookkeeping mechanism to account for authenticated restart operations, and add concurrent-ticket coverage.

- **blocking** (`src/ariane/restart.py:145`) The advertised restart cannot clear an unregistered leftover directory

  leftovers includes every existing matching path, but git.remove_worktree always executes git worktree remove --force, which refuses directories that are not registered worktrees. The new test_c23_restart_a_tree_left_during_the_run_names_restart_once creates exactly this state with mkdir, then checks only the recommendation. Following that recommendation fails repeatedly. Cleanup removes the main ticket tree first, then fails on the unregistered replay directory before pruning, archiving, or starting the new run. Handle these leftovers safely and extend the test to execute the recommended restart successfully.

- **minor** (`docs/architecture/modules/logs.md:29`) The changed logs module documentation was not updated

  The generated catalogue includes ticket.restarted, but the logs module page remains unchanged. The supplied documentation rule explicitly requires updating the module page for every touched module. Document the new restart journal entry and its relationship to ADR 0047.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  README, component sequence, affected workflow module pages, CLI reference, and log catalogue were updated, but docs/architecture/modules/logs.md was not updated as required.

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

  The new test_c23_restart tests assert restart delivery, branch preservation, lock contention and release, remote refusal, shadow refusal, journal ordering, and restart timing. These depend on the new implementation. Ariane reports passing checks; I did not rerun filesystem-writing tests in this read-only review. Concurrent-ticket guards and successful recovery from unregistered directories remain uncovered.

- **not met**: The documentation the change affects is updated (C25).

  README, component sequence, affected workflow module pages, CLI reference, and log catalogue were updated, but docs/architecture/modules/logs.md was not updated as required.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0047 records the operating-system lock, archived branch naming, record provenance, cleanup behavior, shadow exclusion, post-push behavior, and module placement.

## Proposed learnings (not decided)

- Proposed: When introducing legitimate shared-git mutations, test their interaction with another ticket's integrity guard.
- Proposed: Tests for recovery instructions should execute the recommended command against the exact failure state.
