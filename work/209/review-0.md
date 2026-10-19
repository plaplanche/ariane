# Review 0

- Reviewed commit: `00566155b6be75f3a185743de4a070487456e64c`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/cache.py:186`) Restore follows destination symlinks before checking containment

  Path validation is lexical only. A commit can replace a declared cache folder, or its parent, with a symlink while leaving the key files unchanged. On a hit, _copy follows that symlink through mkdir and file writes, then changes file permissions and touches the entry timestamp. This happens before project.setup or any subsequent guard; target.is_symlink() is checked only on the miss/store path. Consequently a replay can overwrite files outside its tree, including the agent's tree or store. Validate destination components before any restore write and reject symlink traversal. Add a regression covering a warmed cache followed by a commit introducing a destination symlink.

- **blocking** (`src/ariane/cache.py:205`) Invalid-entry replacement can delete another worker's completed entry

  The write sequence is temporary-directory creation, data copy and chmod, metadata write, invalid-entry check, recursive deletion, then rename. The check and deletion are not atomic: worker A observes an invalid entry and pauses; B removes it and publishes its complete entry; A resumes and deletes B's completed entry before publishing its own. Readers can therefore encounter a completed entry being dismantled, contrary to the documented first-rename-wins guarantee. Pruning also deletes entries without coordination with readers or publishers. Coordinate replacement, pruning and restore, and test these interleavings rather than only sequential cache reuse.

- **blocking** (`src/ariane/cache.py:188`) Failed restore leaves partially copied data in an existing destination

  When the destination already exists, restore merges files directly into it. If a later file cannot be read, the exception path leaves all earlier writes in place because cleanup runs only when existed is false. prepare then runs setup over that mixture and can publish it as a new cache. A pre-existing directory, for example one containing a tracked marker, is not rejected by this implementation. This violates the explicit requirement never to trust an unreadable entry partially. Stage restoration separately and expose it only after a complete copy, or reliably roll back every write before rebuilding. Test a copy failure after at least one successful write into an existing destination.

- **minor** (`src/ariane/replay.py:245`) Disabling caches still prunes the existing store

  set_up_ticket_tree calls prune even when config.caches is empty. After cache declarations are removed, starting a ticket can still delete old entries and journal those deletions. This contradicts the documented no-pruning/no-journaling behavior without [[project.cache]]. The current no-cache test covers only a repository with no existing store.

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

  The new test module contains more than five named dependency-cache tests covering build/hit/key changes, copy isolation, incomplete entries, journaling, configuration, pruning and verify integration. These depend on functionality absent from the base. Ariane reports passing checks; I did not rerun filesystem-writing tests during this read-only review. Concurrent publication, symlink destinations and failed restoration into existing directories remain uncovered.

- met: The documentation the change affects is updated (C25).

  README, Node and Python configuration examples, affected module documentation, component diagrams, schema and log catalogue are updated. Ariane reports the generated-reference check passed. The implementation discrepancies are identified in the findings.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0054 records key construction, copies versus links, replay-only publication, platform cloning and fallback, retention settings, partial-entry handling, ticket-tree behavior and verify behavior. It includes measured before/after Node dependency setup timings and limitations.

## Proposed learnings (not decided)

- Proposed: test cache publication and pruning with controlled concurrent interleavings; atomic rename alone does not make surrounding validation and deletion atomic.
- Proposed: validate filesystem containment before copying, and stage restores so a failed copy cannot contaminate a rebuild.
