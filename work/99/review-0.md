# Review 0

- Reviewed commit: `1a19dfe8f85a87ae7e379ff161e389ecbc8e4d87`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/report.py:29`) Shadow glob counts every committed metrics file of each clone again

  The report reads `shadows.glob('*/work/*/metrics.json')`. Each shadow clone is a full checkout of the base branch (`shadow._prepare` runs `git checkout -b <branch> <sha>`). Ticket records are committed and merged, so the clone also holds every `work/<m>/metrics.json` that was on main when it was cut. This worktree already has work/96..99/metrics.json. As a result, every delivered ticket on main shows up again once per shadow clone, as a `delivered` row. That inflates the ticket count, cost, agent time, rounds, first-pass rate, human time and gates bypassed, and it sends one extra tracker request per duplicate. Only `shadow/<n>/work/<n>/metrics.json` with the same n should be read (and only mode `shadow`). The tests miss this because their fake clones contain only the shadow ticket's own file. Add a test with a clone that also holds another ticket's delivered metrics.

- **blocking** (`src/ariane/flow.py:474`) Recording blocking checks red at delivery is not tested through the flow

  `test_c19_report_gates_blocking_red_at_delivery` writes `blocking_red_at_delivery=2` into the JSON by hand. No test runs `ariane start` (or `_deliver`) with a red blocking check and asserts that metrics.json records the count. Removing line 474 would not break any test, so this part of the 'gates bypassed' gate is not covered by a test that fails without it.

- **minor** (`src/ariane/github.py:169`) GitHubTracker.pull_request_state has no test

  There is no test for the real tracker's URL (head quoting, state=all, sort), for picking `merged_at` over `closed_at`, for an empty list giving None, or for a malformed response giving TrackerError. Only the in-memory double is exercised.

- **minor** (`docs/architecture/modules/cli.md:7`) cli module doc is stale

  It still describes `report` as 'cost, agent time, rounds and verdicts per ticket' and says only `start` and `verify --issue` build the tracker. It does not mention `_report_tracker`, which now builds a GitHubTracker from config and token for the report, or the report's new numbers. Ariane flagged this document as mapped but not updated.

- **minor** (`docs/architecture/modules/flow.md:12`) flow module doc does not mention blocking_red_at_delivery

  The Metrics bullet does not say that delivery records the number of red blocking checks (C19, ADR 0038). Ariane flagged this document as mapped but not updated.

- **minor** (`src/ariane/measures.py:57`) Docstrings contradict behaviour

  The `waiting` docstring says it returns None while the pull request is still open, but the code returns 0.0 for an open or absent pull request, as ADR 0038 says. The `restart_seconds` docstring says 'next `start` or `verify`', but only verify records are considered. `_STOPPED_OUTCOMES` holds the outcomes that are not stops, so the name is inverted.

- **minor** (`src/ariane/measures.py:61`) Offline report can make one slow request per delivered ticket

  After a TrackerError the next delivered ticket still queries the tracker, each with a 30 s timeout. On a hanging network the report can take minutes. Remember the first failure and skip the remaining requests.

- **minor** (`src/ariane/report.py:48`) Shadow pass window is filtered by --since

  The spec's 'last 10 shadow tickets' is computed only over the rows kept by `--since`, so with a recent date `shadow pass` reads 'no'. ADR 0038 does not record this choice.

- **blocking** Definition of done not met: The change is covered by tests that fail without it.

  tests/test_c19_report_measures.py has 11 tests that match the required name patterns and cover the report logic. However, the flow change that writes `blocking_red_at_delivery` (flow.py:474) and `GitHubTracker.pull_request_state` have no test. The duplicate-counting bug in the shadow glob also goes undetected.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  Updated: report.md, measures.md (new), tracker.md, github.md, metrics.md, 3-components.md, docs/reference/cli.md and README. Not updated: modules/cli.md (stale report description, the new tracker wiring is missing) and modules/flow.md (the new delivery metric is missing).

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

- **not met**: The change is covered by tests that fail without it.

  tests/test_c19_report_measures.py has 11 tests that match the required name patterns and cover the report logic. However, the flow change that writes `blocking_red_at_delivery` (flow.py:474) and `GitHubTracker.pull_request_state` have no test. The duplicate-counting bug in the shadow glob also goes undetected.

- **not met**: The documentation the change affects is updated (C25).

  Updated: report.md, measures.md (new), tracker.md, github.md, metrics.md, 3-components.md, docs/reference/cli.md and README. Not updated: modules/cli.md (stale report description, the new tracker wiring is missing) and modules/flow.md (the new delivery metric is missing).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0038 records: the tracker API and the `ariane/<n>` branch, an open or absent PR waiting 0, stops measured only to verify, the no-go merge rule without comparing heads, and shadow pass needing ten tickets. The `--since` effect on the shadow window is not recorded, which is minor.

## Proposed learnings (not decided)

- Shadow clones are full checkouts containing every committed work/<m>/metrics.json; anything globbing inside them must restrict to work/<n> of the clone's own number.
- When a flow writes a new metrics field, test it through the flow, not only by seeding the JSON the reader consumes.
- New Tracker protocol methods need a test against the GitHub implementation (URL and parsing), not only the in-memory double.
