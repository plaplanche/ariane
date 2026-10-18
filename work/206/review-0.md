# Review 0

- Reviewed commit: `3c26bfbfaaa5a39dc21ba2bac96d8ed9dbf8227b`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`docs/adr/0049-template-project-and-windows-shards.md:168`) Required performance measurements remain uncompleted

  The after-change CI measurements are placeholders, and the Windows baseline top 30 is deferred to the owner. Consequently, neither the required under-570-second Windows result on this PR nor the Windows-based selection of the next five avoidable setups is demonstrated. The shard decision at lines 101–116 extrapolates from Linux instead of following the required order: measure Windows after the fixture optimizations, then shard only if above 480 seconds. Complete the measurement handover and record the run evidence before accepting this ticket; YAML supplied for the owner is useful but does not complete these acceptance criteria.

- **blocking** (`docs/adr/0049-template-project-and-windows-shards.md:155`) CI handover omits required serial validation

  Neither the existing workflow nor either proposed workflow change runs the full suite with `uv run pytest -n 0`. The subprocesses in the shard test only collect tests serially. The issue explicitly requires both parallel and serial suites to pass on Linux, macOS and Windows in CI. Include serial validation in the owner-applied workflow and record successful runs on all three systems.

- **minor** (`README.md:330`) README describes unapplied sharding as current behavior

  The README says Windows CI runs two shards, but the checked-out workflow still has one Windows job running plain `uv run pytest`. The ADR also allows deciding against shards after measurement. Describe the current behavior accurately until the conditional workflow change is applied, then synchronize the documentation with the measured decision.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  README and ADR 0049 were added or updated, and no src module changed. However, the README reports sharding that is not implemented in the workflow, and the ADR's required CI measurements remain placeholders.

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

  New tests exercise copy isolation, independent push destinations, unchanged initial repository contents, path quoting and commit_on_branch behavior; these depend on helpers and fixtures absent before the change. The shard test checks disjoint, exhaustive collection. Ariane reports passing replay checks. I did not execute tests because this review is read-only.

- **not met**: The documentation the change affects is updated (C25).

  README and ADR 0049 were added or updated, and no src module changed. However, the README reports sharding that is not implemented in the workflow, and the ADR's required CI measurements remain placeholders.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0049 records direct config rewriting, per-worker template isolation, fast-import branch setup, pytest-split, duration-based balancing and the proposed shard count. Recording these choices does not establish that the measurement prerequisite for sharding has been met.

## Proposed learnings (not decided)

- Proposed: Treat measured performance targets as acceptance gates; estimates and handover instructions do not substitute for recorded CI results.
- Proposed: Preserve the fixture write order: build the worker template, copy the bare remote, copy the checkout, rewrite the copied origin, then expose the project. The inspected path follows this order without writing back to the template.
