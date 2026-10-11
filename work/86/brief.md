# Product brief: State in the config schema that an opencode agent needs max_tokens (C5, C25)

- Source: issue #86 (https://github.com/plaplanche/ariane/issues/86)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Two minor findings left by the reviews of #83 (PR #85): the generated configuration schema does not say that an opencode agent needs `max_tokens`, and `docs/architecture/modules/opencode.md` lists the session's environment variables without `OPENCODE_DISABLE_PROJECT_CONFIG=1`. This ticket is also the one used for slice 3's gate item "a ticket is reviewed on a second runtime": it runs with `ARIANE_CONFIG=docs/ariane.opencode-reviewer.example.toml`, so its reviewer runs on opencode. Spec: C5, C25.

## Current state

- `src/ariane/config_schema.py`: the `max_tokens` property of an agent says "Optional cap on tokens counted by Ariane per session." `config.parse` refuses an agent with `runtime = "opencode"` and no `max_tokens` (#83), so a configuration valid against `docs/reference/ariane.toml.schema.json` can be refused at load.
- `docs/architecture/modules/opencode.md`: the first bullet ("The environment adds `OPENCODE_CONFIG_CONTENT` …, `OPENCODE_DISABLE_CLAUDE_CODE=1` and `OPENCODE_DISABLE_AUTOUPDATE=1`") omits `OPENCODE_DISABLE_PROJECT_CONFIG=1`, which the paragraph above it names.

## Decided spec

- The agent schema states the rule: `max_tokens` is required when `runtime` is `opencode` (a JSON Schema `if`/`then` on the agent object), and its description says so. `docs/reference/ariane.toml.schema.json` is regenerated.
- The first bullet of `docs/architecture/modules/opencode.md` lists `OPENCODE_DISABLE_PROJECT_CONFIG=1` with the other variables.

## Release note

Fixed: the configuration schema says that an opencode agent needs `max_tokens`.

## Acceptance criteria

- A test named `test_c5_opencode_schema_*` shows that an opencode agent without `max_tokens` fails validation against the generated schema, and that a Claude Code agent without it passes.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c5_opencode_schema` runs at least 1 test and it passes.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/reference/ariane.toml.schema.json` regenerated; `docs/architecture/modules/opencode.md` and `config.md` updated.

## Related

#83, ADR 0029, spec C5, C25.
