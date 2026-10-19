# Review 0

- Reviewed commit: `a709edfe518a8dc1d79f8fc0de654061dfdefc25`
- Reviewer model: gpt-6-astra
- Verdict: **go**

## Findings

- **minor** (`src/ariane/replay.py:78`) A later setup failure loses the cache journal record

  Cache setup can build a folder, validate it, write the temporary store entry and metadata, and publish it by rename. The subsequent project.setup can then fail before trees.append runs. The finally block consequently omits this check from ticket.checks.cache, despite its persistent cache write. Similarly, successful hits preceding that failure are omitted. Preserve cache outcomes independently of the subsequent setup result and add a failing-project-setup regression test.

- **minor** (`src/ariane/cache.py:321`) Directory permissions are not preserved by the copy

  _copy creates directories using the current umask and never reads the source directory's mode; its final chmod also uses the destination's mode. For example, a dependency directory created with mode 0700 becomes 0755 under umask 022, both in the restored tree and, with write bits removed, in the store. This differs from ADR 0054's statement that modes are kept. Preserve source directory permissions, applying the intended write-bit adjustment, and test a nondefault directory mode.

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

  The two new test files contain 30 named test functions, plus parametrized cases. They cover reuse, changed keys, copy isolation, incomplete entries, journaling, pruning, concurrent publication, both replay entry points and pre-publication validation. These depend on behavior absent before the change. Ariane reports the suite passing; I did not rerun tests because they write files and create worktrees.

- met: The documentation the change affects is updated (C25).

  README configuration guidance, Node and Python examples, all requested module documentation, the new cache module documentation, generated schema and log catalogue are updated. Ariane reports the generated-reference check passing.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0054 records key construction, copy mechanisms, replay-only publication, atomic staging, locking, replacement identity, destination checks, retention, journaling and virtual-environment limitations. It includes measured Node replay results before and after.

## Proposed learnings (not decided)

- Proposed: record completed cache operations even when a later setup step fails.
- Proposed: test directory permissions as well as executable-file permissions when implementing filesystem copies.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
