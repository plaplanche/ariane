# Product brief: Run the setup command without credentials (C9, C21)

- Source: issue #48 (https://github.com/plaplanche/ariane/issues/48)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The independent review of slice 2 found that the setup command of the clean replay runs code the agent wrote with Ariane's full environment. Since #24 the setup also runs in the replay tree, which is checked out at the agent's commit. `_setup` passes no environment, so the child process inherits the tracker token (`tracker.token_env`), every other credential variable, the SSH agent and the machine's credential helper. Example: the agent adds a build hook to `pyproject.toml`; `uv sync` runs it during the replay setup, and it reads the token and sends it out. The remote check catches a push, not a stolen token. Spec: security row ("no secret in an agent's context"), C9, C21; ADR 0017 ("agent sessions and the checks keep running without any credential variable"); ADR 0018. The same gap was closed for the statuses workflow in #25.

## Current state

- `src/ariane/flow.py` `_TicketRun._setup` calls `process.run(command, cwd=cwd, timeout_s=SETUP_TIMEOUT_S)` with no `env`.
- `_setup` runs twice: in the ticket's worktree before the agent (base code) and in the replay tree (`_replay`, agent's commit).
- The checks in the replay already get `self.untrusted_env` (`context.untrusted_environment`: no credential variable, no SSH agent, a git that cannot push).
- No test checks the environment the setup gets.

## Decided spec

- `_setup` runs the setup command with `self.untrusted_env`, in both places (one rule, simplest).
- A setup that needs a credential fails visibly instead of receiving one.

## Release note

Security: the setup command no longer receives the tracker token or other credentials.

## Acceptance criteria

- Tests named `test_c9_setup_without_credentials_*` show, for the replay setup and for the first setup, that the setup command sees no tracker token variable and that a push from it is blocked.
- A negative control: the replay test fails if `_setup` is given the full environment again.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c9_setup_without_credentials` runs at least 2 tests and they pass.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

The statuses workflow (fixed in #25), the push itself (#30).
