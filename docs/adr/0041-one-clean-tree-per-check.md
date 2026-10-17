# 0041. One clean working tree per check

- Status: accepted
- Date: 2026-10-17
- Capabilities: C9, C8, C10, C23

## Context
ADR 0018 replays the setup and every check in one clean tree. A check can then pass thanks to
what an earlier check left there (installed dependencies, build output, ignored caches), while
CI runs each check as its own job in a fresh checkout. A pull request replayed green went red in
CI for that reason.

## Decision
- **One tree per check.** For each check, in the declared order (the project's checks, then the
  generated documentation checks), Ariane creates a fresh detached tree at the commit to deliver,
  runs the setup there, runs that check only, verifies the tree's head and the guard, then removes
  the tree, also on a stop or Ctrl-C. Trees are named `<n>-replay-<k>` (`verify-<slug>-<k>` for
  `ariane verify`), `k` from 1. A leftover tree of that name is refused ("remove it, then retry").
- **Setup failures** stop the ticket as before and name the check whose tree it was.
- **Per-check setup.** The optional key `checks[].setup` (argument list, same rules and timeout as
  `project.setup`) replaces `project.setup` in that check's tree, so a check can run with only
  what its CI job installs.
- **One function.** `replay.replay_each` runs this loop for `start` and `verify`.
- **Records.** `checks.md` says each check was replayed in its own clean tree after the setup;
  `ticket.checks.worktree` lists one line per check with its setup duration; a check's duration in
  the table excludes its setup.
- The reviewer's tree is unchanged; the checks no longer leave a replay tree for it.

## Consequences
The setup runs once per check, so wall-clock time grows; running the checks in parallel is a
later ticket. The clean-tree part of ADR 0018 is superseded; its statuses part stands.

## Alternatives considered
- Keep one tree and `git clean -fdx` between checks: it also removes what the setup installed,
  and does not give a check its own setup.
