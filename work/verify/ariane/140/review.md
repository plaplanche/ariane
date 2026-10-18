# Review 0

- Reviewed commit: `68a4e2dbec0ddf8226abde55ca5a0714fcd61614`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/restart.py:190`) A surviving agent can write after preservation and lose its work

  The ticket lock proves the old orchestrator exited, not that its agent exited. After SIGKILL, an agent can survive while the replacement process acquires the lock. Restart writes in this order: lock file, registry entry, fetch metadata, prune registrations, temporary indexes and Git objects, preservation commits, kept ref, forced tree removals, another prune, deletion of the original branch, and creation of the new branch/tree; Git commands also emit technical logs. The breaking interleaving is: _save captures the files; the surviving agent writes more work; _remove_tree deletes that work. No check or termination of the previous run's writers guards removal. ADR 0047 acknowledges this loss, but it contradicts the ticket's lossless interruption requirement. Quiesce those writers or refuse destructive cleanup when their termination cannot be established, with a subprocess regression test.

- **blocking** (`src/ariane/flow.py:84`) Preparation interruptions still recommend the refused plain start

  The preparation exception handler calls describe directly rather than adding the restart action. For example, git worktree add can create the branch and working-tree files before Ctrl-C interrupts preparation. The handler then says 'check the working tree, then start the ticket again'; following that instruction with plain start refuses the leftovers. Errors during restart cleanup similarly return only 'read the error above and retry'. This retains the precise recovery-instruction defect the ticket requires fixing for every unpushed stop. Add preparation-failure coverage and recommend --restart when preparation has left recoverable ticket state, while retaining the lock-held and remote-branch refusals.

- **blocking** (`src/ariane/measures.py:45`) A second restart drops the first restart's human time

  For run A stopping at 09:00, run B restarting at 10:00 and stopping at 11:00, and run C restarting at 12:00, C records only B's stopped_at. restart_seconds therefore reports one hour instead of two. B's earlier restarted_from remains only on its kept branch; report.build reads working-tree metrics files and does not traverse kept branches. Each new run replaces the measurement history rather than accumulating restart intervals. Preserve prior intervals or their accumulated duration and test two stopped runs followed by a successful restart.

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

  The new tests exercise restart delivery, branch and dirty-work preservation, subprocess lock contention, remote and shadow refusals, journal ordering, and reporting. These depend on functionality absent before the change. Ariane reports passing checks; filesystem-writing tests were not rerun during this read-only review. The failure cases identified above remain uncovered.

- met: The documentation the change affects is updated (C25).

  README includes PowerShell and bash commands; affected module pages, the new restart module page, component sequence, CLI reference, and log catalogue are updated. Documenting the surviving-agent limitation does not resolve the preservation defect.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0047 records locking, retained names, preservation commits, staged content, unknown directories, record sources, concurrency exemptions, and module placement.

## Proposed learnings (not decided)

- Proposed: recovery must establish that all previous writers have stopped before snapshotting and deleting their workspace.
- Proposed: test interruptions during preparation and cleanup, not only inside agent sessions.
- Proposed: test restart measurements across multiple failed attempts so a fresh run cannot erase accumulated human time.
