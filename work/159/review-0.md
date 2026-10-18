# Review 0

- Reviewed commit: `0d9f7c478a2f862798ff7b5246def301e2533f76`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/flow.py:342`) Registry is sampled before the changes it must authorize

  Run A reads during() without ticket B. B then writes its registry draft, links its entry, removes its draft, and creates its branch and shared configuration keys. A's subsequent snapshot sees B's changes but uses the earlier set of registered tickets, so it stops a legitimate parallel run. Registration precedes B's git writes correctly, but A observes them in the opposite order. Take the git snapshot before collecting the registrations that authorize its changes, with a consistent registry handoff, and add a deterministic interleaving test.

- **blocking** (`src/ariane/runs.py:105`) Run termination leaves a gap in registration history

  Termination first unlinks runs/n, then opens ended.jsonl, writes the completion record, and closes the file. Between unlink and the flushed append, another run can execute both running() and the history read and find neither record. Its guard then rejects the completed run's legitimate branch changes, violating the requirement to recognize tickets running at any time during the session. Publish completion history before removing the live entry, ensuring readers always observe at least one representation. Test a reader paused between these writes.

- **blocking** (`src/ariane/runs.py:96`) Stale-entry cleanup can delete a replacement live registration

  The stale check and unlink are separate operations. Starters A and B can both read the same dead entry; A unlinks it, links its own draft, removes its draft, and begins preparation. B then executes its pending unlink against A's live entry and links its own draft, admitting both runs. Either run's unconditional exit unlink can subsequently remove the other's registration. running() has the same read/check/unlink race at lines 118–122 and can erase a newly registered ticket while cleaning an old entry. Serialize stale reclamation and registration, and make cleanup ownership-safe. The current sequential duplicate-registration tests do not exercise this interleaving.

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

  The new test module contains 14 parametrized cases, including registered branch creation and a complete nested run that the previous guard would reject. Ariane reports the test check passed. The tests do not cover the blocking concurrent interleavings; I did not rerun filesystem-writing tests in this read-only review.

- met: The documentation the change affects is updated (C25).

  README, the component sequence, flow and git module documentation, the new runs module documentation, and collaboration diagrams are updated. No log event or emitted log template changed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0017's amendment records the JSON registry, hard-link publication, duplicate-run refusal, completion history, exact configuration filtering, and the additional base-branch merge value with its rationale.

## Proposed learnings (not decided)

- Proposed: Test concurrency guarantees with deterministic pauses between reads, checks, and writes; nested sequential runs do not establish concurrency safety.
- Proposed: Publish historical registration before removing live registration so readers cannot observe a gap.
- Proposed: Atomic file creation does not make read-check-delete replacement atomic; stale cleanup must preserve ownership.
