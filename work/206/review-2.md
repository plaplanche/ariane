# Review 2

- Reviewed commit: `1e6dce6c8d126bf1d0b2a744ae42ba89c31b2e5e`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`docs/adr/0049-template-project-and-windows-shards.md:251`) Required cross-platform CI results and Windows target remain unverified

  All post-change CI measurements and serial results remain pending. The checked-out workflow still runs only uv run pytest, without --durations=30 or serial jobs. The supplied green replay does not demonstrate the required Windows tests step under 570 seconds or both execution modes passing on all three systems. The owner handover is explicitly allowed, but must be completed before approval: apply the workflow, record run URLs and results, and resolve the conditional shard decision from the measured unsharded Windows run.

- **blocking** (`docs/adr/0049-template-project-and-windows-shards.md:90`) Five optimization targets were selected without the required Windows baseline

  The ADR explicitly selects these setups provisionally from Linux process counts and has no Windows top-30 baseline. This does not establish that they are the five slowest avoidable Windows setups required by the ticket. Process counts alone cannot establish that ranking. Record the pre-change Windows durations, identify the five qualifying targets from that evidence, and reconcile the implementation with that selection before closing this ticket.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  README and ADR 0049 document the implementation, and no src module changes require architecture updates. However, the explicitly required Windows baseline, post-change cross-platform measurements, and final shard decision remain pending in the ADR.

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

  The new tests check repository and remote isolation, fixture compatibility, branch commits, one template per session, and copying without starting a process. The last two distinguish the implementation from rebuilding repositories per test. Ariane reports a passing replay; no tests were executed during this read-only review.

- **not met**: The documentation the change affects is updated (C25).

  README and ADR 0049 document the implementation, and no src module changes require architecture updates. However, the explicitly required Windows baseline, post-change cross-platform measurements, and final shard decision remain pending in the ADR.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0049 records direct config rewriting, worker-local copying, fast-import setup helpers, the proposed splitting algorithm and dependency, and serial CI job design. The measurement-dependent shard outcome remains an acceptance blocker rather than an undocumented implementation choice.

## Proposed learnings (not decided)

- Proposed: Performance tickets need measurements from the target platform; process-count reductions and green correctness tests cannot establish a wall-time target.
- Proposed: An owner-only workflow handover should remain explicitly incomplete until its CI evidence is recorded.
