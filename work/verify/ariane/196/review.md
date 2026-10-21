# Review 0

- Reviewed commit: `a1e1c05abeb61ac44a3e4dbf43c01a29ae729c8a`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/review_escapes.py:73`) A failed update erases an already-pushed go from escape accounting

  pushed_gos infers push history from the final outcome. After a successful delivery, an update can conflict or fail checks before adding another review. Its stop changes the outcome and category, but the last review is still the original, already-pushed go. This code removes it. An in-memory reproduction changed a reported human-review escape from 1 escape/1 ticket to 0 escapes/0 tickets merely by setting the update outcome to needs a human/category merge. Delivery ordering also disproves the inverse assumption: metrics are marked delivered, records committed, guards checked, the branch pushed, and only then the PR, statuses and local records are written; a failure after the push can produce a stopped outcome despite successful publication. Record publication identity per review instead of deriving it from the latest outcome. Add report assertions after updates that stop before review and after delivery failures following a push.

- **blocking** (`src/ariane/update.py:293`) Unresolved merge stops never record a category

  The update writes merge state through git merge, attempts git merge --abort, and routes a failed abort or interrupted unresolved merge to _left_unresolved. That path emits a log, kills survivors and returns needs a human without writing metrics. The previous delivered metrics remain, so report omits this stop entirely. This violates the explicit requirement that every non-green outcome and each update stop path records its category. Preserving the unresolved index is necessary, but an external metrics record can preserve the stop without committing or resetting it. ADR 0058 calls this an accepted residual, but it is not among the owner's supplied accepted residuals. Existing abort-failure tests do not assert category recording.

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

  New tests assert escape counts, grouping, thresholds, category fields and tracker review reads that the base implementation lacks. More than five matching tests exist, and Ariane reports the suite passing. Coverage misses the blocking cases above; this review used a read-only in-memory reproduction rather than rerunning filesystem-writing tests.

- met: The documentation the change affects is updated (C25).

  README, benchmark, affected module documentation and component diagrams are updated. Independently ran scripts/generate_docs.py --check successfully, confirming generated references and logs remain current.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0058 records escape definitions, grouping, thresholds, categories, tracker reads, timestamp attribution and external refusal records. Recording a proposed residual does not establish owner acceptance or override the ticket's requirements.

## Proposed learnings (not decided)

- Proposed: Record which review was actually published; a run's final outcome cannot reconstruct publication history.
- Proposed: Test report results after orchestration failures, not only the category written by each failure path.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
