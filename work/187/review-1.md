# Review 1

- Reviewed commit: `fcdf515d21bddc84b27ad530507c0fda8d472d2b`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`docs/adr/0047-parallel-tests-and-ci-matrix.md:74`) Required cross-platform CI and performance evidence is still pending

  The ADR leaves all post-change CI durations and the run URL unfilled. The supplied green replay establishes neither parallel success on Windows and macOS nor the required longest-job duration below 12 minutes. The checked-out workflows also still declare six jobs and omit explicit enable-cache settings. Deferring workflow edits to the owner follows the delivery note, but the ticket's acceptance remains incomplete until that handover is performed and the four-job CI results and measured durations are recorded. This is a completion gate, not a request for the cloud implementer to push workflow files.

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

  tests/test_parallel_tests.py checks default addopts, the dev dependency, and its lockfile entry; these assertions fail against the base configuration. Ariane reports the test replay passed. Tests were not rerun during this read-only review.

- met: The documentation the change affects is updated (C25).

  README documents parallel execution and -n 0; ADR 0047 records the design and owner handover; ADR 0005, container documentation, and learnings are updated. No production module or check command changes. CI measurements remain incomplete as reported above.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0047 records default scheduling without grouping, the isolation rationale, matrix, cache settings, required-check migration, and alternatives. Inspection found per-test repository paths and process-local fixtures; survivor cleanup identifies protected groups before signalling, then kills, reaps, and records results. No new cross-worker side-effect ordering defect was identified.

## Proposed learnings (not decided)

- Proposed: distinguish a completed cloud implementation handover from completed ticket acceptance; retain the actual cross-platform CI run URL and timings before declaring a performance target achieved.
