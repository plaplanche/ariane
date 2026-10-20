# Review 0

- Reviewed commit: `14aed46849415033ccb1ac01463dc5cad674cbfb`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/update.py:229`) Restoring pre-merge records deletes records brought by the base

  The folder is loaded before the merge and never reconciled afterward. If the base adds work/7/evidence.md, the clean merge writes that file and creates its merge commit. Ariane then writes journal, metrics, checks and review records. Delivery.commit_record calls TicketFolder.restore(), which deletes evidence.md because it is absent from the pre-merge snapshot, then commits that deletion. _require_replayed permits it because it is inside work/7/, and the leased push publishes it. The stop-record path also performs this destructive restore. This is blocking because it loses data from the resulting branch, even though recovery from Git history remains possible. Preserve incoming records or refuse such changes before merging; add regression coverage for both successful delivery and a post-merge stop.

- **blocking** (`tests/test_c11_update.py:1`) The required blocking test replay failed

  The current replay supplied with this review reports tests failing with exit 1 after 149.1 seconds. Ticket #145 explicitly requires every blocking check to pass. The passing reports committed under work/145/ and work/verify/ariane/145/ refer to older commits and cannot supersede this result. Diagnose the current failure and obtain a passing replay on the reviewed revision. I did not rerun tests because their fixtures write files, contrary to this review's read-only restriction.

- **blocking** Definition of done not met: check tests passes

  Replayed by Ariane: exit 1.

## Definition of done

- met: check lint passes

  Replayed by Ariane: exit 0.

- met: check format passes

  Replayed by Ariane: exit 0.

- met: check types passes

  Replayed by Ariane: exit 0.

- **not met**: check tests passes

  Replayed by Ariane: exit 1.

- met: check file length passes

  Replayed by Ariane: exit 0.

- met: The change is covered by tests that fail without it.

  There are 22 test_c11_update_* test functions, with additional parametrized cases. They exercise the new command, merge ancestry, refusals, conflicts, failed checks, no-go review, remote races, numbering and metrics; they depend on functionality absent from the base. This establishes targeted coverage, not a passing suite: the current blocking replay failed, and incoming-record preservation is untested.

- met: The documentation the change affects is updated (C25).

  README includes PowerShell and bash usage; the CLI reference, log catalogue, architecture views, affected module documents and new update module document are updated. Ariane reports the generated-reference check passing.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0033's amendment records the remote-enforced lease, refusals, review numbering, technical up-to-date log, selective checks, residual source, metrics continuation and interrupted-merge handling. The traced success path is merge writes, journal/metrics writes, replay trees and check outputs, reviewer tree and review records, records commit, remote guard, leased push, pushed journal entry, commit statuses, then local delivery-record commit. Conflict handling aborts before record writes; unresolved merges avoid record commits; red/no-go paths commit stop records without pushing.

## Proposed learnings (not decided)

- Proposed: When restoring an in-memory record snapshot after a merge, test additions and edits arriving from the base; a records-only delivery exemption can otherwise conceal data loss.
- Proposed: Treat check results as evidence for their exact revision; an older committed green report cannot override a current failed replay.

## Run

Slot 1 (`ARIANE_SLOT=1` for the setup, the checks and the reviewer, ADR 0050).
