# Review 1

- Reviewed commit: `78ce81db2728177e0b8536bd777f97332ff48227`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/flow.py:320`) Cached ancestry lets later checks change Git history undetected

  Commit IDs do not fix Git's effective ancestry: the shared shallow file and replacement refs can change it. Neither is covered by git.state. A concrete sequential bypass is: check 1 passes and caches (start, checked); check 2 writes checked's SHA to <git-common-dir>/shallow; verification skips merge-base because the pair is cached, accepts the unchanged snapshot and remote, and writes the successful guard log/journal; its replay tree is removed; check 3's tree is created and check 3 deletes shallow, hiding the modification before subsequent verification and delivery. Previously, verification after check 2 reran merge-base and stopped before check 3 could undo the write. Retain the ancestry check or guard all mutable ancestry inputs before using the cache. Add a whole-run regression asserting that the modifying check stops execution before the restoring check runs.

- **blocking** (`docs/adr/0053-fewer-git-processes-per-run.md:142`) Required Windows performance result is missing

  The ticket requires the pull request's 30 slowest Windows tests to total at most 60% of ADR 0049's baseline. The ADR explicitly leaves this unmeasured and predicts 67–70%, which would miss the target. Linux process counts and passing functional checks do not establish this acceptance criterion. Record the exact baseline, PR CI run and Windows total, then complete further in-scope reductions if the target is missed.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  The component view and all six changed modules have documentation updates, but ADR 0053 lacks the required Windows results. Its claim that a commit fixes ancestry, repeated in flow.md, also overlooks mutable Git ancestry metadata.

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

  Four whole-run process-bound tests enforce reductions below the recorded pre-change counts; focused tests cover snapshot and commit process counts and existing tampering cases. Ariane reports passing tests. The new ancestry-cache bypass is not covered. Tests were inspected, not rerun, to preserve read-only access.

- **not met**: The documentation the change affects is updated (C25).

  The component view and all six changed modules have documentation updates, but ADR 0053 lacks the required Windows results. Its claim that a commit fixes ancestry, repeated in flow.md, also overlooks mutable Git ancestry metadata.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0053 records the chosen optimizations, phase measurements, comparison semantics, retained per-check remote verification, alternatives and regression bounds. Recording these choices does not resolve the blocking correctness and acceptance findings.

## Proposed learnings (not decided)

- Proposed: Cache Git ancestry only when replacement refs and shallow metadata are also guarded; object IDs alone are insufficient.
- Proposed: Keep process-count improvements distinct from measured platform performance acceptance.
