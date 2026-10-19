# Review 0

- Reviewed commit: `5fd47df219c8656651c4f19bfbcd2fb09e939ead`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/cache.py:162`) Validate restored caches before running another cache's setup

  With two caches, A can hit while B misses. If the commit stopped ignoring A without changing its key, the order is: restore A into a temporary folder, rename it into the tree, touch its entry metadata, run B's setup and its writes/external calls, then validate A. The continue delays validation until after another command has run. An in-memory probe confirmed restore A → restore B → run setup B → validation failure. B can also remove the offending files and conceal the violation. Validate each hit before proceeding to any subsequent setup. Add a two-cache regression test; the current unignored-hit tests exercise only one cache.

- **blocking** (`src/ariane/verify.py:239`) Reject tracked setup mutations before publishing a cache

  The pre-publication validation checks HEAD and untracked files, but not tracked working-tree or index changes. A cache setup can modify a tracked non-key file and build the dependency folder. The sequence is: setup writes both; validation passes; _store copies the folder to a temporary entry, changes permissions, writes entry.json, acquires the store lock and renames the entry into place; the check runs; only then _unchanged rejects the tracked mutation through git.status. The rejected verification leaves a reusable cache. Retrying the same commit restores it and skips the setup that caused the mutation, so the retry can pass. Check tracked and staged cleanliness before publishing in both replay integrations, and test that a rejected setup leaves no published entry and cannot become successful merely through a cache hit.

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

  26 named dependency-cache test functions cover build/hit/key changes, copy isolation, partial entries, journaling, pruning, verify integration and guards. These depend on the new implementation. Ariane reports the suite green; I did not rerun filesystem-writing tests in this read-only review. The two ordering cases identified above remain uncovered.

- met: The documentation the change affects is updated (C25).

  README, Node/Python configuration examples, affected architecture modules, the configuration schema and log catalogue are updated. Ariane reports the generated-reference check passed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0054 records key framing, copy mechanisms, locking, publication/replacement, destination protection, retention, agent-tree behavior and portability limitations, with measured Node replay timings before and after.

## Proposed learnings (not decided)

- Proposed: validate every restored cache before any subsequent setup can consume or alter it.
- Proposed: perform replay-integrity checks before publishing reusable artifacts; test that a failed cold run cannot pass on retry solely because it populated the cache.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
