# Product brief: Replay each check in its own clean working tree, as an isolated CI job runs it (C9)

- Source: issue #133 (https://github.com/plaplanche/ariane/issues/133)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

C9 says the checks run in a clean working tree created at the commit to deliver, and only that replay counts (ADR 0018). Today all checks run one after another in the same replay tree, so a check can rely on what an earlier check left behind (installed dependencies, build output, caches ignored by git). CI usually runs each check as its own job in a fresh checkout, where that leftover does not exist. In the benchmark on a reference project, a pull request Ariane delivered with every check replayed green went red in CI for exactly this reason: one CI job lacked dependencies another check had installed in the shared replay tree. Spec: C9, C8, C10 (`ariane verify` gets the same verification).

## Current state

- `src/ariane/replay.py:18-49`: `replay` creates one detached tree `<n>-replay` (`replay.py:28-31`), runs the setup there once (`replay.py:39-41`), then every check in it (`replay.py:42`, `checks.run_checks`, `src/ariane/checks.py:27-31`, sequential); the tree is returned and removed by the caller after the review (`src/ariane/flow.py:423-445`).
- The reviewer does not use that tree: `replay.review_round` creates its own `<n>-review` tree (`replay.py:62-65`).
- `src/ariane/verify.py:158-195`: `ariane verify` does the same in one tree `verify-<slug>` (`verify.py:159-163`): setup once (`verify.py:192`), then every check (`verify.py:193-194`).
- `[[checks]]` accepts `name`, `command`, `blocking`, `timeout_minutes` only (`src/ariane/config.py:330`).

## Decided spec

- **One tree per check.** For each check, in the declared order (the project's checks, then the generated documentation checks): create a fresh detached working tree at the commit to deliver, run the setup there, run that check only, verify the tree's head and Ariane's guard as today after the checks (`replay.py:43-45`), then remove the tree, also on a stop or Ctrl-C. Trees are named `<n>-replay-<k>` (`verify-<slug>-<k>` for `ariane verify`), `k` counting from 1. A leftover tree of that name refuses as today ("remove it, then retry").
- **Setup.** A setup failure or files left untracked by it stop the ticket exactly as today (`flow.py:189-216`), and the stop names the check whose tree it was.
- **Per-check setup.** New optional key `checks[].setup` (argument list): when present, it replaces `project.setup` in that check's tree, so a check can run with only what its CI job installs. Same timeout and rules as `project.setup`.
- **Shared code.** `flow`'s replay and `verify` use the same function for this loop (in `replay.py` or `checks.py`), so both replay identically.
- **Records.** `checks.md` says "Each check was replayed in its own clean working tree at `<commit>`, after the setup." The journal entry `ticket.checks.worktree` lists the trees, one line per check. Each check's duration in the table excludes its setup; the setup durations are in the journal entry.
- The setup now runs once per check: the cost in wall-clock time is accepted here; running the checks in parallel is a later ticket.
- A new ADR (next free number) supersedes ADR 0018's "one clean tree" part (ADR 0018 gets `accepted; clean-tree part superseded by NNNN`) and records the per-check setup key.

## Release note

Changed: each check is replayed in its own fresh working tree, so a check that only passes thanks to another check's leftovers fails in Ariane as it would in an isolated CI job.

## Acceptance criteria

- Tests named `test_c9_isolated_replay_*` show:
  - a first check that writes a file ignored by git and a second check that fails when that file is missing: the second check fails in the replay (it passes on the current code);
  - the setup runs once per check (counted by a setup command that appends to a file outside the trees);
  - `checks[].setup` replaces `project.setup` in that check's tree only;
  - no `<n>-replay-*` tree is left after a green ticket, a failing check, or a stop raised during the second check;
  - `ariane verify` replays the same way (one tree per check).
- `ariane.toml` with `checks[].setup` validates against the generated schema; an empty or non-list `setup` is refused naming `checks[<i>].setup`.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c9_isolated_replay` runs at least 5 tests and they pass.
- [ ] The new ADR is in `docs/adr/` and ADR 0018's status names it.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/replay.md`, `checks.md`, `verify.md`, `config.md`, `config_schema.md` (and `flow.md` if its workflow changes); `docs/architecture/3-components.md` sequences of `start` and `verify`; `docs/reference/ariane.toml.schema.json` and `docs/logs.md` regenerated; README paragraph on the replay; `docs/ariane.example.toml` shows `setup` on one check, commented.

## Out of scope

- Running the checks in parallel (later ticket, after the run slot).
- Changing CI (`.github/workflows/`).
- The reviewer's tree (unchanged).

## Related

ADR 0018, spec C8, C9, C10. Benchmark findings in `docs/benchmark.md` (#130). Followed by #143, which depends on this one and on #142.


---
_Generated by [Claude Code](https://claude.ai/code)_
