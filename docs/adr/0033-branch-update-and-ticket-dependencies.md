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
  `ariane/<n>`; a `work/<n>/` holding anything but plain files (a folder or a link, committed
  or ignored: the update keeps only plain files as records and rewrites the folder from them, so
  it would remove the rest); a base that changed `work/<n>/` since it forked from the ticket
  (the merge would bring records the rewrite removes); the local branch neither the remote branch's head nor a descendant of it whose
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
  clean working tree, all of them before anything is written: a failed or interrupted read
  stops the update with nothing written or removed). Its diff is the merge commit's from the fetched base, without `work/`.
- **Checks selected.** With selective checks (ADR 0056), the checks an update replays are chosen
  from the ticket's diff from the base and from what the merge brings from the base (the ticket's
  head before the merge to the merge commit, both sides of a rename): a check scoped to files only
  the base changed, or moved out of, still runs, so a combination the base breaks is not pushed with a skipped check reported green. The round's risk tier (ADR 0056) reads the same paths, and its changed lines are the ticket's plus those the merge brings: a small ticket merging a large base change is `high`, so a check whose full suite runs only when `high` runs whole on the combination.
- **Accepted residuals.** The update's review gets the accepted residuals of the base commit
  (ADR 0057), read at the fetched base: the ticket's working tree holds the delivered change, so a
  marker the ticket added never exempts it.
- **Metrics.** `metrics.json` is read back and extended (steps, sessions), with a count `updates`,
  written for every ticket (0 when never updated); its outcome becomes the update's. A
  `metrics.json` that cannot be read back (not JSON, a field missing or of the wrong type) is left
  out whole, never half taken: the update's measurements start empty and replace it, and the
  earlier ones stay in the branch's history. Refusing the update for it would block a ticket on a
  measurement, which never decides a delivery (C19).
- **A merge left half done.** Ctrl-C or an error once the merge began, while the tree holds a
  `MERGE_HEAD` or unmerged paths (or git cannot tell), writes and commits nothing, as an abort that
  did not restore the tree: a record commit's `git reset` would drop the merge state a human needs
  to finish or abort it.
- **Stops.** A stop after the merge keeps the merge commit on the local branch, records the stop
  in `work/<n>/` and pushes nothing; a later `ariane update` then refuses the diverged branch until
  it is pushed by hand after `ariane verify` (or #146 takes it).

## Amendment (2026-10-21): the update's implementer session (#146)
A conflict, or blocking checks red after a clean merge, now go to one implementer session instead
of stopping, as §1 decided.
- **Conflict.** The merge is left in progress (no abort). The session's task, in an untrusted block
  `kind="update"`: "Merge `<remote>/<base>` into this branch: resolve the conflicts below, keeping
  both sides' intent; mark each path resolved with `git add`; do not commit", then the conflicting
  paths. The `git add` clause is added to the decided text so that the check below has a meaning:
  a path not marked resolved is still unmerged. The guard expects the head where the update
  started (the session must not commit). Then Ariane refuses to continue when `git ls-files -u`
  lists a path, or a conflicting path's file or staged blob holds a line starting with
  `<<<<<<< ` or `>>>>>>> ` (the conflict-marker check; `=======` alone is too common in text to
  count; the staged blob is what the commit takes, so a working copy hidden from `git add`, such
  as one marked `--skip-worktree`, cannot pass it), or the session
  staged entries under `work/`; and stops as a guard violation when the merge is no longer in
  progress at the fetched base. Otherwise it stages everything outside `work/`, runs the
  unmerged and marker checks again on the index, and runs `git commit --no-edit`: the merge commit keeps both parents, which are checked as for a clean
  merge.
- **A conflict left unresolved** stops `needs a human` with the merge state kept and nothing
  committed or pushed, as an abort that did not restore the tree: a record commit's `git reset`
  would drop it. Since the session already journaled in the working tree, the stop, the status and
  `metrics.json` (category `merge`) are written there too, uncommitted; before any session, a merge
  left half done still writes nothing.
- **Red check after a clean merge.** The session's task is "These checks fail after merging
  `<remote>/<base>`: fix them", then each failing blocking check's name, result and output as
  `checks.md` shows it (a failing check's output whole). Ariane commits its work as
  `#<n>: fix after merging <base>`; a session that leaves the head where it was stops
  `needs a human`.
- **Rounds.** The update session counts as the first of C10's two fix rounds: after it, red
  blocking checks or a `no-go` go to one fix round exactly as in `start` (fix round 2, findings and
  failing checks as data), then the replay and the review once more. An update therefore runs at
  most two implementer sessions. Go and green: pushed as in #145. Otherwise `needs a human`,
  nothing pushed, the merge kept on the local branch. A clean merge with green checks still gets
  one review and no fix round: a `no-go` there stops, as #145 built it.
- **Context.** Every implementer prompt of an update says it is an update of a delivered ticket
  merging `<remote>/<base>`, not a fresh ticket; the recorded context says so too and points to the
  journal entry `ticket.update.implementer`, which holds the task given.
- **Placement.** The session, the resolution checks and the merge commit are the module
  `ariane.resolve`, apart from `ariane.update`, which keeps the merge, the rounds and the push.
