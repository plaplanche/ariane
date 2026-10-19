# Review 0

- Reviewed commit: `50d642c4fbd30956eff5b3b1b48488cf42e072be`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/runs.py:351`) Concurrent verifications can reject a legitimate fetch

  Parallel replay workers share guard, and replay_each runs setup and verify outside its serial lock. Interleaving: worker A snapshots tracking commit X and pauses; another ticket fetches legitimate remote descendant Y; worker B snapshots Y, validates it and writes guard[key] = Y; worker A resumes and compares its older snapshot X against the now-mutated guard Y. tracking_fast_forward rejects X because the remote points to Y, stopping the ticket despite no backward move occurring. I reproduced this stale-snapshot rejection using the actual function in memory. Snapshot acquisition, comparison and guard advancement need synchronization shared by setup and verification, with a deterministic parallel-worker regression test.

- **minor** (`docs/architecture/modules/git.md:68`) The explicitly requested git module documentation was not updated

  The acceptance checklist names this document, but it remains unchanged. Its guard description should point to ADR 0055 and explain that runs now tolerates a tracking-ref fast-forward witnessed through remote_refs.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  README, flow, runs, shadow and ADR documentation were updated, but the explicitly requested docs/architecture/modules/git.md was omitted. No log event changed.

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

  The new file contains nine parametrized test cases. Successful delivery after a tracking-ref fetch would fail under the previous unconditional guard rejection. Invalid moves and unchanged review diffs/delivered commit subjects are also covered. Parallel verification is missing. Relied on Ariane's reported passing checks; did not rerun filesystem-writing integration tests.

- **not met**: The documentation the change affects is updated (C25).

  README, flow, runs, shadow and ADR documentation were updated, but the explicitly requested docs/architecture/modules/git.md was omitted. No log event changed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0055 records the remote witness, mutable guard advancement, additional remote lookup, unchanged shadow/verify behavior and alternatives. ADR 0017 points to it.

## Proposed learnings (not decided)

- Proposed: When an immutable guard becomes mutable, audit every concurrent caller and test stale snapshots explicitly.
- Proposed: Serialize snapshot acquisition through guard advancement; locking only the final assignment does not prevent stale-snapshot rejection.
