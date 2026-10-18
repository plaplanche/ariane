# Review 1

- Reviewed commit: `340f9260ffc7cb450d64b4d18503178d4239eef5`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`docs/adr/0049-template-project-and-windows-shards.md:239`) Required CI measurements and platform validation remain pending

  The ADR contains no post-change CI durations, run URL, or serial results on macOS and Windows. The checked-out workflow still runs plain pytest and has no serial job. Consequently neither the Windows target below 570 seconds nor both execution modes passing on all three systems is established, and the measurement-dependent shard decision remains unresolved. The owner's workflow handover is explicitly allowed, but it must be completed and its results recorded before this ticket can receive go; the supplied green replay does not establish these acceptance criteria.

- **blocking** (`docs/adr/0049-template-project-and-windows-shards.md:90`) Windows-driven optimization selection is replaced by Linux estimates

  The decided spec requires measuring Windows first, then optimizing its five slowest avoidable git setups after the project template. This ADR explicitly selects candidates without that measurement, includes the project fixture itself in the five, and defers any Windows-discovered candidates to another ticket. Linux process counts do not establish Windows timing rankings. Obtain the baseline Windows top 30, identify the five qualifying additional setups, and complete or justify the corresponding changes within this ticket.

- **minor** (`tests/test_c9_project_template.py:25`) Regression tests do not enforce template reuse or subprocess savings

  The new tests cover copy isolation, origin URLs, initial state, and branch contents, but would still pass if project rebuilt its repositories for every test while leaving the new helpers available. Add a focused regression check for one template construction per worker/session and no git subprocess during copying, so the central performance behavior is protected.

- **blocking** Definition of done not met: The change is covered by tests that fail without it.

  New helper behavior and repository isolation have meaningful assertions, and Ariane reports a passing suite. However, no behavioral regression test establishes the central change from per-test construction to session template reuse. Tests were not rerun because they write files and this review is read-only.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  README and ADR 0049 document the implementation and owner handover; no src module changed, so architecture updates are unnecessary. The explicitly required Windows baseline, post-change platform measurements, and final shard decision remain missing.

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

- **not met**: The change is covered by tests that fail without it.

  New helper behavior and repository isolation have meaningful assertions, and Ariane reports a passing suite. However, no behavioral regression test establishes the central change from per-test construction to session template reuse. Tests were not rerun because they write files and this review is read-only.

- **not met**: The documentation the change affects is updated (C25).

  README and ADR 0049 document the implementation and owner handover; no src module changed, so architecture updates are unnecessary. The explicitly required Windows baseline, post-change platform measurements, and final shard decision remain missing.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0049 records configuration rewriting, worker-local copies, fast-import branch setup, the proposed splitting algorithm and dependency, and serial CI design. The unresolved acceptance evidence and deviation from Windows-driven selection are separate blocking findings.

## Proposed learnings (not decided)

- Proposed: Treat performance targets as incomplete until measurements from the specified platform and CI run are recorded.
- Proposed: Protect fixture optimizations with construction or subprocess-count assertions as well as state-equivalence tests.
- Proposed: Preserve the reviewed write order: build the worker template completely; copy the remote; copy the checkout; validate and rewrite the copied origin; only then expose the project. These paths use distinct test directories, and no shared-template mutation or concurrent interleaving defect was found.
