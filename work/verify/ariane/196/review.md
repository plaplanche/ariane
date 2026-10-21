# Review 0

- Reviewed commit: `09b16847e8acfa42a95738d209ae302b95c2a7d8`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/verify.py:407`) Verification marks unpublished reviews as pushed

  The sequence is finish('delivered'), which marks the review pushed, then _before_commit(), then writing and committing the records. No push occurs. report reads these local records and trusts that marker. If an existing PR is subsequently closed without merge, an unpublished verification is counted as an escape; a read-only reproduction confirmed this. If the pre-commit guard refuses, keep_stopped also retains the marker. Establish publication from the remote reviewed commit before counting a verification, and test both unpublished verification and pre-commit refusal.

- **blocking** (`src/ariane/update.py:111`) Early update failures never record stop categories

  A lock or slot refusal returns directly here without writing metrics; tracker failures at lines 75–78 likewise leave no record. These attempts disappear from the category report, although the ticket explicitly requires each start/update stop path and names unavailable locks and slots as infra. Preserve the existing delivery record and write a separate attempt record, as start now does. The update tests cover only merge, checks and review failures, so they miss these required paths.

- **minor** (`docs/architecture/modules/review_escapes.md:22`) Escape eligibility documentation contradicts the implementation

  This paragraph requires outcome delivered, no category, and only the last review. pushed_gos instead includes every marked go, including an earlier delivery whose subsequent update stopped with a category. The new update-attribution test explicitly requires that behavior. Update this paragraph and its workflow diagram to describe the implemented eligibility rules.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  README, benchmark and affected module documentation were updated, and the read-only generated-documentation check passed. However, the escape eligibility description contradicts the code and tests.

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

  The new escape, grouping, threshold, verdict and category assertions depend on functionality absent from the base. Seventeen named test functions include additional parametrized cases. Ariane reports the suite passing; coverage gaps are identified above. No filesystem-writing tests were rerun during this read-only review.

- **not met**: The documentation the change affects is updated (C25).

  README, benchmark and affected module documentation were updated, and the read-only generated-documentation check passed. However, the escape eligibility description contradicts the code and tests.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0058 records escape eligibility, grouping, thresholds, categories, tracker reads, attempt storage and attribution choices. Recording a decision does not resolve the requirement violations identified above.

## Proposed learnings (not decided)

- Proposed: distinguish reviewed, committed and published states; test failures between those transitions.
- Proposed: enumerate stop paths from exception handlers, including failures before a run exists, rather than testing only one example per category.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
