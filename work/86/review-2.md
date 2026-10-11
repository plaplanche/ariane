# Review 2

- Reviewed commit: `30477f3dd301c1e025ad5046cbb248d67fd79f39`
- Reviewer model: openai/gpt-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/config_schema.py:30`) Agent schema does not state opencode max_tokens requirement

  The description for agents.<role>.max_tokens still says "Optional..." and there is no conditional requirement tied to runtime=opencode. Spec C5 requires the generated schema to enforce that opencode agents must set max_tokens.

- **blocking** (`src/ariane/config_schema.py:34`) Missing if/then in agent object to require max_tokens when runtime=opencode

  _AGENT lacks a JSON Schema if/then that requires max_tokens when runtime is opencode. Without it, configurations can validate against the schema yet be rejected by config.parse, violating the spec and acceptance criteria.

- **blocking** (`docs/reference/ariane.toml.schema.json:158`) Reference schema not regenerated with opencode conditional

  The reviewer agent still documents max_tokens as "Optional..." and there is no if/then requiring it when runtime is opencode. The acceptance checklist (C25) requires this file to be regenerated to reflect the rule.

- **blocking** (`docs/architecture/modules/opencode.md:5`) Missing OPENCODE_DISABLE_PROJECT_CONFIG=1 in environment variables list

  The first bullet does not list OPENCODE_DISABLE_PROJECT_CONFIG=1 alongside the other variables, despite the context and spec calling for it.

- **blocking** (`tests/test_docs_reference.py:131`) Missing tests for opencode max_tokens schema rule

  There are no tests named test_c5_opencode_schema_* asserting that an opencode agent without max_tokens fails validation while a claude-code agent passes. The acceptance criteria require these tests.

- **minor** (`docs/architecture/modules/config.md:16`) Docs do not state the generated schema enforces opencode max_tokens

  The Runtimes section does not mention that the generated schema encodes the requirement via an if/then on the agent object.

- **minor** (`docs/architecture/modules/config_schema.md:7`) Docs omit mention of agent-level if/then constraint

  The module overview for config_schema does not note that SCHEMA enforces max_tokens when runtime is opencode using if/then, as specified.

- **blocking** Definition of done not met: The change is covered by tests that fail without it.

  No tests named test_c5_opencode_schema_* exist; tests/test_docs_reference.py ends at line 131 without these cases.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  docs/reference/ariane.toml.schema.json not regenerated to add if/then and updated descriptions; docs/architecture/modules/opencode.md does not list OPENCODE_DISABLE_PROJECT_CONFIG=1; docs/architecture/modules/config.md not updated to mention the schema rule.

## Definition of done

- met: check lint passes

  Replayed by Ariane: exit 0.

- met: check format passes

  Replayed by Ariane: exit 0.

- met: check types passes

  Replayed by Ariane: exit 0.

- met: check tests passes

  Replayed by Ariane: exit 0.

- met: check file length passes

  Replayed by Ariane: exit 0.

- **not met**: The change is covered by tests that fail without it.

  No tests named test_c5_opencode_schema_* exist; tests/test_docs_reference.py ends at line 131 without these cases.

- **not met**: The documentation the change affects is updated (C25).

  docs/reference/ariane.toml.schema.json not regenerated to add if/then and updated descriptions; docs/architecture/modules/opencode.md does not list OPENCODE_DISABLE_PROJECT_CONFIG=1; docs/architecture/modules/config.md not updated to mention the schema rule.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  No new open choices beyond ADR 0029’s runtime policy; the ticket’s spec is precise (require max_tokens for opencode) and leaves no additional decisions to capture.

## Proposed learnings (not decided)

- Keep generated schemas in lockstep with runtime validation to avoid configs that pass schema but fail at load.
- When adding JSON Schema conditionals, extend the local schema test helper to cover const and if/then so regressions are caught.
- Update all impacted docs together (module docs and reference artifacts) to maintain a single source of truth.
- Centralizing agent constraints at the shared schema level via if/then is effective, but ensure role-specific overrides remain coherent.
