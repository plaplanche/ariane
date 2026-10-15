# 0036. Shadow mode and agent attempts

- Status: accepted
- Date: 2026-10-15
- Capabilities: C19, C23

## Context
ADR 0030 items 3, 4 and 6: a second user measures Ariane on real tickets while their current
process does the real work, with no push, no pull request and no write to their repository, and
Ariane counts what an agent tried to push.

## Decision
- `ariane start --shadow <issue>` is `shadow.start`: the same flow in `<repo>.ariane/shadow/<n>/`,
  made with `git clone --local --no-checkout` from the user's repository, cut at the commit of the
  user's last known `origin/<base branch>`. The clone's `origin` is removed; its base commit is
  named by the ref `refs/remotes/shadow/<base>`, which is not a remote.
- No fetch: a fetch would write to the user's `.git`. The base is as fresh as the user's last
  fetch; the journal names the branch and the commit is the clone's start. A missing
  `origin/<base>` stops the run with "run `git fetch origin`".
- `ShadowRun` subclasses the ticket run: no remote check (there is no remote) and a local delivery
  that records the outcome and commits the records. A shadow ticket ends with exit 0 whether the
  review is `go` or still `no-go` (outcome `delivered` or `needs a human`); a stopped ticket is
  reported like any stop.
- The runtime adapters read the shell tool calls of the session's event stream (Claude Code
  `tool_use` blocks, opencode `tool_use` parts, each call once) and count, on
  `SessionResult.attempts`, the simple commands whose words are `git push` or `gh pr create`
  (global options skipped, `sh -c` strings followed). The command is split like a shell: a quoted
  string is one word, so `echo "git push"` and `git pushd` count nothing.
- `metrics.json` gains `attempts` (`push`, `pull_request`, `guard_violations`), for every ticket.
  A guard violation is a `Stop` raised by the post-session check (`verify`).

## Consequences
Shell parsing is a heuristic: a push built by a script the agent wrote and ran is not seen; the
post-session check and the blocked push URL stay the guards. A shadow ticket's numbers live in its
clone only.

## Alternatives considered
A worktree or branches in the user's repository: writes to the user's `.git` (ADR 0030).
A plain substring search for `git push`: counts quoted text and `git pushd`.
