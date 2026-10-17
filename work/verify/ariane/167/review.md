# Review 0

- Reviewed commit: `e651ba300c6e28bad699b0f0f9f6790debec990e`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/verify.py:303`) Verification deletes its truncation journal

  For an oversized diff, verification writes ticket.review.diff_truncated into the temporary folder's journal, runs the reviewer, commits only review.md, checks.md and metrics.json, then deletes the temporary folder at line 194. The committed review record does not contain the truncation warning or missing paths. Consequently the required journal evidence disappears after verification. Preserve the journal or explicitly persist this evidence in the verification records, and test the records after verify returns.

- **blocking** (`src/ariane/flow.py:589`) An interrupted initial setup loses survivor metrics

  The initial setup runs before folder.create. If it starts a detached child and is interrupted, process teardown kills and records the child, then execute enters _stopped. That method consumes take_killed and updates the in-memory counter, but folder.exists() is false, so metrics.finish and every metrics write are skipped. The run returns without metrics.json recording the survivor, contrary to the ticket and ADR's interrupted-command guarantee. Persist stopped metrics even before the ticket folder opens. Existing interruption coverage starts inside an agent session, after folder creation, and misses this path.

- **minor** (`docs/architecture/modules/logs.md:1`) Touched logs module documentation was not updated

  The log catalogue was updated, and this module page still accurately links to it, but the project's explicit rule requires updating the module document for every touched module. Add the new reviewer-integrity logging responsibility and its ADR 0031 reference.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  README, ADR 0031, the log catalogue and the principal affected module pages were updated. docs/architecture/modules/logs.md remains untouched despite the explicit per-module documentation requirement.

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

  The new integrity tests assert external-instruction rejection, complete changed-file lists and PR truncation warnings, and detached-process cleanup with survivor metrics. These behaviors are absent from the base implementation. Ariane reports the suite passing; I inspected the tests without rerunning filesystem-writing tests in this read-only review. The findings identify additional uncovered paths.

- **not met**: The documentation the change affects is updated (C25).

  README, ADR 0031, the log catalogue and the principal affected module pages were updated. docs/architecture/modules/logs.md remains untouched despite the explicit per-module documentation requirement.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ADR 0031 amendment records runtime-specific snapshot coverage, cleanup timing and scan limits, timeout counting, stopped-verification metrics storage, and platform residuals.

## Proposed learnings (not decided)

- Proposed: Test audit evidence after temporary-directory cleanup, not merely when it is first written.
- Proposed: Exercise interruption before record initialization as well as during established sessions.
