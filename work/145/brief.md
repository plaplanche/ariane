# Product brief: Add `ariane update <n>`: merge the base branch into a delivered ticket's branch, replay, review, push (C11, C23)

- Source: issue #145 (https://github.com/plaplanche/ariane/issues/145)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

ADR 0033 decided `ariane update <n>` for slice 5: when the base branch has moved, merge it into `ariane/<n>` (never a rebase or a force-push), replay the checks, review, and push only on go. It has not been built. It is also the only way to push a second time to a delivered ticket's pull request, which the benchmark showed is needed: when a delivered pull request went red, the only way out was to close it, file a new issue and run the ticket again from scratch, because the remote branch `ariane/<n>` cannot be reused by `ariane start` (and could not even be deleted from the benchmark's environment). This first ticket builds the command with the clean-merge path; a conflict or a red check goes to an implementer in the next ticket (#146), and a red CI on the pull request in the one after (#147). Spec: C11, C23, C9, C10; ADR 0033.

## Current state

- `src/ariane/cli.py:56-118`: commands `start`, `status`, `report`, `verify`, `judge`; no `update`.
- `src/ariane/flow.py:87-98`: `ariane start` refuses a ticket whose branch exists locally or on the remote.
- `src/ariane/tracker.py:61-63` and `src/ariane/github.py:169-187`: `pull_request_state(branch)` gives the latest pull request of a branch, with `ended` and `merged`.
- `src/ariane/replay.py`, `src/ariane/review_session.py`, `src/ariane/delivery.py`: the replay, the review and the push used by `start`; `git.push` pushes an exact commit to the branch (`src/ariane/git.py:370-402`).
- `src/ariane/metrics.py:149-164`: `Metrics` starts empty for each run; nothing reads an existing `metrics.json` back.

## Decided spec

- **Command.** `ariane update <n>` (CLI, `docs/reference/cli.md`). It reads the issue through the issue gate like `start` (so the label must be added again after the pull request referenced the issue, as the README already says for `verify --issue`).
- **Refusals**, each before any change, with one line and a next action: no pull request from `ariane/<n>`, or it is merged or closed; the ticket's working tree (`flow.worktree_path`) missing; that tree not clean; its branch not `ariane/<n>`; the local branch not the remote branch's head or a descendant of it whose extra commits touch only `work/<n>/` (the records commit left after delivery); the ticket lock held, when the lock exists (#140).
- **Nothing to do.** When the remote base branch is already an ancestor of the head: "Ticket #<n> is up to date with <base>. Next: nothing." (exit 0), nothing written.
- **Merge.** `git merge --no-ff --no-edit <remote>/<base>` in the ticket's working tree, with the untrusted environment (commit hooks may run). A conflict: `git merge --abort`, then stop with status `needs a human`, listing the conflicting paths (#146 replaces this stop by an implementer session).
- **Replay and review.** On the merge commit: the replay of `start` (setup and checks in clean trees), then one review on a separate tree, as in `start`, with the issue and the diff from the merge base of the base branch. The review file continues the ticket's numbering (`review-<k>.md`, `k` one more than the highest present).
- **Push.** On go and green blocking checks: records committed under `work/<n>/` (journal, `checks.md`, the review, `status.md`, `metrics.json`), then the head pushed to `ariane/<n>` as a fast-forward with `git.push`, after checking the remote branch has not moved since the update began; then one commit status per check on the new head. The pull request updates by itself; no new one is opened. No-go or red: stop with status `needs a human`, nothing pushed, the merge kept on the local branch and recorded.
- **Records and metrics.** Journal entries `ticket.update.started`, `ticket.update.merged`, `ticket.update.pushed`, `ticket.update.up_to_date`. `metrics.json` is read back and extended (sessions, steps), with a new count `updates`; the outcome becomes the update's.
- ADR 0033 gets an amendment: where the review file numbering continues, the refusals, and that the update's push is the documented second push of a ticket (C11).

## Release note

Added: `ariane update <n>` merges the base branch into a delivered ticket's branch, replays the checks, reviews, and pushes on go.

## Acceptance criteria

- Tests named `test_c11_update_*` with the in-memory tracker and the fake runtime show:
  - a base branch that moved without conflict: a merge commit (two parents) on `ariane/<n>`, checks replayed, one review, the remote branch fast-forwarded to it, statuses on it, no new pull request, exit 0;
  - an up-to-date branch: exit 0, nothing written or pushed;
  - a merged or closed pull request, a missing or dirty working tree, and a local branch that diverged from the remote are each refused before any merge;
  - a conflict: the merge aborted, status `needs a human`, the conflicting paths named, nothing pushed;
  - a no-go review or a red blocking check after the merge: nothing pushed, the stop recorded;
  - a remote branch that moved during the update: nothing pushed;
  - `metrics.json` after an update holds the delivery's sessions and the update's, and `updates` 1.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c11_update` runs at least 7 tests and they pass.
- [ ] ADR 0033 has the amendment.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): a module file under `docs/architecture/modules/` for each new module, and `cli.md`, `flow.md`, `delivery.md`, `metrics.md`, `git.md` for those touched; `docs/architecture/1-context.md`, `2-containers.md` if they list commands, and a `update` sequence in `3-components.md`; `docs/reference/cli.md` and `docs/logs.md` regenerated; README: how to update a delivered ticket, in PowerShell and bash.

## Out of scope

- A conflict or a red check after the merge going to an implementer (#146).
- A red CI on the pull request (#147).
- Running dependent tickets in order (C12, frozen); the "Depends on" refusal of ADR 0033 §2.

## Related

ADR 0033 §1, spec C9, C10, C11, C23. Depends on #144 (clean working tree after delivery). Followed by #146 and #147. Benchmark findings in `docs/benchmark.md` (#130).


---
_Generated by [Claude Code](https://claude.ai/code)_
