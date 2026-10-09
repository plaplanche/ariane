# Product brief: Push a delivered ticket once, and redact commit messages

- Status: draft
- Approved: not yet
- Source: issue #22 (https://github.com/plaplanche/ariane/issues/22)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Each push of a ticket branch starts a full CI run (six jobs, about 4 minutes on Windows). A delivered ticket is pushed twice today: once with the checks record, once with the delivery record. The owner decided that each ticket costs one CI run: every record is committed before a single push (ADR 0009, issue 3; ADR 0011). While touching these commits: commit messages are published with the branch, so they are redacted too (gap found in the review of #19).

## Current state

- `src/ariane/delivery.py:51` commits "record the checks", `:53` pushes, opens the pull request, `:71` commits "record the delivery" and `:75` pushes again.
- `src/ariane/delivery.py:105` commits "record the refused statuses" after the pushes (it stays local).
- `src/ariane/flow.py:286` names the agent's commit `#<n>: <issue title>` and `src/ariane/flow.py:337` `_commit_record` commits the ticket folder; neither message is redacted.
- `src/ariane/redact.py` `redact(text, known)` exists (#19).

## Decided spec

- After the blocking checks pass, Ariane writes the final records before pushing: journal entry "Delivering" and status `delivered` with detail `pull request from <branch>` and next action `review and merge the pull request`. It commits them ("#<n>: record the checks and the delivery") and pushes that exact commit once.
- It then opens the pull request and publishes the statuses on that pushed commit. Nothing is committed after the push: the pull request URL, a refused status or a refused pull request are written to the journal and status in the working tree only (uncommitted), and reported in the command's output line as today.
- A refused pull request still stops the ticket with the current message ("is pushed but the pull request was refused ... open the pull request by hand"); the local status says `stopped`.
- Every commit message Ariane writes goes through `redact` with the run's known secrets.
- No other behaviour changes: same guard checks before the push, same pull request body, same outcome line.

## Release note

Changed: a delivered ticket is pushed once, so its pull request runs CI once.

## Acceptance criteria

- A test named `test_c11_one_push_*` shows that a delivered ticket updates the remote branch exactly once (for example by counting pushes to the test remote) and that the pushed head contains the `delivered` status and the checks record.
- A test named `test_c11_one_push_refused_pull_request_*` shows that when the pull request is refused, the branch was pushed once and the local status says `stopped`.
- A test named `test_c21_redact_commit_messages_*` shows that a GitHub token in the issue title does not appear in any commit message on the pushed branch.
- Existing tests that read the delivery record from the pushed branch are updated to the new single record; no other test changes meaning.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `src/ariane/delivery.py` calls `git.push` once.
- [ ] `uv run pytest -k "c11_one_push or c21_redact_commit_messages"` runs at least 3 tests and they pass.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

The reviewer and the learnings checkpoint (later issues), rebasing on a moved base branch.

## Related

ADR 0009 (issue 3 of slice 2), ADR 0011, ADR 0013, #19.
