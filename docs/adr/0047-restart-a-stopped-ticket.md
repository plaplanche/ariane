# 0047. Restart a stopped ticket

- Status: accepted
- Date: 2026-10-18
- Capabilities: C5, C11, C19, C23

## Context
A ticket that stopped, or whose process died, left its working trees `<n>`, `<n>-review` and
`<n>-replay-<k>` and its local branch `ariane/<n>`; `ariane start <n>` then refused it, and the
person removed them by hand after every stopped ticket of the benchmark, although the stop line
said "start the ticket again". The spec asks that an interruption never loses work, that every
command names the next possible action (C23), that the human's restart time is measured (C19) and
that two runs never share a working tree (C11). Resuming a stopped session (C5, slice 8) is not
this decision. Nothing told a live `ariane start <n>` from a dead one: the run registry
(ADR 0017) says which runs exist, but a restart has to be sure no process uses the trees it
removes.

## Decision
- **Ticket lock.** `ariane start <n>` holds an operating-system lock on
  `<repo>.ariane/locks/<n>.lock` from before the preparation to its exit: `fcntl.flock`
  (exclusive, non-blocking) on POSIX, `msvcrt.locking` (`LK_NBLCK`, one byte) on Windows. The
  system releases it when the process dies, so a killed run never leaves it held and no stale lock
  has to be cleaned. A second `ariane start <n>` (with `--restart` or not) refuses at once: "ticket
  #<n> is running in another Ariane process", and removes nothing. The lock file stays; it holds
  nothing.
- **`--restart`.** With the lock held and no `ariane/<n>` on the remote (a pushed ticket is never
  restarted), Ariane removes the ticket's trees that exist (`git worktree remove --force` each,
  then `git worktree prune`; a folder at a tree path that git does not know, left by a run killed
  before it registered it, is Ariane's own and removed as a folder, a link unlinked), keeps the local branch as
  `ariane-restarted/<n>-<UTC time as YYYYMMDDTHHMMSSZ>`, and starts the ticket as a new run.
  Nothing to remove: a plain start. `--restart --shadow` is refused before the configuration is
  read; a shadow ticket starts over by removing its clone.
- **Nothing is deleted.** The previous branch is kept, never deleted: what the previous run
  committed (its records, the agent's work) stays reachable under a name that sorts by time and
  cannot collide with a ticket branch `ariane/<m>`. Before any tree is removed, the files left
  uncommitted in the ticket's tree `<n>` (modified or untracked, not ignored: a run killed during
  its implementer session has its work only there) are saved: `git add --all` into a temporary
  index, `write-tree`, then `commit-tree` on top of the branch's head (and of the tree's own HEAD
  when it is not on the branch, so both stay reachable); the kept branch points at that commit.
  Content staged in the tree's index that differs from both its HEAD and its files (a copy of the
  index, `write-tree`) is a commit of its own just below, so neither version is lost. The tree,
  its index and its refs are not touched, so if saving fails the restart stops with everything in
  place. The kept name is then created as a new ref (never overwritten: an existing name stops
  the restart) at the saved commit or the branch's head, **before** any tree is removed, and the
  old name `ariane/<n>` is deleted last: a restart that dies midway leaves the work reachable. The `<n>-review` and `<n>-replay*` trees are Ariane's checkouts of
  committed work and are removed as they are. Ignored files (build output, environments) are not
  saved.
- **Records.** The new run's journal opens with `ticket.restarted`: the trees removed, the kept
  branch and its head, and the previous run's last action read from `work/<n>/status.md` on the
  kept branch. `metrics.json` gets `restarted_from: {"branch", "stopped_at"}`, `stopped_at` being
  the last step of the kept branch's `work/<n>/metrics.json` (absent when unreadable). Both are
  read from the branch, not from the removed trees: the branch holds what Ariane committed after
  restoring its records, the trees what an agent may have rewritten. `measures.restart_seconds`
  adds `started - stopped_at` (never negative).
- **Next actions.** The refusals of a leftover tree or local branch, in the preparation and in the
  replay and review round, say "run `ariane start <n> --restart`"; every stop of a ticket that
  was not pushed ends with "to start over, run `ariane start <n> --restart`". A stop after the
  push (the delivery calls `on_pushed`) and a shadow run's stops do not name it.
- **Concurrent tickets.** The kept name is chosen before the run registers and stored in its
  registry entry (`runs.Run.kept`); another ticket's push guard tolerates exactly that branch for
  a run it can vouch for. The entry is a file an agent can write, so the name is checked
  (`restart.is_kept_name`): it must be `ariane-restarted/<m>-<stamp>` for that run's own ticket
  `m`, the stamp at most a minute before, and never after, the run's start; and a run's entry
  counts as first witnessed, a later rewrite with the same process ignored. A forged `kept`
  (`main`, another ticket's or an older kept branch) exempts nothing, as it tolerates `ariane/<m>` (ADR 0017). Any other branch is still a
  change that stops it.
- The lock and the preparation live in a new module, `restart`, so that ticket #142 can reuse the lock
  helper and `flow` stays within the file length limit.

## Consequences
- After any stop or crash the person runs one command; the stopped attempt is kept for reading or
  for a hand takeover (`ariane verify ariane-restarted/<n>-...`).
- Kept branches accumulate locally; deleting them is the person's choice.
- For a killed run, `stopped_at` is the last step committed on its branch, which can be earlier
  than the moment it died: the restart time is then overestimated, never lost.
- The preparation now reads the remote before it looks for leftovers, so a ticket both pushed and
  left over is refused for the remote first.

## Alternatives considered
- **Delete the branch.** Loses the previous run's commits; refused by the requirement that an
  interruption never loses work.
- **A PID file.** Needs stale detection (a reused PID, a machine restart) and cleaning; the
  operating-system lock is released by the system and cannot go stale.
- **Use the run registry as the lock.** Its entries outlive a crash until reclaimed and are read
  under a shared lock for the guard; a per-ticket lock held for the whole run is simpler to reason
  about; the registry only carries the kept name for the guard.
- **Read the records from the removed trees.** More recent for a killed run, but those files may
  be an agent's; the branch's are Ariane's.
