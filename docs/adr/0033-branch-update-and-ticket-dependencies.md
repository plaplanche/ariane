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
