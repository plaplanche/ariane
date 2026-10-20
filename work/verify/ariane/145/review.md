# Review 0

- Reviewed commit: `892ae3db2de8b1304fdcd270a3c88516a8b62728`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/ticket.py:99`) Interrupted record loading can delete existing ticket files

  load() populates _records incrementally. If reading review-0.md raises PermissionError, or Ctrl-C interrupts loading after journal.md, folder.exists() already returns true. execute_update() catches the exception and invokes the inherited stop handler before loading has completed. The write order is then: append the stop to journal.md; overwrite metrics.json using fresh, unresumed metrics; write status.md; restore() deletes every file absent from the partially populated _records; commit those changes. Consequently, later review records are deleted, earlier measurements are replaced, and an ignored plain file such as z-evidence.txt is irretrievably removed even though it passed _not_records(). This is blocking because it loses data. A read-only mocked reproduction confirmed that a failed read leaves exists() true and subsequent records absent from the restoration set. Load into a temporary mapping and publish it only after every read succeeds; errors or interruptions before successful loading must leave the existing folder untouched. Add regression tests for both read failure and interruption.

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

  The new test_c11_update tests cover successful merging, replay, review, fast-forward delivery, statuses, refusals, conflicts, abort failures, remote races, metrics, and selective checks. These depend on the new command and implementation. Ariane reports all checks passing; I did not rerun filesystem-writing tests in this read-only review. The partial-load failure above lacks coverage. Side-effect audit: entry creates log/lock/slot bookkeeping; ordinary refusals precede fetching, while the base-record refusal follows fetch writes. Up-to-date exits before fetching and writes only external bookkeeping/logs. Active updates register the run, fetch Git objects/tracking metadata, merge the tree/index/history, then write journal and metrics. Conflicts abort before recording; unresolved merges avoid record writes. Successful merges write replay records, create/setup/run/remove replay trees, create/run/remove the reviewer tree, and write review/metrics records. Red or no-go outcomes write and commit stop records locally. Go commits records, checks guards, pushes with an atomic expected-head lease, journals the push, publishes statuses, and commits final records locally. No new pull request is opened.

- met: The documentation the change affects is updated (C25).

  README includes PowerShell and bash usage. The update module documentation, affected module pages, context/container/component diagrams, CLI reference, and log catalogue are updated. Ariane reports the generated-reference check passing.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0033's amendment records the push lease, additional refusals, review numbering, no-op logging, check selection, residual provenance, metrics continuation, unresolved-merge handling, and stopped-branch recovery.

## Proposed learnings (not decided)

- Proposed: Load persistent records atomically before enabling any recovery handler that rewrites or deletes files; test interruptions during loading as well as during merging.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
