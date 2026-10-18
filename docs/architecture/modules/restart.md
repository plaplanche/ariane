# Module `ariane.restart`

`ariane start <n> --restart` (C5, C23, ADR 0047): the ticket lock that tells a live `ariane start <n>` from a dead one, the preparation of a ticket's branch and working tree, and starting a stopped or interrupted ticket over while keeping its previous branch.

## Public API

| Name | Kind | What it does |
| --- | --- | --- |
| `REMOTE` | constant | The remote name, `origin`. |
| `LOCKS` | constant | `locks`, the folder of the ticket locks under `<repo>.ariane/`. |
| `KEPT_PREFIX` | constant | `ariane-restarted`, the prefix of a kept branch. |
| `kept_name(number)` | function | `ariane-restarted/<n>-<UTC time as YYYYMMDDTHHMMSSZ>`, the name a restart keeps the branch under; `flow.start` registers it with the run before `prepare` writes it. |
| `is_kept_name(name, number, started)` | function | Whether `name` is `ariane-restarted/<number>-<stamp>` with the stamp at most a minute before, and not after, `started`: the only kept name the push guard exempts (`runs.kept_branches`). |
| `lock_path(repo_root, number)` | function | `<repo>.ariane/locks/<n>.lock`. |
| `command(number)` | function | The text `` `ariane start <n> --restart` ``. |
| `with_restart(action, number)` | function | `action` followed by "; to start over, run `ariane start <n> --restart`", a trailing ", then start (the ticket) again" dropped; unchanged when it already names the command. |
| `locked(path, number)` | context manager | Holds the ticket's lock for the block, without waiting; held by another process: `Stop` "ticket #<n> is running in another Ariane process". |
| `prepare(repo_root, base_branch, branch, worktree, kept)` | function | Fetches the base branch, reads its instructions and the remote's refs, refuses a pushed branch, clears a previous run when `kept` is not empty (restarting), refuses leftovers, then creates the branch and the working tree; returns the push URL, the remote refs, the instructions and the `Restarted` record (or None). |
| `Restarted` | dataclass | What `--restart` cleared: `removed` trees, `kept_branch`, `kept_head`, `saved` (the commit of the uncommitted work, or empty), the previous run's `last_action`, `stopped_at` and `earlier_s` (the restart time that run carried, 0 when none); `journal(number)` is the `ticket.restarted` text, `metrics()` the `restarted_from` object. |
| `leftovers(worktree, number)` | function | The ticket's trees that exist: `<n>`, `<n>-review` and every `<n>-replay*`. |
| `clear(repo_root, worktree, number, branch, kept)` | function | Stops when the tree `<n>` is a folder git does not know that holds files (`_unknown_with_files`: neither saved nor removed). Saves the uncommitted work of the tree `<n>`, removes those trees (`git worktree remove --force` for a registered one, the folder otherwise, then `git worktree prune`), deletes `ariane/<n>` (`git branch -D`, its config with it); `kept` is created first, at the saved commit or the branch's head, before any removal (`git update-ref` with an empty old value: an existing `kept` stops the restart with everything in place); None when there was nothing to clear. |

## Behaviour and errors

- The lock is an operating-system lock on the whole run of `ariane start <n>`, taken by `slots.try_lock`: `fcntl.flock` (exclusive, non-blocking) on POSIX, `msvcrt.locking` (`LK_NBLCK`, one byte) on Windows. Closing the file releases it, and so does the system when the process dies, so a killed run never leaves it held. The file stays; it holds nothing.
- `prepare` checks the remote first: a branch `ariane/<n>` on `origin` refuses, with or without `--restart` ("close its pull request and delete the branch, then start again"). Then, when `restarting`, `clear`; then any leftover tree or local branch refuses with the next action "run `ariane start <n> --restart`".
- `clear` never deletes a branch: the kept branch's name has the UTC time, to the second, of the restart. The previous run's last action is read from `work/<n>/status.md` at the branch's previous head (Last action, Detail, At), and `stopped_at` is the time of the last step of `work/<n>/metrics.json` there, `earlier_s` its `restarted_from.earlier_s` plus its own `started - restarted_from.stopped_at` (`_earlier`); either is empty when unreadable. They are read from what Ariane committed, never from the saved work, which an agent may have written.
- Before removing anything, `clear` saves the files left uncommitted in the registered tree `<n>`, modified or untracked but not ignored: `git add --all` into a temporary index (`GIT_INDEX_FILE`), `write-tree`, and `commit-tree` with Ariane's identity, its parents the branch's head and, when not on the branch, the tree's own HEAD. A copy of the tree's index is written as a tree too: staged content that differs from both the HEAD and the files is a commit of its own just below the files' one. Nothing to save (the files and the index are the tree's HEAD, and that HEAD is on the branch): no commit. The tree is not touched, so a failure stops the restart with every tree in place. The journal names the saved commit, which is the kept head.
- `clear` prunes first, then removes each leftover: a working tree git has registered with `git worktree remove --force`; a folder at the ticket's tree path that git does not know (a killed run left it before registering it, or an agent created it) is in Ariane's own `<repo>.ariane/worktrees/` and is removed as a folder (read-only files made writable first, for Windows); a link in its place is unlinked, never followed.
- The kept name is registered with the run (`runs.Run.kept`) before it is written, so another ticket's push guard tolerates that one branch appearing while this run is live or witnessed (ADR 0017, ADR 0047), and only if `is_kept_name` accepts it for that run's ticket and start: the entry is agent-writable, so a forged `kept` (`main`, any other branch) is never exempt.
- A failing git command raises `git.GitError`; the flow reports it as a stop before the ticket started.

## Workflow

```mermaid
flowchart TD
  A[locked: lock free?] -- no --> X[Stop: running in another Ariane process]
  A -- yes --> B[prepare: fetch, instructions, remote refs]
  B --> C{ariane/n on origin?}
  C -- yes --> Y[Stop: already exists on origin]
  C -- no --> D{restarting?}
  D -- yes --> E[clear: prune, save uncommitted and staged work, write kept ref, remove trees or unknown folders, prune, delete old branch, read status and metrics]
  D -- no --> F{leftover tree or local branch?}
  E --> F
  F -- yes --> Z[Stop: run ariane start n --restart]
  F -- no --> G[add the branch and working tree]
```

## Code view (C4 level 4)

```mermaid
classDiagram
class Restarted {
  <<dataclass>>
  removed tuple~Path~
  kept_branch str
  kept_head str
  saved str
  last_action str
  stopped_at str
  earlier_s float
  journal(number) str
  metrics() dict
}
class restart {
  <<module>>
  lock_path(repo_root, number) Path
  locked(path, number)
  prepare(repo_root, base_branch, branch, worktree, restarting) tuple
  clear(repo_root, worktree, number, branch) Restarted
  with_restart(action, number) str
}
restart ..> Restarted
```

## Collaborations

Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only.

<!-- generated: collaborations -->
```mermaid
flowchart LR
  flow --> restart
  replay --> restart
  restart --> git
  restart --> metrics
  restart --> slots
  restart --> stop
  restart --> ticket
  runs --> restart
```
<!-- end generated -->

## Serves

C5, C11, C19, C23; ADR 0047. See [the component view](../3-components.md).
