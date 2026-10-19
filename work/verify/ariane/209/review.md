# Review 0

- Reviewed commit: `9b760e1beeb40af5a08ef111f88ec61eea8f81a2`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/cache.py:129`) Unreadable key files can select an unrelated cached dependency folder

  key_of treats every OSError as a missing file, including PermissionError, IsADirectoryError and I/O failures. A read-only probe confirmed these produce exactly the same digest as FileNotFoundError. If an entry was built with a missing key file, a later tree whose key file exists but cannot be read will restore that entry and skip setup, despite not establishing that its contents match. The sequence is: failed key read → missing-file digest → restore writes staging files → rename into the tree → touch entry metadata → validate only Git state → run the check. Neither validation checks the failed key read. Handle genuinely missing files separately; other read failures must stop or bypass caching without publishing under that digest. Add a regression proving an unreadable key cannot hit an entry built for a missing key.

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

  The new test_c9_dependency_cache_* tests cover builds, hits, changed keys, copy isolation, incomplete entries, journaling, pruning, verify integration and unchanged behavior without caches. These depend on functionality absent from the base. Ariane reports the suite green; I did not rerun filesystem-writing tests in this read-only review. Unreadable key files remain uncovered.

- met: The documentation the change affects is updated (C25).

  README, Node/Python examples, the configuration schema, log catalogue and affected architecture modules are updated. Ariane reports the generated-reference check green.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0054 records key construction, copies, replay-only publication, locking, retention, relocation limitations and measured Node replay timings. Side-effect tracing: ticket startup locks and prunes entries, prepares caches without publication, runs project setup, then writes ticket records. Replay misses execute setup, validate, create temporary data, copy/chmod files, write metadata, acquire the publication lock, check the existing entry, rename any replacement aside, publish by rename, and clean up. Hits acquire the lock, create parents/staging, copy files, rename the destination, touch metadata, then validate before subsequent setup. Checks run afterward, followed by verification, tree removal and reporting. Restore/publication/pruning share the lock; concurrent publishers recheck entry identity before replacement. Verify uses the same cache publication path and records results in review.md without pruning.

## Proposed learnings (not decided)

- Proposed: distinguish a missing cache-key input from an unreadable input; never turn a failed content read into a reusable cache identity.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
