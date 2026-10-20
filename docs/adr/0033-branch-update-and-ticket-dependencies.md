# 0033. Branch update by merge and ticket dependencies

- Status: accepted
- Date: 2026-10-13
- Capabilities: C1, C11, C23

## Context
Keeping delivered branches current and running dependent tickets in order is done by hand. On
2026-10-11 and 12, pull requests #106 and #107 went into conflict with `main` after other merges:
`main` was merged into each branch by hand, conflicts were resolved (including a behaviour
conflict between #103 and #104 that only tests showed), checks were replayed, `ariane verify` was
run and the branch pushed; CI on Windows then went red on #107 and was fixed the same way. Slice
4's tickets #95 to #100 also depend on each other, and only the session that runs them knows the
order. C11 said that Ariane rebases the ticket branch, which is not what the owner decided.

## Decision
1. **Branch update.** `ariane update <n>` merges the remote base branch into `ariane/<n>` with a
   merge commit, in the ticket's working tree. It never rebases and never force-pushes.
   - Clean merge: the checks are replayed in a clean tree and one review runs, as in
     `ariane verify`. On go and green checks, Ariane pushes the branch.
   - Conflict or red check after the merge: one implementer session resolves it (the conflict or
     the failure is its task, like a fix round), then the replay and the review run as above,
     within the fix-round limit of C10. Still no-go or red: the ticket stops as "needs a human"
     and nothing is pushed.
   - Records go to `work/<n>/` like any round.
   - A branch whose pull request is merged or closed is refused.
2. **Dependencies.** The issue body may hold an optional section "Depends on", listing issue
   numbers (`#95, #97`). `ariane start` refuses a ticket while one of them is not closed by a
   merged pull request, naming it, before any branch or agent. Running dependent tickets
   automatically in order waits for C12.
3. **Placement.** These are the first tickets of slice 5, before C2.

## Consequences
A pushed branch is never rewritten, so a person who checked it out keeps a valid history. The most
frequent case, a conflict with the base branch, is handled by an implementer instead of by hand.
The owner still decides on every stop. Ordering is enforced by refusal, not by a scheduler.

## Alternatives considered
- Rebase then replay (the former text of C11): rewrites a pushed branch, and a person may have
  checked it out.
- Clean merges only, conflicts to the human: leaves the most frequent case manual.
- A queue command running tickets in order: already a form of C12, which is frozen.

## Amendment (2026-10-20): `ariane update <n>`, first ticket (#145)
The clean-merge path is built; a conflict or a red check after the merge stops as "needs a human"
until an implementer session takes them (#146).
- **Second push.** The update's push is the documented second push of a ticket (C11): the head is
  pushed to `ariane/<n>` as a fast-forward with `git.push`, only on `go` with green blocking checks,
  and only if `ariane/<n>` on the remote is still where it was when the update began. That
  condition is enforced by the remote itself, atomically with the push: the push carries a lease
  (`--force-with-lease=refs/heads/ariane/<n>:<head read at the start>`), so a branch moved or
  deleted after Ariane's last read is refused, and `git.push` first checks that the pushed head
  descends from that head, so the lease never allows anything but a fast-forward. The pull
  request updates by itself; none is opened. One commit status per check goes on the new head.
- **Refusals**, each before any change, with one line and a next action: no pull request from
  `ariane/<n>`, or a merged or closed one; the ticket's working tree missing, dirty, or not on
  `ariane/<n>`; the local branch neither the remote branch's head nor a descendant of it whose
  extra commits each change only `work/<n>/` (the records committed after a push, ADR 0027;
  every extra commit's own paths are read, a merge's against each parent, so a change and its
  revert are refused although the two heads differ only there); the ticket
  lock held. The issue is read through the issue gate (ADR 0032), as for `ariane start`.
- **Up to date.** When the remote base branch is an ancestor of the head, the command says so and
  exits 0. It decides this from the base `ls-remote` lists, when the repository has that commit,
  before any fetch: nothing is written in the repository (no `FETCH_HEAD`, tracking ref or reflog), so `ticket.update.up_to_date` is a technical
  record (the log file `update-<n>.log`) rather than a journal entry; `ticket.update.started`,
  `ticket.update.merged` and `ticket.update.pushed` are journal entries.
- **Review numbering.** The update's review continues the ticket's numbering: `review-<k>.md`, `k`
  one more than the highest present in `work/<n>/` (the ticket's records are read back from its
  clean working tree). Its diff is the merge commit's from the fetched base, without `work/`.
- **Checks selected.** With selective checks (ADR 0056), the checks an update replays are chosen
  from the ticket's diff from the base and from what the merge brings from the base (the ticket's
  head before the merge to the merge commit): a check scoped to files only the base changed still
  runs, so a combination the base breaks is not pushed with a skipped check reported green.
- **Metrics.** `metrics.json` is read back and extended (steps, sessions), with a count `updates`,
  written for every ticket (0 when never updated); its outcome becomes the update's.
- **A merge left half done.** Ctrl-C or an error once the merge began, while the tree holds a
  `MERGE_HEAD` or unmerged paths (or git cannot tell), writes and commits nothing, as an abort that
  did not restore the tree: a record commit's `git reset` would drop the merge state a human needs
  to finish or abort it.
- **Stops.** A stop after the merge keeps the merge commit on the local branch, records the stop
  in `work/<n>/` and pushes nothing; a later `ariane update` then refuses the diverged branch until
  it is pushed by hand after `ariane verify` (or #146 takes it).
