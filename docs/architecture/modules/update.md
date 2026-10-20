# Module `ariane.update`

`ariane update <n>` (C9, C10, C11, C23; ADR 0033): when the base branch has moved, it merges the remote base branch into a delivered ticket's branch `ariane/<n>` with a merge commit, in the ticket's working tree (never a rebase or a force-push), replays the checks on the merge commit as `ariane start` does, runs one review, and on `go` with green blocking checks pushes the branch again as a fast-forward: the pull request updates by itself. It is the documented second push of a ticket (C11). The run is a `flow._TicketRun` continued (`_UpdateRun`): the ticket folder and `metrics.json` are read back, the replay, the review round, the guard and the stop are `start`'s.

## Public API

| Name | Kind | What it does |
| --- | --- | --- |
| `NEEDS_A_HUMAN` | constant | `needs a human`, the status of every stop after the merge began. |
| `Refused` | exception | The ticket cannot be updated, before any change; carries `reason` and `next_action`. |
| `Heads` | dataclass | Where the update starts: the push `url`, the remote's `refs` (read once), the `local` head, the `remote` branch's head and the remote `base`. |
| `next_review(names)` | function | The number of the next review record: one more than the highest `review-<k>.md` of `names`, else 0. |
| `update(number, ...)` | function | The entry point; returns a `flow.Outcome`. |

## Behaviour and errors

- The issue is read through the issue gate first (`Tracker.read_issue`), as for `start`: a refused issue exits with the tracker's code. The label must be added again after the pull request referenced the issue.
- Then, before any change, it holds the ticket lock (`restart.locked`: "ticket #<n> is running in another Ariane process") and a machine-wide slot (ADR 0050), and refuses, each with one line and a next action, exit 1: no pull request from `ariane/<n>` (`Tracker.pull_request_state`), or a merged or closed one; the ticket's working tree (`flow.worktree_path`) missing; that tree with uncommitted changes; its branch not `ariane/<n>`; `ariane/<n>` not on `origin`; the local branch not the remote branch's head or a descendant of it whose extra commits change only `work/<n>/` (the records committed after the delivery's push, ADR 0027): "the local branch ariane/<n> diverged from origin/ariane/<n>".
- Up to date: when the fetched `origin/<base>` is an ancestor of the head, "Ticket #<n> is up to date with <base>. Next: nothing.", exit 0; nothing is written in the repository, and the technical log has `ticket.update.up_to_date`.
- Merge: `git merge --no-ff --no-edit origin/<base>` in the ticket's working tree with the untrusted environment and Ariane's identity (commit hooks may run), then the guard of `flow` ("the merge"), the history checked from the head the update started at. The merge commit's parents must be that head and the fetched base. The journal gets `ticket.update.started` and `ticket.update.merged`; `metrics.json` its `updates` count plus one and the step `base merged`.
- Conflict: `git merge --abort`, then the stop "merging origin/<base> conflicts in <paths>", status `needs a human`, the paths in the journal; the next action merges by hand and runs `ariane verify ariane/<n>`. Nothing is pushed.
- Replay and review: the checks are replayed at the merge commit (`replay.replay`), the changed files and the reviewer's diff taken from the fetched base to the merge commit, without `work/`; then one review round `k` (`replay.review_round`), its record `review-<k>.md` with `k` from `next_review`. A red blocking check (no review then) or a `no-go` stops with status `needs a human`: nothing pushed, the merge kept on the local branch, the stop recorded and committed there.
- Push: `delivery.Delivery.push_update`: the records committed under `work/<n>/` (`#<n>: record the update`), the head checked to differ from the merge commit only there, then the last guard: `ariane/<n>` on `origin` must still be at the head read when the update began ("ariane/<n> moved on origin during the update", nothing pushed), and the guard of `flow` ("the delivery"); then `git.push` of the head (a fast-forward), `ticket.update.pushed`, one commit status per check on the pushed head, and the status `delivered` committed on the local branch only. No pull request is opened.
- Metrics: `metrics.json` is read back (`Metrics.resume`) and extended: the delivery's steps and sessions are kept, the update's added, and the outcome becomes the update's (`delivered`, or the stop's status).
- Ctrl-C or a git, tracker or file error after the refusals is a stop of `flow` (`_TicketRun._stopped`), never naming `--restart`: the branch is pushed.

## Workflow

```mermaid
flowchart TD
  A[update n] --> B[read the issue: issue gate]
  B --> C[lock, slot, pull request open, tree there, clean, on ariane/n, branch not diverged]
  C -- no --> X[Refused: one line, nothing changed]
  C -- yes --> D{origin/base ancestor of the head?}
  D -- yes --> Y[up to date: exit 0, nothing written]
  D -- no --> E[read the folder and metrics.json back, git merge --no-ff]
  E -- conflict --> F[git merge --abort: needs a human, paths named]
  E -- merged --> G[replay the checks at the merge commit]
  G -- red --> H[needs a human: merge kept, nothing pushed]
  G -- green --> I[review round k]
  I -- no-go --> H
  I -- go --> J[commit records, remote branch unmoved, push fast-forward, statuses]
```

## Code view (C4 level 4)

```mermaid
classDiagram
class Heads {
  <<dataclass>>
  url str
  refs dict
  local str
  remote str
  base str
}
class _UpdateRun {
  restartable False
  execute_update() Outcome
  verify(after, start_commit, guard, refs_before, expected_head)
}
class update {
  <<module>>
  update(number, ...) Outcome
  next_review(names) int
}
_TicketRun <|-- _UpdateRun
update ..> Heads
update ..> _UpdateRun
```

## Collaborations

Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only.

<!-- generated: collaborations -->
```mermaid
flowchart LR
  cli --> update
  update --> checks
  update --> config
  update --> context
  update --> delivery
  update --> flow
  update --> git
  update --> logs
  update --> metrics
  update --> process
  update --> replay
  update --> restart
  update --> runs
  update --> runtime
  update --> slots
  update --> stop
  update --> ticket
  update --> tracker
```
<!-- end generated -->

## Serves

C9, C10, C11, C19, C23; ADR 0033. See [the component view](../3-components.md).
