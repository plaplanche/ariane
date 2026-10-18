# Review 0

- Reviewed commit: `5a220d8d6fb067002515862fe139af293e5b6574`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`docs/adr/0048-parallel-tests-and-ci-matrix.md:75`) Measured CI duration exceeds the stated acceptance criterion

  The recorded longest job is 16.3 minutes, exceeding the ticket's under-12-minute requirement. Lines 80–82 say the owner accepted this result, but the supplied issue still requires under 12 minutes and the ADR's handover at lines 110–112 explicitly forbids merging otherwise. Resolve the acceptance contract: either meet the threshold and record the measurement, or incorporate the owner's revised criterion into the issue and consistently update the ADR. The current evidence does not satisfy the supplied criterion.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  README, architecture documentation, ADR 0005, and ADR 0048 describe the new configuration and serial override. However, ADR 0048 simultaneously accepts 16.3 minutes and prohibits merging unless the longest job is under 12 minutes; the acceptance documentation needs reconciliation.

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

  tests/test_parallel_tests.py checks the default -n auto option, development dependency, and lock entry; these assertions fail against the original configuration. The worker test checks temporary-directory isolation and handles serial execution. Ariane reports a passing replay. Tests were not rerun during this read-only review.

- **not met**: The documentation the change affects is updated (C25).

  README, architecture documentation, ADR 0005, and ADR 0048 describe the new configuration and serial override. However, ADR 0048 simultaneously accepts 16.3 minutes and prohibits merging unless the longest job is under 12 minutes; the acceptance documentation needs reconciliation.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0048 records default parallelism, no grouped tests and its isolation rationale, the four-job matrix, caching, required-check migration, alternatives, and measured durations. No additional undocumented implementation choice was identified.

## Proposed learnings (not decided)

- Proposed: when an owner revises a measured acceptance threshold, update the issue and all merge-gate instructions together so reviewers have one consistent criterion.
