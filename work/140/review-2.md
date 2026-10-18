# Review 2

- Reviewed commit: `4328eb3a09a40f65e446afd7e26a87aa5780cbaf`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/restart.py:185`) The saved work must be reachable before deleting its working tree

  The write order is: create/open the ticket lock; register the run; fetch; check remote refs; prune worktree metadata; write a temporary index, objects and an unreferenced snapshot commit; delete the working trees; prune; rename the branch; finally update the kept ref to the snapshot. If the process dies after deletion but before update-ref, the only snapshot identifier was in memory. A retry cannot recover it from the deleted tree and preserves only the old branch head; the snapshot is unreferenced and eventually collectible. A rename failure, including an existing timestamp-based destination, has the same effect. Persist a ref to the saved commit before any tree removal, and make retries recover that record. Add interruption and rename-failure tests at this boundary.

- **blocking** (`src/ariane/restart.py:214`) Saving only the working-tree contents loses staged work

  The temporary index is initialized from HEAD, then replaced with the files on disk by git add --all. The original index is never saved. For example, stage version B of a tracked file, then restore version A from HEAD into the working file without changing the index. The snapshot equals HEAD, so _save returns an empty string; clear then force-removes the tree and its index. Version B is absent from the kept branch. Staged-only additions similarly disappear when their working files have been removed. Preserve both index and working-tree contents before deleting either, and test differing staged and unstaged versions.

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

  The new test_c23_restart tests exercise restart delivery, preservation, child-process locking, remote refusal, shadow refusal and reporting; they depend on functionality absent from the base. Ariane reports the suite passing. Tests were inspected, not rerun in this read-only review. The destructive failure boundaries identified above remain untested.

- met: The documentation the change affects is updated (C25).

  README includes PowerShell and bash restart instructions; the affected module documentation, start sequence, CLI reference and log catalogue are updated. The preservation guarantees described there require the blocking fixes.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0047 records lock semantics, kept-branch naming, uncommitted-work snapshots, cleanup behavior, restart records, concurrent-run guard exemptions and module placement.

## Proposed learnings (not decided)

- Proposed: Before destructive cleanup, attach recovery snapshots to durable refs and test interruption between every destructive step and its recovery bookkeeping.
- Proposed: Git work preservation must account separately for HEAD, the index and working-tree contents.
