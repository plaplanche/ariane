# Review 0

- Reviewed commit: `a56f07501612d7efff84f1fe2b16c3ed9c75b4d8`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/restart.py:185`) Unregistered ticket folders are deleted without preserving their work

  Saving is conditional on the ticket tree being registered with git, but removal is unconditional. If registration is missing or damaged and worktrees/7 contains uncommitted files, clear skips _save and _remove_tree recursively deletes those files. With no local branch, it creates no backup at all. A read-only mocked probe confirmed the order: prune, remove the folder, prune; _save was never called and kept_branch was empty. Preserve an unregistered primary ticket folder before deleting it, or refuse and leave it intact. Add coverage for a nonempty unregistered primary folder; the existing unknown-folder test covers only an empty replay folder.

- **blocking** (`src/ariane/restart.py:188`) A dead runner can leave an agent writing during restart

  The lock establishes that the previous Ariane parent exited, not that its agent processes exited. process._execute starts subprocesses in separate sessions and kills them in a Python finally block; SIGKILL or a parent crash bypasses that cleanup. The breaking interleaving is: the parent dies and releases the lock; restart acquires it, snapshots the old tree and creates the kept ref; the surviving agent writes additional work; restart force-removes the tree, losing those writes. The orphan can also continue touching shared git state during the new run. Before snapshotting or removing trees, establish that the previous run's writers have terminated, using crash-safe process ownership or equivalent isolation. Test a killed runner with a surviving writer, rather than only a child holding the lock.

- **minor** (`src/ariane/flow.py:84`) Preparation interruptions still recommend a plain start

  Only _TicketRun._stopped adds --restart. An interruption during prepare, including after creating a branch or while removing restart trees, takes this exception handler and retains 'check the working tree, then start the ticket again'. That plain start can immediately refuse the leftovers. Apply restart guidance to preparation failures that leave an unpushed ticket behind, while preserving the distinct lock-held and remote-branch refusals. The existing interrupt test exercises an implementer interruption, not preparation.

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

  The new test file contains 19 test functions, with the lock refusal parametrized for both modes. Assertions cover the new option, branch preservation, dirty and staged work, restart records, remote/shadow refusals, and reporting, and would fail without this implementation. Ariane reports passing checks; I did not rerun filesystem-writing tests under the read-only restriction. The blocking cases above remain uncovered. Write-order review: CLI configures logging; start creates/opens the ticket lock, writes the registry entry, fetches git state, and checks the remote; restart prunes registrations, writes temporary indexes and git objects, creates the kept ref exclusively, removes trees, prunes again, and deletes the old branch; preparation creates the new branch/tree; execution runs setup before creating the ticket records and logging ticket.restarted. Registry exit appends the ended record before removing the live entry. Each git invocation also emits a technical log. Existing-name failure precedes tree removal, but the preservation gaps identified above remain.

- met: The documentation the change affects is updated (C25).

  README includes PowerShell and bash restart examples. The component sequence, affected module documents, new restart module document, CLI reference, and log catalogue are updated. Documentation describes preservation and concurrency guarantees that need the blocking fixes above.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0047 records the lock implementation, kept naming, staged and uncommitted snapshots, exclusive ref creation, cleanup ordering, unknown-folder handling, record provenance, and concurrent-run guard exemptions. Recording these choices does not resolve the identified preservation failures.

## Proposed learnings (not decided)

- Proposed: treat an absent runner lock as evidence only about the runner, not about surviving subprocesses.
- Proposed: require a verified backup or an explicit refusal before deleting any primary ticket folder, including one git no longer recognizes.
- Proposed: test interruption boundaries during preparation and cleanup as well as during agent execution.
