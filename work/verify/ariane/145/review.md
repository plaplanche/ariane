# Review 0

- Reviewed commit: `e9b7a15d0c3d2c1b0e4d0e5ea5b772c4873d8fce`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/replay.py:255`) Incoming changes select checks but do not contribute to their risk tier

  The update adds incoming paths to `changed` but discards their changed-line count. `risk_tier` therefore receives the ticket-only line count. With a two-line ticket and 1,000 incoming lines in the same module, a policy threshold of 300 incorrectly produces `low` and `ARIANE_FULL_SUITE=0`. A blocking check that runs integration tests only for the full suite can consequently pass without testing the merged combination, and that success is published after pushing. This makes a check pass wrongly. Compute the update's risk from both relevant diffs, with documented counting semantics, and add a regression test where the omitted full suite would fail.

- **minor** (`src/ariane/update.py:93`) Concurrent runs do not recognize an update process on Linux

  Updates register themselves, but `runs._started_as` recognizes only `start <number>`. Read-only probes confirmed that `ariane update 7` is rejected while `ariane start 7` is recognized. Interleaving: another ticket snapshots refs; the update registers and writes its merge commit; the other ticket verifies its snapshot, excludes the update from genuine runs, and stops on its legitimate branch change. Two updates can similarly stop each other. Extend registry recognition and its tests to the new command. This is not the accepted ADR 0017 impersonation residual.

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

  The new test modules cover successful merging, replay, review, statuses, refusals, conflicts, interrupted merges, remote movement including the final push race, record preservation, metrics and CLI dispatch. They depend on the new implementation. Ariane reports the suite passing; I did not rerun filesystem-writing tests in this read-only review. The findings identify additional missing regression cases.

- met: The documentation the change affects is updated (C25).

  README includes PowerShell and bash usage; architecture views, affected module documents, the new update module document, CLI reference and log catalogue are updated. Side-effect trace: CLI logging and lock/slot bookkeeping precede refusal checks; a needed fetch writes objects and tracking metadata; registration writes registry records; merge writes the tree, index and commit; journal/status/metrics writes follow; replay creates and removes clean trees and writes check records; review creates and removes its tree and writes review records; delivery restores and commits records, checks the guard, performs the leased push, writes the push journal, publishes statuses, and commits local delivery records. Conflict handling aborts before recording the stop; unresolved merges avoid record commits. Red/no-go paths commit stop records without pushing. Up-to-date exits before fetch and ticket-record writes, with technical logging and lock bookkeeping only.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0033's amendment records lease enforcement, additional record-preservation refusals, up-to-date logging, review numbering, incoming-path selection, residual provenance, metrics continuation and interrupted-merge handling. The risk-tier finding is an implementation inconsistency requiring correction and clarified counting semantics.

## Proposed learnings (not decided)

- When combining diffs for check selection, test that risk measurements and full-suite decisions cover the same changes.
- Adding a registered command requires testing its recognition by concurrent-run guards using its real command-line shape.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
