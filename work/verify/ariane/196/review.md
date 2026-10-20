# Review 0

- Reviewed commit: `04c992c26fc55f6f73b15de46344a88e5d54373c`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/report.py:77`) Concurrent refusal records can be replaced by the active run

  The newly loaded refusal records pass through _with_local, which identifies runs solely by (ticket, started). Metrics.started has only second precision. Interleaving: A acquires the ticket lock, registers and prepares its worktree, then starts its metrics at time T; B attempts the same ticket within that second, fails the lock, creates a unique refused directory and writes its infra metrics with started=T; A writes its own metrics with the same identity. Reporting replaces B's refusal with A's worktree record. If A is running or delivered green, the infra stop disappears; when A also has a merged record, its reviews and costs can instead be duplicated. An in-memory reproduction returned no category lines for this refusal. Preserve refusal identities separately from merged/worktree deduplication and add a same-second concurrent-attempt regression test.

- **blocking** (`src/ariane/flow.py:68`) Interrupting issue lookup records no stop category

  Ctrl-C during tracker.read_issue takes this return path without calling keep_refused. The sequence is tracker read, KeyboardInterrupt, return exit 130: there is no metrics directory creation or metrics write. This contradicts the requirement that every non-green start outcome records a category and ADR 0058's explicit classification of interrupts as infra. A mocked read-only reproduction confirmed exit 130 and zero keep_refused calls. Record this interruption through the unique refusal-record path and test that the report includes it.

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

  The new test_c19_review_escapes_* tests assert newly introduced escape counts, grouping, thresholds, reviewer-session fields and stop categories, so they fail without the implementation. Ariane reports the suite green. The concurrent-identity and interrupted-lookup cases above remain uncovered; filesystem-writing tests were not rerun during this read-only review.

- met: The documentation the change affects is updated (C25).

  README, benchmark documentation and affected architecture modules are updated. PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python scripts/generate_docs.py --check passed, confirming generated references and logs remain current despite having no textual diff.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0058 records the escape definition, grouping and threshold, tracker reads, temporal ordering, categories, refusal storage, legacy handling and reserved merge/CI categories. The findings concern implementation gaps in those decisions.

## Proposed learnings (not decided)

- Proposed: Give attempts a durable unique identity; second-resolution timestamps are insufficient for deduplicating concurrent metrics records.
- Proposed: Test stop-category completeness at early returns as well as exceptions inside an established run, including interrupts during tracker lookup.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
