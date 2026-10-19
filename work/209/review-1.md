# Review 1

- Reviewed commit: `abe7cecb6eee5fdf10a109fa8f55e9f5821b360c`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/cache.py:168`) Cache publication precedes validation of the replay tree's HEAD

  A cache setup can switch the detached replay tree to another commit without changing shared refs. The setup guards do not validate that tree's HEAD. The write order is: setup changes HEAD and builds dependencies; _store creates a temporary directory, copies and chmods data, writes entry.json, then publishes by rename; project/check setup and the check run; only afterward does replay.verify_tree (or verify._unchanged) reject the moved HEAD. The published entry survives that rejection. A subsequent replay with the original key restores those dependencies and skips the offending setup, so the failed run contaminates later clean replays. Validate the replay HEAD before publishing any cache, in both start and verify, and test that a setup moving HEAD leaves no published entry.

- **blocking** (`src/ariane/replay.py:281`) Cache hits bypass the requirement that setup outputs be ignored by Git

  Warm a cache with node_modules ignored, then replay a commit that removes that ignore rule while retaining the lock file and cache command. The hit creates parent/staging directories, copies files, renames the folder into place and touches entry.json. It skips the cache setup and its git.untracked validation. When project.setup is absent, run.setup returns immediately, so the implementer or check runs with unignored dependencies. In the ticket tree these files can subsequently be committed with the agent's work; verify detects them only after running the check. A cold cache correctly refuses the same configuration. Validate restored outputs before starting any agent or check, including when no remaining setup command exists, and cover this warm-cache regression.

- **minor** (`src/ariane/cache.py:276`) A data-unreadable entry is retained after a successful rebuild

  When entry.json is valid but copying data fails, _restore cleans up and builds again. _store then copies the successful rebuild into a temporary entry, but _read_entry checks only metadata and whether data is a directory. It therefore accepts the same unreadable entry, deletes the replacement, and reports 'stored by another tree at the same time'. Every later replay can repeat the failed copy and rebuild. Track the failed entry's identity and safely replace it under the lock without deleting a newer publication. The existing failing-copy test uses fill=False and misses this case.

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

  The new test module contains 21 named test functions, including integration coverage for reuse, key changes, copy isolation, partial entries, journaling, pruning, verify and absent configuration. These depend on the new functionality. Ariane reports the suite passing; I did not rerun tests because they write files. The findings identify additional regression coverage needed.

- met: The documentation the change affects is updated (C25).

  README, Node/Python configuration examples, affected architecture modules, the new cache module documentation, schema reference and log catalogue are updated. Ariane reports the generated-reference check passing.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0054 records key construction, copy mechanisms, replay-only publication, destination restrictions, locking, retention, journaling and relocation limitations, with measured Node replay timings before and after.

## Proposed learnings (not decided)

- Proposed: validate replay provenance before publishing reusable artifacts; a later guard failure cannot undo another replay's consumption.
- Proposed: cache hits must preserve setup postconditions, including Git-ignore validation.
- Proposed: test unreadable cache data through rebuild and replacement, not only restore cleanup.
