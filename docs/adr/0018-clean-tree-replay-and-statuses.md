# 0018. Checks replayed in a clean working tree; statuses come from a replay

- Status: accepted
- Date: 2026-10-08
- Capabilities: C9, C8, C11

## Context
Ariane replays the checks in the working tree the implementer just used, ignored files
included: the virtual environment created by the setup command, caches, anything the agent
left ignored by git. An agent can change an ignored dependency so that the checks pass without
the pull request showing it. Separately, `.github/workflows/check-statuses.yml` (ADR 0005)
publishes the `ariane/*` statuses from the committed `work/<n>/checks.md`: whoever writes that
file on an `ariane/*` branch sets the statuses, and branch protection may require them (C9).

## Decision
- **Clean replay.** After the implementer's work is committed, Ariane creates a second, fresh
  working tree at that commit (beside the ticket's, removed afterwards), runs the setup command
  there, then the checks. Only that replay counts; its report is the one recorded and
  published. The reviewer reads that tree too (ADR 0016).
- **Statuses from a replay.** `check-statuses.yml` no longer reads `work/<n>/checks.md`. It
  checks out the pull request's head commit, runs the setup and every check declared in
  `ariane.toml` itself, and publishes one `ariane/<check>` status per check from those results.
  A report file in the branch never sets a status. When Ariane can publish statuses itself
  (outside the cloud proxy), it publishes those of its own clean replay.

This decision amends ADR 0005 (the `check-statuses.yml` paragraph) and ADR 0006 (where the
checks run).

## Consequences
The setup runs twice per ticket (once for the implementer, once for the replay); with a warm
package cache it is short. The status workflow costs one more CI job per pull request. Changing
the workflow file has to be pushed from the owner's machine (no `workflow` scope in the cloud).

## Alternatives considered
- Delete the statuses and rely on CI's own checks: simpler, but C9 asks for one status per
  declared check.
- Replay in the implementer's tree after `git clean -fdx`: removes the environment the
  implementer may still need for fix rounds, and still runs in a tree the agent controlled.
