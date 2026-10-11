# Product brief: Record slice 4's decisions: ADR 0030, measurement, shadow mode and the report (C19, C23)

- Source: issue #94 (https://github.com/plaplanche/ariane/issues/94)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Slice 4 (measurement and shadow) starts with its decisions. The owner answered the open choices on 2026-10-11 and an engineering review of the plan raised three blocking findings, settled by the owner (separate clone for shadow tickets, human minutes declared in `ariane judge`, agent push and pull-request attempts counted). This ticket records them before any code. Spec: C19, C23, roadmap slice 4, "Measuring Ariane", "Adopting Ariane on an existing project" step 2.

## Current state

- `docs/adr/` ends at `0029-opencode-reviewer.md`.
- `docs/adr/0012-measurements.md` fixes `work/<n>/metrics.json` and `ariane report [--since]`; no code implements it yet (`src/ariane/` has no `metrics` or `report`).

## Decided spec

- Add `docs/adr/0030-slice-4-measurement-and-shadow.md` with exactly the text between the two lines `--- ADR 0030 ---` below (only the fence lines removed).
- `docs/adr/0012-measurements.md`: its status becomes `accepted; format amended by 0030`.
- No code change.

--- ADR 0030 ---
# 0030. Slice 4: measurement, shadow mode and the report

- Status: accepted
- Date: 2026-10-11
- Capabilities: C19, C23, C1
- Amends: 0012

## Context
Slice 4's gate: a second user installs Ariane on macOS, and their first tickets are measured in
shadow mode. ADR 0012 already fixes `work/<n>/metrics.json` and `ariane report [--since]` for
cost, tokens, rounds and first-pass verdict. ADR 0020's success measure needs two more numbers
per ticket: human time per merged pull request, and steps skipped or gates bypassed. The spec's
shadow step: Ariane processes real tickets without pushing, with its own state, no pull-request
attempt, no write to real data; the human judges Ariane's diff acceptable or not; cost and
duration are recorded.

## Decision
1. **Metrics** as ADR 0012, written at each step; `duration_s` per session, `cache_read_tokens`
   and `cache_write_tokens` added (C5 counts them), timestamps of each step.
2. **Human time** = waiting time measured from timestamps Ariane already has or can read:
   pull request opened → merged or closed (read from the tracker by `ariane report`), stop →
   next `ariane start`/`verify` on the same ticket. Active human minutes are not guessed.
3. **Shadow mode** = `ariane start --shadow <issue>`: the whole flow (implementer, replay,
   review, fix rounds) runs, then Ariane stops before push, pull request and commit statuses.
   It never contacts the tracker except to read the issue.
4. **Shadow state** lives outside the user's repository: each shadow ticket gets a separate
   local clone in `<repo>.ariane/shadow/<n>/` (origin removed), so nothing is written to the
   user's `.git` and the user's own git commands, which go on during a shadow ticket, cannot
   race with Ariane's. Its records stay in that clone.
5. **The human's verdict** on a shadow diff: `ariane judge <n> accept|reject --minutes N
   [--note TEXT]` writes the verdict and the minutes the human spent on that diff into the
   shadow ticket's metrics; these minutes are Ariane's human time for a shadow ticket.
6. **Gates bypassed and attempts**: Ariane counts, per ticket, the `git push` and
   `gh pr create` commands an agent attempted (read from the session's event stream), the guard
   violations it detected, hand takeovers (`verify` runs), blocking checks red at delivery, and
   a pull request merged while the last review on its head is no-go.
7. **`ariane report`** reads `work/*/metrics.json` of the checkout and
   `<repo>.ariane/shadow/<n>/work/<n>/metrics.json`, one line per ticket (mode shadow or delivered), and
   totals: cost, agent time, human waiting time, rounds, first-pass go rate, shadow accept
   rate, gates bypassed, agent push or pull-request attempts. Without a token or network,
   the tracker-based waiting time reads "not available".

## Consequences
Shadow mode leaves no trace in the user's repository; its numbers are lost if the
`.ariane` folder is deleted. For delivered tickets human time is a waiting time, an upper
bound on active time; for shadow tickets it is the minutes the human declares in `ariane judge`.
The user's own log stays the reference for the comparison (ADR 0020). `ariane report` needs the
tracker for waiting times and says so when it cannot reach it.

## Alternatives considered
- Asking the human to declare minutes per ticket: closer to active time, but one more chore.
- Shadow as a config key: easier to forget it is on; a flag is explicit per run.
- A worktree or shadow branches in the user's repository: simpler code, but writes to the
  user's `.git` and races with the user's own git commands during a shadow ticket.
- Waiting time between the end of a shadow ticket and `ariane judge`: measures when the human
  looks, not how long.
--- ADR 0030 ---

## Release note

Docs: slice 4's decisions are recorded (ADR 0030).

## Acceptance criteria

- `docs/adr/0030-slice-4-measurement-and-shadow.md` holds the text above; ADR 0012's status line names 0030.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] ADR 0030 added, ADR 0012 status amended.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): only the two ADR files change.

## Out of scope

Any implementation of ADR 0030 (later tickets of slice 4).

## Related

ADR 0012, ADR 0020, ADR 0021, spec C19, C23.
