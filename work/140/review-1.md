# Review 1

- Reviewed commit: `cc0f5be9f9040c714bfebc64ab22bb5e1c60553f`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/restart.py:156`) Restart permanently deletes work left uncommitted by an interruption

  If the process dies during the implementer session, before flow._commit_agent_work, modified and untracked files exist only in its tree. Restart writes in this order: create/open the lock file, register the run, fetch, prune worktree registrations, force-remove the trees, prune again, rename the old branch, create the new branch/tree, run setup, then write the new journal and metrics. No preservation step precedes tree removal. The renamed branch therefore cannot recover those files. The interrupt test raises before writing anything, and the killed-run fixture uses clean trees, so neither catches this. Preserve the interrupted tree's work before destructive cleanup and test modified and untracked files. The README and ADR acknowledge the loss, but that contradicts the ticket's lossless-restart requirement and the spec's robustness requirement; preserving work does not require implementing session resumption.

- **blocking** (`src/ariane/runs.py:287`) Agent-writable registry data can exempt arbitrary branches from the guard

  Run.kept is read from registry files that the existing threat model explicitly treats as agent-writable. genuine() validates the process and ticket number, not kept, and during() replaces witnessed entries with the current file contents. With ticket 8 genuinely running, ticket 7's agent can write kept='main' into runs/8 and then move refs/heads/main. Ticket 7's guard snapshots the changed ref, rereads the forged registry entry, and suppresses the main-branch change before delivery. An in-memory probe confirmed foreign_changes reports the main change normally but returns [] with kept={'main'}. Thus checking that the process is genuine happens without authenticating the newly trusted branch exemption. Restrict and validate exemptions against trusted restart metadata and add a regression test that tampers with a genuine live run's kept field.

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

  The new test module defines 13 tests, yielding 14 cases with parametrization. They exercise restart delivery, retained heads, leftovers, subprocess locking, remote refusal, shadow refusal, and reporting; these depend on functionality absent before the change. Ariane reports the suite green. Tests were inspected, not rerun in this read-only review. Dirty interrupted trees and forged registry exemptions remain uncovered.

- met: The documentation the change affects is updated (C25).

  README includes PowerShell and bash restart commands; affected module documentation, the start sequence, architecture index, CLI reference, and log catalogue are updated. The new restart module has documentation. The documented loss of uncommitted files remains a behavioral defect.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0047 records lock implementation, retained branch naming, cleanup behavior, record sources, concurrent-run bookkeeping, and module placement. Recording the destructive behavior does not resolve its conflict with the lossless-restart requirement.

## Proposed learnings (not decided)

- Proposed: interruption-recovery tests should leave modified and untracked files before simulating process death.
- Proposed: authenticating a registry entry's process does not authenticate additional agent-writable fields used to grant guard exemptions.
