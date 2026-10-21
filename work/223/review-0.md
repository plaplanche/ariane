# Review 0

- Reviewed commit: `2755db39aa7ea44eb960569088ac51c79afa0796`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/next_ticket.py:315`) Confirmation is not reserved or consumed before starting

  The write order is: proposal computation may reclaim stale registry entries and opens slot lock files; then DELETE ready label, POST ready label, create/open logs/N.out, spawn the child, append next.md, emit next.started. The proposal check and child registration are separate, with no reservation between them. Two --start calls can both read the same proposal and both relabel and spawn before either child registers. A read-only mocked reproduction launched #7 twice and removed its label twice. The child's per-ticket lock prevents simultaneous execution of that ticket, but does not prevent duplicate external writes or launches. Likewise, another ticket sharing its files can register after the proposal snapshot and before launch; flow.start never repeats the overlap check. Reserve and consume the confirmed proposal across the launch handoff, coordinating concurrent starts, and test these interleavings.

- **blocking** (`src/ariane/next_ticket.py:142`) Different overlapping globs incorrectly pass the shared-file check

  shared() compares a glob only with a literal path, so expected files docs/** and docs/architecture/** return no overlap. The same happens with src/**/*.py and src/ariane/*.py, even when matching files exist in the checkout. Both cases were reproduced without writing files. A running ticket and candidate described through supported folders or label globs can therefore be reported as having no shared file. ADR 0059 records this limitation, but it is not an owner-accepted residual and contradicts the ticket's expected-file safety check. Expand against known files and conservatively handle potentially overlapping patterns; add regression coverage.

- **blocking** (`src/ariane/next_ticket.py:209`) Unreadable running changes are treated as no changes

  Git errors are suppressed and leave found empty; an unreadable fallback brief is also suppressed. This makes the overlap check pass wrongly rather than reporting that safety cannot be established. It can occur during ordinary startup: flow.start registers the run before prepare creates its branch and worktree. A concurrent next command can observe that registration, fail to read the branch, and propose a conflicting issue. For a running issue outside the queue, both changed and expected files can become empty; a read-only reproduction confirmed this. Refuse proposals while a running ticket's footprint is unavailable and test startup and Git-read failures.

- **blocking** (`src/ariane/next_ticket.py:215`) Running tickets outside the queue lose their label-based expected files

  When a running issue lacks next_label, its labels are replaced with an empty tuple and only its brief is read. For example, a manually started ticket labelled docs with next.paths.docs = ['docs/**'] loses that expected footprint. Before it changes a documentation file, a queued candidate naming docs/architecture/cli.md is incorrectly proposed. The ticket requires every running ticket's expected files, not only those still queued. Retrieve or persist the running issue's labels and test a running ticket without the queue label.

- **blocking** (`src/ariane/next_ticket.py:340`) A successful launch can escape the required start record

  The child is spawned before the start entry is appended. If opening or writing next.md fails, the child continues, no start record exists, and cli._next reports 'Did nothing'. A crash between launch and record has the same missing-record outcome. This violates the explicit requirement that every start be recorded and leaves the previous confirmation reusable during the registration gap. Persist a recoverable start intent before external side effects, reconcile the launch result, and distinguish failures after launch from actions that did nothing. Test a record failure after a successful launch.

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

  There are 18 new test_c23_next_* tests covering the new API, queue, dependencies, overlap, blockers, confirmation, recording and spawning; they depend on functionality absent from the base. Ariane reports the test suite passing. The reviewer used read-only probes rather than rerunning tests that create files. Concurrency and failure-path coverage remains missing as described in the findings.

- met: The documentation the change affects is updated (C25).

  README, container/component views, next_ticket and globs module documentation, affected existing module documents, example configuration, generated CLI/schema references and log catalogue are updated. Ariane reports the generated-reference check passing.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0059 records queue ordering and fallback, dependency syntax, path inference, running-file sources, blockers, confirmation comparison, detached launch and recording choices. Recording a choice does not resolve the safety defects identified above.

## Proposed learnings (not decided)

- Proposed: Treat confirmation as a consumable reservation that survives the handoff to a background process.
- Proposed: Missing overlap evidence must block a safety proposal rather than count as an empty footprint.
- Proposed: Test the interval between process launch and registration, and failures between external effects and audit recording.
