# Review 0

- Reviewed commit: `ea7820c0aa65b4e3cd032eb3188ba2fdbe6b8306`
- Reviewer model: gpt-6-astra
- Verdict: **go**

## Findings

- **minor** (`tests/test_c21_env_allow_list.py:56`) Add coverage of environment propagation through orchestration

  The environment tests call context.untrusted_environment directly. The flow test verifies the journal entry, but not what setup, checks or agents receive. Removing declared=config.env from flow or verify would therefore escape these assertions. Add integration coverage that observes declared and undeclared variables at those process boundaries.

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

  The new tests exercise undeclared-variable exclusion, explicit declarations, extended secret patterns, proxy credentials and schema validation, which the previous implementation lacks. Six pure environment test functions passed when executed directly without writes. Pytest is unavailable in the review interpreter; the supplied Ariane replay reports the full suite passing.

- met: The documentation the change affects is updated (C25).

  README, example and project configuration, affected module documentation, schema reference and log catalogue are updated. The supplied docs-reference check passed. Side-effect tracing confirms environments are filtered before subprocess execution. Start runs setup, creates ticket records and metrics, logs ticket.started and the declaration warning, then commits records and starts the agent. Replay and verify pass the filtered environment to setup and checks. Commit resets the index, removes requested entries, stages paths, checks for changes, then commits with identity variables restored.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ADR 0024 amendment records matching rules, platform-specific variables, credential-bearing proxy handling, secret-pattern boundaries, commit identity restoration, warning severity and verify's lack of a persisted declaration journal.

## Proposed learnings (not decided)

- Proposed: Test environment security policies both as pure filtering functions and at each orchestration boundary that passes environments to subprocesses.
