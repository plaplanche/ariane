# Review 1

- Reviewed commit: `d2d431b30c4712170aa2a9cf015b0a473a735a42`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/full_replay.py:117`) A later replay stop discards an already-observed escape

  Reproduced with two checks skipped in the selective round: full check A fails, then B's setup raises Stop. The sequence is: create A's tree, run setup and A, remove A's tree, create B's tree, fail setup, remove B's tree, write metrics with empty escapes, write a stop-only full-replay.md, journal the stop, and commit. replay_each retains A's result only locally and raises without returning it. Consequently A's failure and output disappear, no ticket.checks.escape is journaled, and no failing status or PR comment is posted. This violates the required handling of a check that fails in the full replay and loses observed failure data. Preserve completed results across stops and record/publish their escapes even when later checks cannot finish. Add a regression covering this sequence.

- **blocking** (`src/ariane/full_replay.py:190`) Aggregate success can overwrite a configured check's failure status

  The configuration accepts a check named full-replay, while delivery publishes individual checks under ariane/<name>. Reproduced with an advisory full-replay check that fails both rounds and another skipped check that triggers sampling: delivery first writes failure to ariane/full-replay; escapes excludes the already-failing check; _publish then writes success to the same context on the same SHA. The aggregate result therefore replaces the actual check failure with success. No concurrency is needed. This remains blocking under the proportionality rule because it makes a check pass wrongly. Reserve the aggregate status name during configuration validation or otherwise prevent context collisions, and test this case.

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

  The added tests exercise sampling, post-delivery ordering, partial-check escapes, publication, unchanged delivery results, report aggregation, and configuration parsing; these depend on the new behavior. Ariane reports the suite green. Independent pytest execution was unavailable because pytest is not installed. Both findings were independently reproduced using memory-only stubs; regression coverage for them is missing.

- met: The documentation the change affects is updated (C25).

  README, the requested module documentation, component sequence, example configuration, generated schema, and log catalogue are updated. The new full_replay module is documented. The normal side-effect order matches the documented sequence: delivery records and commit, push, pushed journal, PR creation, delivered journal, optional label, check statuses, local PR record commit; then replay journal, replay-tree/setup/cache/check writes and cleanup, metrics and replay record, escape/pass journal, aggregate status, optional comment, and local replay-record commit.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ADR 0056 amendment records deterministic sampling, defaults, replay timing and environment, escape counting, stopped-run treatment, publication failures, local-only records, report discovery, and how the owner uses the escape-rate warning.

## Proposed learnings (not decided)

- Proposed: preserve completed check results when a later setup, guard, or interruption stops a replay.
- Proposed: validate configured check names against reserved aggregate status contexts before publishing statuses.
