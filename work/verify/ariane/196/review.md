# Review 0

- Reviewed commit: `7b13bdaf0c2bc5a1e899469b01e200a2dcffae93`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/flow.py:96`) Early start failures never record a stop category

  Issue-gate refusals return at line 71, and lock, slot, registry and preparation failures return here before Metrics exists. None writes category-bearing metrics. The ticket explicitly requires spec for issue-gate failures and infra for unavailable slots or locks. The new tests exercise failures after run construction, so they miss these paths. Record these attempts separately without overwriting an active run's metrics.

- **blocking** (`src/ariane/report.py:37`) The report excludes externally saved stop metrics

  An interrupted first setup logs the stop, kills survivors, then writes categorized metrics to <repo>.ariane/stopped/<n>/metrics.json. A refused verification similarly writes to <repo>.ariane/verify/<slug>/metrics.json. This discovery list reads neither location, so those stops never reach category_lines; with only such records, the report says no metrics exist. Include these records with appropriate identity and deduplication. tests/test_c10_stopped_metrics.py already establishes the first-setup storage path, but no new test checks its report visibility.

- **blocking** (`src/ariane/github.py:245`) Historical changes requests are attributed to later go verdicts

  changes_requested accepts any human CHANGES_REQUESTED review, without its submission time or a boundary identifying Ariane's go. A human can request changes, the owner can fix them, and ariane verify can then record go; the report still counts the earlier request as an escape of that later review. This violates 'go followed ... by'. The request path records reviewer-session metrics, validates the session, records the settled review and commits verification records; report-time GETs then inspect all historical reviews without comparing their order. Preserve the go time and PR identity and filter subsequent events. Looking up only the latest PR by branch also cannot guarantee the event belongs to the same PR.

- **blocking** (`src/ariane/review_escapes.py:108`) The five-ticket threshold counts records instead of distinct tickets

  group.tickets increments for every qualifying row, although group.seen separately tracks distinct ticket numbers. Multiple takeover records for one ticket can therefore satisfy MIN_TICKETS. A read-only in-memory reproduction with five rows for ticket 7 prints '5 reviews over 1 tickets' and 'escape rate 5/5 (100%) over 5 tickets'. The acceptance criterion forbids rates below five tickets. Track distinct eligible tickets for the threshold and define how repeated observations contribute to escapes and the denominator.

- **minor** (`docs/architecture/modules/replay.md:33`) Affected replay and checks documentation was not updated

  The replay documentation still describes recording only the first-pass verdict, omitting the newly recorded per-session verdict and findings and propagation of stop categories. docs/architecture/modules/checks.md likewise omits the new guard category. Both mapped module documents were untouched despite the explicit documentation requirement.

- **blocking** Definition of done not met: The change is covered by tests that fail without it.

  The new tests directly exercise new output and category fields and would fail without the implementation; Ariane reports all checks passing. Coverage is incomplete for explicitly required early stop paths, external stop-record discovery, event ordering and distinct-ticket thresholds. I ran read-only in-memory reproductions, not the filesystem-writing test suite.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  README, benchmark, ADR and most affected architecture documents are updated. The mapped checks and replay module documents omit their changed behavior. Generated references reportedly pass their consistency check; unchanged generated files alone are not a defect.

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

  The new tests directly exercise new output and category fields and would fail without the implementation; Ariane reports all checks passing. Coverage is incomplete for explicitly required early stop paths, external stop-record discovery, event ordering and distinct-ticket thresholds. I ran read-only in-memory reproductions, not the filesystem-writing test suite.

- **not met**: The documentation the change affects is updated (C25).

  README, benchmark, ADR and most affected architecture documents are updated. The mapped checks and replay module documents omit their changed behavior. Generated references reportedly pass their consistency check; unchanged generated files alone are not a defect.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0058 records escape attribution, categories, grouping, thresholds, tracker-time reads, the normal-report section and compatibility with older metrics. Its exclusion of issue-gate refusals does not override the ticket's explicit requirement, as identified above.

## Proposed learnings (not decided)

- Proposed: Test measurement features from failure entry point through persisted record discovery to report output.
- Proposed: Attribute later outcomes using stable PR identity and event timestamps.
- Proposed: Test minimum-sample thresholds with repeated records for the same ticket.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
