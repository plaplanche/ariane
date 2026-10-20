# Review 0

- Reviewed commit: `394d4c475e96dee56e6081455ca67d0e716a11a0`
- Reviewer model: gpt-6-astra
- Verdict: **go**

## Findings

- **minor** (`README.md:88`) Example selects changed tests rather than related tests

  A low-risk change to src/a.py and tests/test_b.py runs only test_b.py, potentially omitting unchanged tests covering a.py. Deleted test files also become invalid pytest arguments. Use a conservative full-suite fallback when source files change or selected tests no longer exist, or clearly label the example's limitations.

- **minor** (`src/ariane/verify.py:299`) Verification omits the risk-tier journal event

  The verification path computes and reports the tier but never emits ticket.checks.risk_tier, unlike replay.replay. Emit the event into its temporary journal when the ticket folder is created, and cover this path with a verification test.

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

  tests/test_c9_risk_tier.py exercises default and measured tiers, every high-risk trigger, full_when, failed-round escalation, reports, reviewer sizing and schema rejection. These assertions depend on the added behavior. Supplied replay results report passing tests; integration tests were not rerun in this read-only review.

- met: The documentation the change affects is updated (C25).

  Affected module documentation, the new risk module page, architecture diagrams, configuration schema, log catalogue, example configuration and README are updated. The README example has the minor limitation noted above.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0056 records thresholds, module-root interpretation, unmatched paths, failure escalation, diff-based computation, environment semantics and compatibility with existing reviewer sizing.

## Proposed learnings (not decided)

- Test risk-tier propagation through both ticket replay and standalone verification.
- Related-test examples should fall back conservatively when changed files cannot be mapped reliably to runnable tests.
