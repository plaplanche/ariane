# Product brief: Let each agent runtime declare the login variables it keeps (C5, C21)

- Source: issue #32 (https://github.com/plaplanche/ariane/issues/32)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The agent's environment keeps the runtime's login by hard-coded prefixes (`ANTHROPIC_`, `CLAUDE_`) and strips any other name that looks like a credential, so another provider's key (for example one ending in `_API_KEY`) is removed. ADR 0015: each runtime declares the variables it keeps.

## Current state

- `src/ariane/context.py:20` `_AGENT_RUNTIME_PREFIXES = ("ANTHROPIC_", "CLAUDE_")`.
- `src/ariane/context.py:61` `untrusted_environment` keeps those prefixes when `keep_agent_login` is set.
- `src/ariane/runtime.py:42` `AgentRuntime` has `name` and `run`.

## Decided spec

- `AgentRuntime` gains `login_variables`: exact names and prefixes the runtime keeps for its own login. `ClaudeCodeRuntime` declares `ANTHROPIC_` and `CLAUDE_` (prefixes).
- `untrusted_environment` receives the runtime's list instead of the hard-coded prefixes; nothing else changes (the tracker token never passes, other credential-like names are stripped).
- The checks' environment keeps no login variable at all, as today.
- `known_secrets` treats a kept login variable whose name looks like a credential as a known secret, so it is still redacted from records and posts.

## Release note

Changed: each agent runtime declares the login variables it keeps.

## Acceptance criteria

- Tests named `test_c21_login_variables_*` show: a runtime declaring `OPENAI_API_KEY` keeps it in the agent's environment and not in the checks' environment; Claude Code keeps `ANTHROPIC_*` and `CLAUDE_*` as before; the tracker token is never kept, even if a runtime declares its name; a kept key is masked in records.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `src/ariane/context.py` has no hard-coded runtime prefixes.
- [ ] `uv run pytest -k c21_login_variables` runs at least 4 tests and they pass.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/context.md`, `docs/architecture/modules/runtime.md` and `docs/architecture/modules/claude_code.md` describe the runtime-declared login variables; the generated references are regenerated if they change.

## Out of scope

The opencode adapter (separate issue).

## Related

ADR 0015, ADR 0007, spec C5, C21.
