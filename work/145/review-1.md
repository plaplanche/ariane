# Review 1

- Reviewed commit: `125e86f9340c0aaa8ee675dabd8897d70e33c0fe`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/update.py:233`) Confirm the merge was aborted before writing or committing stop records

  The failure path writes journal.md before running merge --abort, ignores the abort result, then verifies only the branch/head and proceeds to _stopped, whose record commit starts with git reset --quiet. If the failed merge cleanly updated journal.md while another path conflicted, the journal write makes that merged index entry dirty and can prevent abort from restoring it. A hook can likewise leave changes that prevent abort. The subsequent reset clears the unresolved index and merge state without restoring the working files, leaving conflict markers or partially merged files behind while reporting an aborted conflict. Capture conflicting paths, abort and verify successful restoration before writing records; if abort fails, preserve the unresolved state and avoid the normal record-commit path. Add a regression covering an abort failure, beyond the existing app.txt-only conflict.

- **minor** (`src/ariane/update.py:202`) Some update failures record 'stopped' instead of the documented 'needs a human'

  execute_update delegates exceptions directly to inherited _stopped. GitError, including a lease rejection after the last guard, records status 'stopped'; inherited guard/setup Stop exceptions also default to 'stopped'. The update module documents every stop after the merge began as 'needs a human'. Normalize the applicable update failures or narrow that documentation, and assert the status in the existing lease-race tests.

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

  The new test_c11_update suite exercises merge parents, replay, review numbering, fast-forward delivery, statuses, refusals, conflicts, red checks, no-go, remote races, metrics and CLI routing. These depend on the new command. The supplied replay reports passing tests; I did not rerun tests because this review permits only reads. Abort-failure coverage is missing as described above.

- met: The documentation the change affects is updated (C25).

  README includes PowerShell and bash usage; the CLI reference, log catalogue, architecture command views, update sequence, new update module and affected module documentation are updated. One stop-status discrepancy is noted above.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0033's amendment records the leased fast-forward push, per-commit records-only refusal, review numbering, no-op logging, cumulative metrics and stopped-branch handling. Side-effect tracing found: preparation creates lock/slot state and fetches Git metadata; no-op exits without ticket records; merge writes Git state, then journal and metrics; replay creates/removes trees and writes reports; review writes session metrics and its record; delivery commits records, checks guards, performs the leased push, journals it, publishes statuses and commits local delivery records. The conflict path's unsafe ordering is the blocking finding.

## Proposed learnings (not decided)

- Treat rollback as a checked operation: confirm restoration before writing recovery records or resetting the index.
- Test failure cleanup with both conflicted files and cleanly merged files that recovery logging may modify.
