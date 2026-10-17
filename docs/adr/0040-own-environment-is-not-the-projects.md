# 0040. Ariane's own environment is not the project's

- Status: accepted
- Date: 2026-10-17
- Capabilities: C5, C9, C22

## Context
Ariane often runs from its own virtual environment. The setup, the checks and the agent sessions
inherited `VIRTUAL_ENV` and its scripts directory on `PATH`, so the project's `uv run`, `python`
or `pytest` could resolve to Ariane's environment and a replay would not run what CI runs (C9).
`ARIANE_*` variables are Ariane's own settings, not the project's (C5, C22).

## Decision
- Ariane's own environment is not the project's. `untrusted_environment` withholds, for every
  caller, `VIRTUAL_ENV` and `VIRTUAL_ENV_PROMPT`, the `PATH` entries equal to the scripts directory
  of that environment and of the interpreter running Ariane (when it runs in a virtual
  environment), and every variable whose upper-cased name starts with `ARIANE_`.
- Entries compare after `os.path.normcase(os.path.normpath(...))`; other entries keep their order.
- The whole `ARIANE_` prefix is withheld rather than a list: a list goes stale each time Ariane
  gains a setting, and a forgotten name would leak Ariane's configuration to the project.
  `ARIANE_ROLE` is added by the runtimes afterwards.
- `PYTHONPATH`, `CONDA_*` and `UV_*` are unchanged (no evidence yet).

## Consequences
A project that wants an `ARIANE_*` variable must name it otherwise.

## Alternatives considered
A fixed list of names (`ARIANE_CONFIG`, `ARIANE_LOG_LEVEL`): simpler, but incomplete over time.
