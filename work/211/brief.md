# Product brief: Resume a ticket stopped by its budget, turn or time limit, or by a runtime quota, from its saved work (C5, C23)

- Source: issue #211 (https://github.com/plaplanche/ariane/issues/211)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Spec C5 says: "A session stopped by budget, turns or timeout leaves its work saved on the ticket branch and a clear status; the next run resumes it, with a larger budget after a budget stop, capped by the configuration." Today only the first half holds. On 18 October an implementer session of a ticket reached its 30-minute limit while running the tests; the ticket stopped without a pull request, with about 500 lines of work in its tree. `ariane start <n> --restart` (ADR 0047) saved that work on the kept branch `ariane-restarted/<n>-<time>`, as designed, but the new run started from the base branch: the new session redid the work from nothing, and the only way to give it more time was a hand-made configuration file. Spec: C5 (agent sessions), C23 (restart, verify).

## Current state

- `restart.clear` keeps the previous branch, with the uncommitted work saved in a commit on top, and the new run starts a fresh branch from the base (ADR 0047).
- The stop reason (`finished`, `budget`, `turns`, `timeout`, `idle`, `error`) is in `metrics.json` per session.
- `[agents.implementer]` has `max_budget_usd`, `timeout_minutes` and `idle_minutes`; nothing raises them for a second attempt.

## Decided spec

- **`ariane start <n> --resume`.** Allowed only when the previous run of the ticket stopped because its implementer (or a fix session) reached a limit: `budget`, `turns` or `timeout`, read from the previous run's `metrics.json` on its branch. Any other stop refuses `--resume` and names `--restart`.
- **What it keeps.** The restart steps of ADR 0047 run as today (lock, saved work, kept branch), then the new branch `ariane/<n>` starts **from the kept branch's head** instead of the base branch, and the new implementer session is told, in its prompt, that it continues an interrupted attempt: the previous session's stop reason, its last journal entries and the list of files it changed are given as data. Ariane's own records (`work/<n>/`) start a new run as for `--restart`, and keep `restarted_from` with `"resumed": true`.
- **Larger limit.** For that session only, the limit that stopped it is raised by `[agents.implementer] resume_factor` (default 2: twice the budget after a budget stop, twice the time after a timeout, twice the turns), capped by new optional settings `max_budget_usd_cap`, `timeout_minutes_cap` (defaults: the raised value itself). The journal says which limit was raised, from what to what.
- **At most once in a row.** A resumed run that stops on a limit again refuses another `--resume` and names `--restart` or a hand takeover, so a ticket never loops on limits.
- **A quota stop (owner, 21 October 2026).** `--resume` also accepts a run stopped because an agent's runtime reported its usage limit (stop reason `quota`, ADR 0043), for the implementer, a fix session or the reviewer. No limit is raised. When the stopped session was the reviewer (the implementer's work is committed on the branch), the resumed run starts `ariane/<n>` from the kept branch's head, replays the checks and goes to the review without a new implementer session; the fix rounds already used count against C10's limit. Before the reset time the runtime gave (when it gave one), `--resume` refuses and names that time.
- The stop message of a limit or quota stop names `--resume` (and `--restart` as the other choice); a quota stop names the reset time when the runtime gave one.
- ADR (next free number): why the branch continues from the saved work, what the session is told, the factor and caps, and the once-in-a-row rule.

## Release note

Added: `ariane start <n> --resume` continues a ticket stopped by its budget, turn or time limit from the work it saved, with that limit raised once.

## Acceptance criteria

- Tests named `test_c5_resume_*` show:
  - after a timeout stop, `--resume` starts `ariane/<n>` from the kept branch's head, keeps the saved files, and doubles `timeout_minutes` for the session; after a budget stop it doubles `max_budget_usd`; a cap lowers the raised value;
  - the implementer prompt names the previous stop reason and changed files, inside the untrusted-data envelope;
  - `--resume` after a check failure, a review hand-over or a guard stop is refused and names `--restart`;
  - a second limit stop after a resume refuses `--resume`;
  - the stop line of a limit stop names `--resume`;
  - after a reviewer quota stop, `--resume` replays the checks and reviews the kept head with no new implementer session, raises no limit, and is refused before the given reset time.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c5_resume` runs at least 7 tests and they pass.
- [ ] `resume_factor` and the caps in the configuration schema and `docs/ariane.example.toml`.
- [ ] A new ADR records the decision.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/flow.md`, `restart.md`, `context.md`, `config.md`, `config_schema.md`, `metrics.md`, `cli.md`; `docs/reference/ariane.toml.schema.json`, `docs/reference/cli.md` and `docs/logs.md` regenerated; README (restarting and resuming a ticket).

## Out of scope

- Resuming after a container or machine restart (no limit was reached; `--restart` covers it).
- Resuming a reviewer session.
- Raising limits without the person running `--resume`.

## Related

#140 and ADR 0047 (`--restart`), #141 (idle watchdog), spec C5, C23.


---
_Generated by [Claude Code](https://claude.ai/code)_
