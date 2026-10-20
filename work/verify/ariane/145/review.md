# Review 0

- Reviewed commit: `9547f51cf2814123a0dc58d3e98c8396b8ba7fda`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/update.py:96`) The update trusts accepted residuals from the unmerged ticket

  _UpdateRun inherits _TicketRun.__init__, which reads residuals_in(worktree). For update, that tree contains the delivered ticket, not the base commit. An ADR marker added by the ticket therefore becomes an owner-accepted residual in the next review, even though the owner has never merged it. The sequence is: read ticket-authored residuals, merge, replay, instruct the reviewer to downgrade matching findings, then push on go. This breaks ADR 0057's security boundary: a change can grant itself a review exemption. Read accepted_residuals from the pinned base commit and add a regression test showing that ticket-only markers never enter the accepted-residuals prompt.

- **blocking** (`src/ariane/replay.py:255`) Incoming renames can skip a blocking check and publish success

  git.changed_between uses diff --name-only, which reports only the destination of a detected rename. If the base moves src/a.py to lib/a.py while the ticket changes an unrelated file, the base-to-merge diff contains neither side of that rename and the incoming listing adds only lib/a.py. A blocking check scoped to src/** is consequently skipped. The sequence is: lose the source path, select checks, create a passing skipped result, commit that report, push, and publish a success status without running the check. This makes a check pass wrongly and violates ADR 0056's explicit requirement to include both sides of renames. Use git.changes plus checks.changed_files for incoming changes and test a rename out of a blocking check's scope.

- **minor** (`src/ariane/update.py:93`) Concurrent update processes are not recognized by the Linux run guard

  The update registers itself, but runs._started_as recognizes only command lines containing start <number>. A concurrent start or update therefore never considers an update process genuine on Linux. When that update writes its merge or records commit, the other run sees an unauthorized branch change and stops. Extend recognition to update and test overlapping runs. This is an availability defect; it fails closed rather than permitting an unsafe push.

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

  tests/test_c11_update.py adds integration coverage for successful merging, replay, review, statuses, refusals, conflicts, red checks, no-go, remote movement including lease races, interrupted merges, metrics and CLI dispatch. These exercise the new command and cannot pass without it. The owner reports green checks; I did not rerun write-producing tests in this read-only checkout. The findings identify missing regression cases. Side-effect audit: CLI logging and lock/slot bookkeeping precede refusals; the up-to-date path emits a technical log without fetching. An active update fetches objects/tracking metadata, registers the run, then writes merge objects/index/tree/ref state. A conflict invokes abort before journal or record writes; an unresolved merge leaves records untouched. A completed merge writes journal/metrics/status, creates replay trees and any setup/cache artifacts, writes changed-file listings, runs checks, removes replay trees, writes reports, creates the reviewer tree and session records, removes that tree, and writes the review. Red/no-go paths write and commit stop records without pushing. Success writes metrics/status, restores and commits records, verifies replay equivalence and guards, pushes with an atomic expected-head lease, writes the push journal, publishes statuses, and commits final records locally. Registry teardown appends history and removes the live entry. Git commands and failures also produce technical logs.

- met: The documentation the change affects is updated (C25).

  README includes PowerShell and bash usage; ADR 0033 is amended; the CLI reference and log catalogue include update; context, container and component diagrams are updated; update has a module document and affected module documentation is updated. The reported generated-reference check passed.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0033's amendment records the push lease, refusal semantics, no-write up-to-date behavior, review numbering, incoming-change selection, metrics continuation and handling of unresolved merges and stops. The blocking findings are implementation violations of existing decisions, not missing design decisions.

## Proposed learnings (not decided)

- When reusing a run class, revalidate constructor assumptions about whether its working tree contains trusted base code or an unmerged change.
- Use the same rename-aware change representation for every input to check selection; test moves out of a check's scope.
- Adding a registered command also requires updating process-authentication rules and concurrent-run tests.

## Run

Slot 1 (`ARIANE_SLOT=1` for the setup, the checks and the reviewer, ADR 0050).
