# 0062. Resume a ticket stopped by a limit or a quota

- Status: accepted
- Date: 2026-10-23
- Capabilities: C5, C10, C23

## Context
C5 says that a session stopped by budget, turns or timeout leaves its work saved on the ticket
branch and a clear status, and that the next run resumes it, with a larger budget after a budget
stop, capped by the configuration. `ariane start <n> --restart` (ADR 0047) saved that work on a
kept branch but started the new run from the base branch: an implementer stopped at its time
limit with most of the work done was redone from nothing, and only a hand-made configuration
gave it more time. The owner added (21 October 2026) that a stop on a runtime's usage quota
(ADR 0043) resumes the same way, without raising anything.

## Decision
- **`ariane start <n> --resume`**, exclusive with `--restart` and refused with `--shadow`. It is
  allowed when the previous run's last agent session stopped on `budget`, `turns` or `timeout`
  and was the implementer's (its first session or a fix session) with the run's stop category
  `budget`, or stopped on `quota` (implementer, fix or reviewer session) with the category
  `runtime`. These are read from `work/<n>/metrics.json` on the local branch `ariane/<n>`, what
  Ariane committed, before anything is cleared. Any other stop (a check failure, a review
  hand-over, a guard stop after the session, a crash whose outcome is still `running`) refuses
  and names `--restart`. An idle stop is recorded as `timeout` (ADR 0045) and resumes as one.
- **What it keeps.** The restart steps of ADR 0047 run as they are (lock, saved work, kept
  branch). The new branch `ariane/<n>` is created at the base, so that the run reads the base's
  accepted residuals (ADR 0057) and not ones an agent wrote, then moved to the kept branch's head
  with `git reset --hard` (no hook runs) before the guard's first snapshot. `work/` is brought
  back to the merge base's, in a commit of its own: the previous run's records, and anything an
  agent left under `work/`, go, and Ariane's records start a new run as for `--restart`.
  `restarted_from` gets `"resumed": true`; the journal adds `ticket.resumed` after
  `ticket.restarted`.
- **The diffs start at the base.** The changed files, the checks' selection, the risk tier and
  the reviewer's diff start at the merge base of the kept head and the base branch, so the
  previous run's work is checked and reviewed; the guard's history check still starts at the new
  run's start commit.
- **What the session is told.** The first implementer session of the run gets, in the prompt, a
  section saying it continues an interrupted attempt, and, in an untrusted block
  (`kind="resume"`), the previous session's role, round and stop reason, the files the previous
  run changed from the base (without `work/`) and its last 4 journal entries, each cut at 2000
  characters, the "session started" entries (a whole prompt) left out. The journal entries hold
  agent text: they are data, as the ticket is.
- **Larger limit, once.** For that session only, the limit that stopped it is multiplied by
  `[agents.implementer] resume_factor` (at least 1, default 2): after `budget`, `max_budget_usd`
  and, when set, `max_tokens` (both are the session's budget, and the record does not say which
  cap was reached); after `timeout`, `timeout_minutes` (`idle_minutes` stays). The raised values
  are capped by `max_budget_usd_cap` and `timeout_minutes_cap`, optional, at least the value
  they cap, the raised value itself by default; `max_tokens` has no cap of its own. Ariane sets no
  turn limit, so after `turns` nothing is raised. The journal says which limit was raised, from
  what to what.
- **At most once in a row.** A run that was resumed and stops on a limit again refuses
  `--resume`, naming `--restart` or a hand takeover with `ariane verify`, and its stop line names
  only `--restart`. A quota stop raises nothing, so it can be resumed again.
- **A quota stop.** Nothing is raised. When the reviewer stopped, the implementer's work is
  committed on the kept branch: the run has no implementer session, replays the checks on the
  kept head and reviews it. The rounds continue from the previous run's (`metrics.rounds`), so
  the fix rounds already used count against C10's limit; the same holds after a fix session's
  limit. The runtime's reset time ("try again at 3:45 PM", "in 2 hours", an ISO time) is read as
  a UTC time, `reset_at` on the session in `metrics.json` (a clock time is the machine's local
  time at its next occurrence); before it, `--resume` refuses and names it. The quota's next
  action becomes "wait for the quota to reset (after <time>)", replacing ADR 0043's "restart the
  ticket after <time>", and `ariane next` names `--resume` for a quota-stopped ticket.
- **Stop lines.** A stop whose last session reached a limit or a quota (as above) ends with "to
  continue from its saved work, run `ariane start <n> --resume` (or `ariane start <n>
  --restart`)".
- The module `resume` holds this, so that `flow` and `restart` stay within the file length
  limit; the setup command's run moved from `flow` to `replay.run_setup`, its only caller, for the
  same reason.

## Consequences
- A ticket stopped near the end of its work continues in one command, with more room, once.
- The resumed branch carries the previous attempt's commits, the saved-work commit and a commit
  removing the previous records: the pull request's history shows the interruption.
- A clock time with a date Codex may give ("Oct 25, 3:45 PM") is read as the next 3:45 PM: the
  refusal can end early, and the resumed run then stops on the quota again; never later.
- Resuming a reviewer session itself, a resume without the person running it, and a resume after
  a crash with no limit reached (`--restart` covers it) are not provided.

## Alternatives considered
- **Start from the base and give the session the kept branch to read.** Redoes the work; C5 asks
  to resume it.
- **Raise the limits in the configuration file.** Raises them for every later ticket and asks
  for an edit by hand; the factor applies to one session.
- **Allow any number of resumes.** A ticket that cannot finish would grow its limits forever;
  once in a row, then a person decides.
- **Keep the previous run's records in the new run.** They describe another run and an agent
  could have left files beside them; the kept branch keeps them.
