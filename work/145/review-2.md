# Review 2

- Reviewed commit: `c6678fd9c370496447cd562fac307a0d6da8dd0a`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/update.py:209`) An interrupted merge can have its unresolved index reset by stop recording

  If Ctrl-C interrupts the merge or its abort after Git has written merge state, KeyboardInterrupt bypasses the Unresolved handler and enters _stopped. The write order becomes: merge writes index/files/MERGE_HEAD; stop writes journal, metrics and status; _commit_record calls git.commit, which first runs git reset --quiet. That reset discards the unresolved index and merge metadata before restoration has been checked, leaving conflict markers without the merge state needed to abort normally. Errors while inspecting or aborting a failed merge take the same path. Before recording any stop, establish that the merge completed or was restored; otherwise use the no-write unresolved path. Add interruption and abort-exception tests, not only abort return-code tests.

- **blocking** (`src/ariane/update.py:162`) The up-to-date check happens after a repository-writing fetch

  _refuse_or_read fetches before update checks ancestry at line 84. Fetch writes FETCH_HEAD and can update origin/<base>, its reflog and the object database even when the command subsequently reports 'up to date' and promises nothing written. For example, the local ticket can already contain the remote base while its remote-tracking ref is stale. The existing no-op test checks only the ticket HEAD, working-tree status, pushes and sessions, so it misses these writes. Use the base SHA already returned by remote_refs to decide the known-ancestor no-op before fetching, and test Git metadata as well as tracked files.

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

  The new file contains 16 test functions, with additional parametrized cases, covering the command, merge, refusals, conflicts, review/check failures, remote races and metrics. They depend on the new implementation. Ariane reports passing checks; I did not execute tests because this review permits reads only. Interruption and no-op metadata coverage remain missing.

- met: The documentation the change affects is updated (C25).

  README examples, CLI reference, log catalogue, architecture diagrams and affected module documentation are updated, including the new update module. The documented no-write guarantee is not fully implemented.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0033's amendment records the lease, refusal rules, review numbering, metrics continuation, technical no-op logging and stopped-branch recovery. Side-effect trace: lock/slot files, fetch, run registration, merge writes, journal/metrics/status writes, replay tree/setup/cache/check writes and cleanup, reviewer tree and records, pre-push records commit, leased remote push, pushed journal entry, commit statuses, local delivery-record commit, registration cleanup. Red/no-go paths record a local stop without pushing; ordinary conflicts abort before recording; unresolved aborts avoid record writes. The exceptional merge path and no-op ordering defects are identified above.

## Proposed learnings (not decided)

- Treat interruption and exceptions during merge recovery as unresolved state until restoration is verified; recording a stop can itself destroy recovery metadata.
- Test no-write guarantees against Git metadata as well as tracked files and branch heads.
- Keep the remote lease and explicit ancestry check together: they enforce both concurrency protection and fast-forward-only delivery.
