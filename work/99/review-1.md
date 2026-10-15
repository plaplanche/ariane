# Review 1

- Reviewed commit: `daf23b40248b602d93d8de665cb79fb152c82951`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/measures.py:47`) Malformed timestamps now crash the report instead of being named and skipped

  `_read` only checks that `started` is a string. `restart_seconds` then calls `moment(step["at"])` and `moment(r["started"])` outside the try in `report.build`. A record with a non-ISO `started`, a date-only `started` (a naive datetime compared with an aware one raises TypeError), a `steps` entry that isn't a dict, or a non-numeric `attempts` or `judgement.minutes` value (`int(...)` at measures.py:99 and report.py:188) now aborts `ariane report` with a traceback. The documented contract is still that a file with a field of the wrong type is named and skipped with exit 1. Ariane writes these files itself, so this is unlikely in practice, but it is a robustness regression.

- **minor** (`docs/adr/0038-report-human-time-gates-and-shadow.md:16`) Restart time ignores `ariane start`, although the decided spec says 'next start or verify'

  The issue's decided spec counts each stop up to 'the next `start` or `verify` of the same ticket'. The ADR narrows this to `verify` only, because a fresh `start` rewrites the metrics. The reasoning holds and is recorded, but it drops human time the spec asked for: a stop followed by a re-`start` counts 0. This narrows a decided behaviour rather than settling an open choice, so the owner should confirm it. Keeping the earlier stop step when metrics are rewritten would be another way to do it.

- **minor** (`src/ariane/measures.py:84`) 'Merged while no-go' does not check that the verify ran before the merge

  The last `verify` record of the branch cancels the no-go even when its `started` is after the pull request's merge time. A verify run after the merge should not clear a merge made while the review was no-go. The ADR records that the head is not compared, but not that ordering against the merge time is also skipped. The merge time is already available from `PullRequestState.ended`.

- **minor** (`src/ariane/measures.py:72`) Takeover matching differs between restarts and gates bypassed

  `human` matches verify records by ticket number or branch, while `bypassed` matches by branch only. A `verify --issue N` on a branch other than `ariane/N` adds restart time but is not counted as a hand takeover. This is not a bug against the issue, but it is an undocumented asymmetry.

- **minor** (`src/ariane/cli.py:166`) `_report_tracker` has no test

  No test covers the wiring from configuration and token variable to the `GitHubTracker` (missing config, empty token, `logs.add_secrets`). The measures are tested through `report.build` with an in-memory tracker only.

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

  tests/test_c19_report_measures.py has 12 tests named test_c19_report_human_*, test_c19_report_gates_* and test_c19_report_shadow_*. They cover waiting time from the in-memory tracker, offline 'not available', stop-to-restart time, a hand takeover, red-at-delivery, a merged no-go counted then cleared by a later verify go, an unmerged no-go not counted, and passing, failing, attempt and too-few shadow sets. They depend on `measures`, `PullRequestState` and the new report lines, so they fail without the change. tests/test_github.py covers `pull_request_state`, and tests/test_c19_metrics.py covers `blocking_red_at_delivery`.

- met: The documentation the change affects is updated (C25).

  Updated: docs/architecture/modules/report.md, the regenerated docs/reference/cli.md, and README.md (the report's numbers). Also updated or added: measures.md (new module), tracker.md, github.md, metrics.md, flow.md, cli.md and the 3-components.md graph. The 'docs: references' check is green.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0038-report-human-time-gates-and-shadow.md records: the tracker call and branch naming, waiting for an open or absent pull request, what counts as a stop and a restart, the `blocking_red_at_delivery` field, the merged-no-go rule without a head comparison, the shadow window not filtered by --since and needing ten tickets, reading only a shadow clone's own metrics, and no more tracker calls after the first failure. The 'start' narrowing deserves owner confirmation (minor finding).

## Proposed learnings (not decided)

- When a report command adds new parsing of record fields (timestamps, nested objects), extend its validation step too, so that the 'named and skipped' contract for malformed files still holds.
- Time-ordered rules ('later verify go cancels a merged no-go') should compare against the event they cancel (the merge time), not only against other records.
- An ADR that narrows a behaviour the issue already decided (rather than an open choice) should be flagged as a question to the owner, not only recorded.
