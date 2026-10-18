# Review 1

- Reviewed commit: `5bc141204f7826c643254d714f8fd756009c6a4d`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/git.py:313`) Concurrent config writes can produce an inconsistent baseline

  The shared config digest, parsed keys and scoped settings are read separately. Interleaving: A reads the old digest for its baseline; B writes its registry draft, links its registration, removes the draft, then creates its branch and writes its tracking configuration; A reads the new keys and settings. At A's next guard, only the digest differs. foreign_changes requires a nonempty key delta to tolerate that difference, so it stops A despite B making only authorized changes. An in-memory reproduction returned 'changed: file /repo/.git/config'. Reading the registry after the snapshot does not make these config reads consistent. Capture a coherent config snapshot or detect and retry concurrent changes, and add a test interrupting baseline collection between these reads.

- **blocking** (`src/ariane/runs.py:215`) Unordered key comparison hides changes to effective configuration

  Counter discards entry order, while the scoped-setting snapshot also stores lines as unordered dictionary keys. With an existing repeated setting, an agent can reverse its values while adding an allowed branch key for a registered run. For example, reversing core.sshCommand entries from unsafe,safe to safe,unsafe changes the effective command. The only counted delta is the allowed branch key, so lines 224–227 discard the digest and listing differences and the guard accepts the change. An in-memory reproduction returned no changes. Previously the digest detected this edit. Preserve the order of non-exempt entries and test duplicate-key reordering combined with legitimate bookkeeping.

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

  The new test module covers registered and unregistered branches, forbidden keys, hooks, lifecycle cleanup, stale entries and registry races. The registered-branch acceptance case would fail under the original guard. Supplied replay results report passing tests; the two snapshot cases identified here are missing. Review validation used read-only, in-memory reproductions rather than rerunning tests that write fixtures.

- met: The documentation the change affects is updated (C25).

  README, component sequence, flow/git/stop module documentation and the new runs module documentation are updated. Existing log event identifiers and message templates remain unchanged.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0017 records registry representation, locking, atomic entry publication, end-history ordering, snapshot/registry read ordering and key comparison. It also explicitly records the additional base-branch merge value.

## Proposed learnings (not decided)

- Concurrency tests should interrupt snapshot collection itself, not only registration and cleanup.
- Configuration comparison must preserve duplicate-value ordering when ordering changes effective behavior.
