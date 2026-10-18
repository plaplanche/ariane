# Review 0

- Reviewed commit: `eb008d89b8f5aafa00f5c9f6d65d550b91928517`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/runs.py:192`) Another run's agent can forge a trusted registration

  genuine() excludes only descendants of the current Ariane process, and _started_as() accepts any command containing adjacent arguments 'start <number>'. Interleaving: run B's agent starts a Python process with arguments 'start 9', writes runs/9 naming that PID, then creates ariane/9 and its allowed keys. Run A's watcher accepts that process because it is not A's descendant; A's subsequent guard suppresses these unauthorized changes. A read-only mocked reproduction confirmed that such a Python command is accepted. On Windows and macOS even the argument check is absent. Registration must establish that the process is an authorized Ariane run for this repository, not merely a live process outside this run's descendants. Add a cross-process forgery regression test.

- **blocking** (`src/ariane/runs.py:246`) Polling loses legitimate runs that end between observations

  The decided spec includes tickets running at any time during the session. Interleaving: A's watcher reads the registry; B writes its registration, creates its branch, stops during preparation or setup, appends ended.jsonl and deletes its entry; A's next observation finds only the history. Since A never witnessed B live, during() excludes B and foreign_changes() stops A on B's legitimate branch. The 0.2-second polling interval provides no guarantee, especially when the watcher is delayed. The ADR acknowledges this behavior but it contradicts the ticket requirement. Tests shorten the interval to 0.01 seconds and do not deterministically exercise this gap. Use an authenticated registration/history mechanism that preserves every overlapping run, with a test forcing B's entire lifetime between A's observations.

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

  The new test module covers registered branch changes, forbidden keys, hooks, cleanup and registry races; these require the new implementation. Ariane reports passing replayed tests. Tests were inspected, not rerun because they write files; the blocking cross-process and missed-observation cases remain uncovered.

- met: The documentation the change affects is updated (C25).

  README, component sequence, flow/git module documentation, the new runs module and collaboration diagrams are updated. Existing log event text is unchanged.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0017 records registry locking, history, publication order, process checks, polling and exact configuration-key filtering. Recording the polling limitation does not resolve its conflict with the decided spec.

## Proposed learnings (not decided)

- Proposed: Test concurrent authorization using separate process trees; same-process mocks can hide ancestry-check weaknesses.
- Proposed: Polling cannot guarantee observation of every overlapping operation; test a complete operation between consecutive observations.
