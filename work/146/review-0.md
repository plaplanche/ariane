# Review 0

- Reviewed commit: `3d7df0e08c0f38b22fde59108343ccf1edfb78e0`
- Reviewer model: gpt-6-astra
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/resolve.py:101`) Validate conflict markers in the staged content before committing

  The marker check reads working-tree files, but the subsequent commit consumes the index. A session can stage app.txt containing conflict markers, set `git update-index --skip-worktree app.txt`, then replace its working copy with marker-free text. `unmerged()` is empty, `with_markers()` passes, and the guard does not inspect index flags. The subsequent `git add --all` skips this entry, so `git commit --no-edit` commits the staged markers. The breaking order is working-copy validation, staging that preserves a different blob, then committing that unchecked blob; no concurrent process is needed. This makes the required resolution check pass wrongly. Validate the staged blobs after staging and before committing, and add a regression test covering this index/working-copy mismatch.

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

  The new test module contains nine parametrized cases covering resolution, two-parent merges, unresolved paths, markers, failing-check prompts, exhausted rounds and an aborted merge. The successful resolution and repair cases fail against the previous stop-only behavior. Ariane reports all checks green; I did not rerun filesystem-writing tests under the read-only restriction. The staged-content bypass is not covered. Write-order audit: preparation acquires locks/slots, fetches when necessary and registers the run. Conflict handling writes merge state, journals the update and guard, writes task/status/context, runs the implementer, records session metrics and output, guards it, validates resolution, stages and commits, then records merge metrics/journal. Clean-merge repair first commits the merge, records it, replays checks and writes their reports, then journals/runs/guards the implementer and commits its work. Subsequent fix rounds write status/journal, run and record the session, guard and commit, then replay/review again.

- met: The documentation the change affects is updated (C25).

  README, ADR 0033, the component sequence, affected module documents, the new resolve module document and the log catalogue are updated. Ariane reports the references check passed. The remaining delivery sequence preserves the existing ordering: replay worktrees/setup/cache and check records; reviewer worktree and review records; delivery metrics/status and record commit; replay-equivalence check and final guard; remotely leased fast-forward push; push journal and external commit statuses; local delivered-status record commit. Unresolved conflicts write stop journal/metrics/status without committing; exhausted rounds record the stop locally without pushing.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0033's amendment records explicit staging instructions, marker syntax, merge-state checks, staged-record protection, unresolved-stop recording, unchanged-session behavior, round accounting, update context and module placement. No additional undocumented behavioral choice was identified.

## Proposed learnings (not decided)

- Proposed: validate the exact staged content consumed by a commit; working-tree validation alone is insufficient when an agent controls the index.
