# Product brief: Install and run Ariane as a second user: bash commands, uv tool install, example configuration

- Source: issue #29 (https://github.com/plaplanche/ariane/issues/29)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

A second user will run Ariane on macOS, on their own GitHub repository, with Claude Code. The README gives commands in PowerShell only and installs from a local checkout. Decision: ADR 0021 (licence kept, installation, what the user must know); ADR 0017 (nobody runs git during a ticket).

## Current state

- `README.md:16` gives `uv tool install <path-to-the-ariane-checkout>` in a PowerShell block; every command block is PowerShell.
- `ariane.toml` is Ariane's own configuration; there is no example for another project.
- `src/ariane/flow.py:243` stops a ticket when the remote changed, with "check it was not the agent; if a person pushed, start the ticket again".

## Decided spec

- README: installation with `uv tool install git+https://github.com/plaplanche/ariane`, and every command block given twice, PowerShell and bash, with the same steps. A short section "While a ticket runs" says that nobody runs git commands in the repository or pushes to it, and why (the guard stops the ticket).
- A new file `docs/ariane.example.toml`: a commented configuration for another Python project (tracker, base branch, setup, implementer, checks), every key explained in a comment; `config.load` accepts it once renamed to `ariane.toml`.
- Every stop caused by the git guard (git configuration, hooks, local branches, or the remote changed) adds to its next action: "nobody runs git commands in the repository or pushes to it while a ticket runs".
- README links ADR 0021 for the licence and says that fixes are sent as issues.

## Release note

Added: installation from GitHub, bash commands and an example configuration for new users.

## Acceptance criteria

- A test named `test_c22_example_config_*` loads `docs/ariane.example.toml` with `config.parse` and gets no error.
- Tests named `test_c11_guard_message_*` show the sentence in the stop line for a changed remote and for changed git configuration.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `README.md` has a bash block for every PowerShell block.
- [ ] `uv run pytest -k "c22_example_config or c11_guard_message"` runs at least 3 tests and they pass.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

The setup assistant (C24, frozen), Ariane pushing with its own token (separate issue).

## Related

ADR 0021, ADR 0017, ADR 0008.
