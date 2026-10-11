# Product brief: Keep ARIANE_CONFIG out of the agents' and checks' environment (C22, C9)

- Source: issue #87 (https://github.com/plaplanche/ariane/issues/87)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Running #86 with `ARIANE_CONFIG=docs/ariane.opencode-reviewer.example.toml` (slice 3's gate, "a ticket is reviewed on a second runtime") stopped before the review: the replay of the checks failed on 12 tests. `ARIANE_CONFIG` names Ariane's own configuration, yet it passes into the environment of the agent sessions and of the checks. Ariane's tests start `ariane` in temporary projects; those processes inherit the variable, look for `docs/ariane.opencode-reviewer.example.toml` in the temporary project and refuse to start ("Refused configuration: ARIANE_CONFIG (docs/ariane.opencode-reviewer.example.toml): file not found in …"). Any run with `ARIANE_CONFIG` set therefore fails its own checks, whatever the change. Reproduced on `main`: `tests/test_cli.py::test_c22_start_refuses_an_invalid_configuration_naming_the_key` fails with the variable set and passes without it. Spec: C22, C9.

## Current state

- `src/ariane/config.py:160`: `load` reads `ARIANE_CONFIG` (`CONFIG_ENV`, line 21) from the environment it is given.
- `src/ariane/context.py:109`: `untrusted_environment` copies every variable of `base` except the tracker token, credential channels and secret-looking names; `ARIANE_CONFIG` passes through.
- `src/ariane/flow.py:143` and `:151` (`ariane start`), `src/ariane/verify.py:113` and `:119` (`ariane verify`): the agent sessions' and the checks' environments are built with `untrusted_environment` from Ariane's own environment.

## Decided spec

- `untrusted_environment` drops `ARIANE_CONFIG` (matched case-insensitively, like the other names it withholds), for agent sessions and for checks alike: it is the configuration of the Ariane that runs the ticket, not of code the ticket runs. The value is not a secret: `known_secrets` does not change.
- Nothing else changes: `config.load` still reads `ARIANE_CONFIG` from Ariane's own environment.

## Release note

Fixed: a run started with `ARIANE_CONFIG` no longer passes that variable to its agents and checks, so Ariane's own tests pass in the replay.

## Acceptance criteria

- A test named `test_c22_untrusted_environment_*` shows that `untrusted_environment` drops `ARIANE_CONFIG` (also in another case, for example `ariane_config`) with and without login variables, and keeps an unrelated variable.
- A test shows that `uv run pytest` started with `ARIANE_CONFIG` set to a file absent from the test projects still passes the CLI tests, or equivalently that the checks of a run started with `ARIANE_CONFIG` do not see it.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c22_untrusted_environment` runs at least 1 test and it passes.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/context.md` updated (the variables `untrusted_environment` withholds); README's paragraph on `ARIANE_CONFIG` says it does not reach agents or checks.

## Out of scope

- Changing how `ARIANE_CONFIG` is resolved, or any other `ARIANE_*` variable.
- Re-running #86: done by hand after this ticket is merged.

## Related

#86, #83, spec C9, C22, C25.
