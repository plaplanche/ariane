# Review 0

- Reviewed commit: `eeb3f33ee2c2e1b4be4a8dc0ded197ccc9574ad8`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/config.py:451`) Reserve the full-replay status name case-insensitively

  The reservation rejects only lowercase 'full-replay'; read-only execution confirmed that 'Full-Replay' and 'FULL-REPLAY' are accepted. GitHub status contexts are case-insensitive ([GitHub documentation](https://docs.github.com/en/rest/commits/statuses#create-a-commit-status)). Reproduction: configure an advisory check named 'Full-Replay' that fails with ARIANE_FULL_SUITE=0 and passes with 1, and sample at 1. Delivery pushes the commit, opens the PR, publishes the check's failure as ariane/Full-Replay, and commits the delivery record locally. The full replay then runs, writes its metrics, record and journal, publishes success as ariane/full-replay on the same pushed commit, and commits its records locally. That second status replaces the first context's failure. This makes a check pass wrongly and violates the intended status isolation. Reject case variants before delivery and add regression tests; the current reservation test exercises only lowercase.

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

  Found 18 test_c19_full_replay_* functions in the new test module and one in test_github.py, covering sampling, delivery ordering, escapes, redaction, statuses, interruption and reporting. These exercise newly added behavior absent from the base. Read-only sampling/configuration smoke checks passed. The integration suite was not independently rerun because it writes files and worktrees; Ariane reports it green. The case-insensitive collision remains uncovered.

- met: The documentation the change affects is updated (C25).

  The requested module documentation, component run sequence, README, example configuration, generated schema and log catalogue are updated, with a new full_replay module document. The documented ordering matches the normal path: delivery records and commit, guarded push, PR creation, labels/statuses, local PR-record commit; then sampling, replay-tree creation/setup and cache writes, changed-file listings, checks and verification logs, tree removal, metrics/report/journal writes, full-replay status and escape comment, and a local record commit without another push.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0056 records the sampling algorithm, post-delivery placement, local-only persistence and report discovery, advisory failures, interruption behavior, status reservation, escape aggregation, and the owner's use of the warning threshold.

## Proposed learnings (not decided)

- Proposed: reserve external status identifiers using the provider's equality rules, and test that publishing an aggregate status cannot overwrite an individual check's failure.

## Run

Slot 0 (`ARIANE_SLOT=0` for the setup, the checks and the reviewer, ADR 0050).
