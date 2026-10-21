# Review 2

- Reviewed commit: `5631f94e7ad56130a02071122a53ef2d05e44d5b`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/next_start.py:144`) The relabel temporarily authorizes an issue revision that is subsequently rejected

  The write order is: create the reservation temporary file and replace the reservation, append start intent, DELETE the ready label, POST the ready label, then check the issue revision. If an issue was edited after analysis, a concurrent manual start can read and pass the issue gate after POST but before the revision check. flow.start reads and caches that issue before acquiring the handoff lock. next --start then detects the edit, removes the label, records CHANGED, deletes the reservation and releases the lock; the manual start subsequently registers and executes its cached, rejected revision without rechecking trust. Removing the label does not revoke that cached authorization. This breaks the issue-gate security property. Make the manual start's issue authorization participate in the handoff synchronization and validate it after waiting; add a regression test for this interleaving.

- **blocking** (`src/ariane/next_ticket.py:143`) Module expansion misses shared source files that have not been created yet

  _module_files expands module documentation references using only files already present in the main checkout. A running issue naming docs/architecture/modules/new_scheduler_223.md therefore has no expected src/ariane/new_scheduler_223.py until that source exists there. Another queued issue explicitly naming that source is incorrectly declared non-overlapping, even when the running ticket is about to create it or has it only in its worktree. A read-only reproduction returned ('docs/architecture/modules/new_scheduler_223.md',) and ('src/ariane/new_scheduler_223.py',), with shared() returning []. This makes the shared-file safety check pass wrongly and contradicts the required mapping of module names to expected source files. Preserve prospective source patterns such as src/*/<module>.py independently of existing files, and test a new module absent from the main checkout.

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

  The four new test_c23_next files exercise queue ordering, dependencies, conflicts, slots, quota, confirmation, records and handoff behavior through APIs absent from the base. Ariane reports the suite green. The two reported safety gaps lack regression coverage. Tests were not rerun because their fixtures write files.

- met: The documentation the change affects is updated (C25).

  README, container and component views, affected module documentation, new module pages, example configuration, generated CLI/schema references and log catalogue were updated.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0059 records queue ordering, dependency syntax, expected-file detection, confirmation semantics, synchronization, reservations, recovery and revision checks. Recording these choices does not resolve the implementation safety findings.

## Proposed learnings (not decided)

- Proposed: serialize authorization reads with approval-changing writes; revoking an approval cannot invalidate an already cached authorization.
- Proposed: expected-file analysis must represent prospective paths, including files absent from the main checkout.
