# Product brief: Start agent sessions without the person's user-level plugins and mods (C6)

- Status: draft
- Approved: not yet
- Source: issue #39 (https://github.com/plaplanche/ariane/issues/39)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Claude Code now loads plugins and mods that a person installs at user level (hooks, panels, skills). When Ariane runs on that person's machine, the `claude -p` sessions it starts may load them too: a mod that writes rules into `CLAUDE.md`, or one that holds a risky command until someone clicks "Proceed", would act inside an agent session nobody watches. Spec C6: only the skills a project declares are available to a role; ADR 0015: a runtime loads only what the project declares, or is refused for the role.

## Current state

- `src/ariane/claude_code.py:35` `command` passes `--strict-mcp-config` (no extra MCP server) but nothing about plugins, hooks or settings sources.
- Probe on Claude Code 2.1.292 (2026-10-09), with a plugin `marker-probe` installed at user level in a temporary home (`claude plugin install marker-probe@probe-market --scope user`) whose `SessionStart` and `UserPromptSubmit` hooks create marker files, in a project whose `CLAUDE.md` asks to answer "PINEAPPLE", running `claude -p --output-format json --model claude-haiku-4-5-20251001 --tools "" --no-session-persistence`:
  - no extra flag: both markers created, answer "PINEAPPLE" (the user plugin's hooks run in the agent session);
  - `--setting-sources project,local`: no marker, answer "PINEAPPLE", login kept;
  - `--setting-sources project`: no marker, answer "PINEAPPLE";
  - `--setting-sources ""`: no marker, but `CLAUDE.md` is not read (answer "2 + 2 = 4").
- `--bare` skips plugin hooks but also `CLAUDE.md` discovery and OAuth login, so it is not used.

## Decided spec

- `ClaudeCodeRuntime.command` passes `--setting-sources project,local` for every session, so settings, plugins, mods and hooks installed at user level never load in an agent session, while the project's `CLAUDE.md`, its own settings and the login are kept.
- `docs/adr/0015-runtime-neutral-agent-contract.md` gains a short "Plugins and mods" paragraph with the probe above (version, commands, results).

## Release note

Security: agent sessions started by Ariane load no plugin or mod installed by the person.

## Acceptance criteria

- Tests named `test_c6_no_user_plugins_*` show that the Claude Code command carries `--setting-sources project,local`.
- The ADR paragraph names the Claude Code version, the flag and the probe's results.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c6_no_user_plugins` runs at least 1 test and it passes.
- [ ] ADR 0015 has a "Plugins and mods" paragraph.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Declared skills per role (slice 8), opencode (its adapter already uses `--pure` and `OPENCODE_DISABLE_CLAUDE_CODE=1`).

## Related

ADR 0015, ADR 0014, spec C6, C5; #32 (login variables per runtime).
