# Product brief: Selective checks: checks[].paths and ARIANE_CHANGED_FILES (C9)

- Source: issue #184 (https://github.com/plaplanche/ariane/issues/184)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Every ticket replays every check, whatever it changes: a one-line documentation fix waits for the whole test suite, and with several tickets at once (#159, #142, #143) the replays queue up. The owner wants Ariane to test what must be tested, and to adapt the amount of testing to the ticket. This first ticket lets a project say which files each check covers, and gives a check the list of changed files so it can choose its own tests. Spec: C9 (deterministic checks); ADR 0041 (one clean tree per check), ADR 0042 (`not_run_locally`, the same path globs).

## Current state

- `src/ariane/config_schema.py` (`checks` items): `name`, `command`, `blocking`, `timeout_minutes`, `setup`, `not_run_locally`; no key ties a check to the files it covers.
- `src/ariane/flow.py` `all_checks()` returns every configured check plus the documentation checks; `src/ariane/replay.py` `replay()` runs all of them in every round.
- `src/ariane/config.py:123` `matching_paths(globs, paths)` already matches path globs against changed files (ADR 0042).
- `src/ariane/delivery.py:116` `_publish_statuses` posts one commit status per check that ran.

## Decided spec

- **A check's scope.** Two new optional keys on `checks[]`:
  - `paths`: a non-empty list of path globs (same rules as `not_run_locally`); the check is selected when at least one changed file of the ticket (the diff from the base commit to the replayed commit, renames counted on both sides) matches;
  - `always = true`: the check is always selected (the default when `paths` is absent, so existing configurations keep running everything).
  Setting both is refused, naming `checks[<i>]`. Documentation checks (`documentation.generated`) are always selected.
- **Configuration changes select everything.** When the diff touches `ariane.toml` or a file the project lists in a new key `[project] check_all_paths` (globs, for example lockfiles and CI files), every check is selected.
- **Changed files for the check.** Every check (selected or not run) gets `ARIANE_CHANGED_FILES`: the path of a file in the replay tree's `work/<n>/` folder listing the changed files, one per line, relative to the repository root. A check may use it to run only the tests related to them (for example `vitest related` or a pytest plugin); Ariane does not interpret it. The variable is set by Ariane after the environment is built (it is not a project variable).
- **Records and statuses.** `checks.md` lists the checks not selected with the reason ("no changed file matches `paths`"); the summary table shows them as `skipped`. A skipped check posts a `success` commit status whose description says "skipped by Ariane: no changed file matches", so required statuses do not block the pull request, and the pull request body lists the skipped checks. The reviewer's prompt lists them too.
- **Same selection in every round** of a ticket: the selection is computed once per round from that round's diff.
- New ADR: selective checks, why the default stays "all", why configuration changes select everything, why the changed-files list is a file and not a variable value (length limits on Windows).

## Release note

Added: a check can declare the files it covers (`checks[].paths`); Ariane skips it when a ticket changes none of them, and gives every check the list of changed files (`ARIANE_CHANGED_FILES`).

## Acceptance criteria

- Tests named `test_c9_selective_checks_*` show:
  - a check with `paths` that no changed file matches is not run, is recorded as skipped in `checks.md` and its status says it was skipped;
  - the same check runs when one changed file matches, including a renamed file whose old path matches;
  - a check without `paths`, a check with `always = true`, and the documentation checks always run;
  - a change to `ariane.toml` or to a `check_all_paths` file selects every check;
  - `paths` and `always` together, an empty `paths` and a non-string entry are refused by the schema, naming the check;
  - `ARIANE_CHANGED_FILES` names a file listing exactly the changed files, for a check that runs.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c9_selective_checks` runs at least 6 tests and they pass.
- [ ] A new ADR records the decision.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/checks.md`, `replay.md`, `config.md`, `config_schema.md`, `delivery.md`; `docs/reference/` (schema) and `docs/logs.md` regenerated; `docs/ariane.example.toml` (a commented `paths` example); README's paragraph on checks.

## Out of scope

- Ariane's own `ariane.toml` keeps every check on (its checks are fast; measured first in the follow-up tickets).
- Choosing the amount of testing from the ticket's risk: #185. Measuring what selection misses: #186.
- The project's own CI, which still runs everything on the pull request.

## Related

#133 (one clean tree per check), #136 (`not_run_locally`), #137 (review sized), #142 (run slot), #143 (parallel checks), #159 (parallel guard); ADR 0041, ADR 0042; spec C9.


---
_Generated by [Claude Code](https://claude.ai/code)_
