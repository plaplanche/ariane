# Review 0

- Reviewed commit: `a8851e636e7338ed104e1ef89a4004921b26c061`
- Reviewer model: openai/gpt-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/config_schema.py:27`) Schema does not require max_tokens for opencode agents

  _AGENT lacks a JSON Schema if/then rule to require max_tokens when runtime == "opencode", and the description still reads "Optional cap...". This contradicts parse() which enforces it, and does not meet the ticket spec.

- **blocking** (`docs/reference/ariane.toml.schema.json:110`) Generated schema not regenerated to encode opencode requirement

  The committed schema contains no if/then on agents and keeps the description "Optional cap on tokens..." for both implementer and reviewer sections. It must state and enforce that opencode requires max_tokens per the spec.

- **blocking** (`tests/test_docs_reference.py:1`) Missing acceptance tests for C5 opencode schema

  No tests named test_c5_opencode_schema_* exist. Acceptance requires tests that prove an opencode agent without max_tokens fails validation while a claude-code agent without it passes.

- **blocking** (`docs/architecture/modules/opencode.md:5`) Documentation omits OPENCODE_DISABLE_PROJECT_CONFIG in the environment bullet

  The paragraph mentions OPENCODE_DISABLE_PROJECT_CONFIG=1, but the first bullet listing environment variables omits it. The ticket requires adding it alongside the others.

- **blocking** (`docs/architecture/modules/config.md:16`) Config docs not updated to mention schema rule

  Runtimes section states opencode must set max_tokens, but does not note that the generated schema encodes this via an if/then on the agent object as required by the spec.

- **minor** (`tests/test_docs_reference.py:29`) Test helper does not support const and if/then

  errors() does not implement JSON Schema const and if/then. The ticket’s proposed tests rely on these; without extending errors(), such tests cannot assert the behavior at the schema layer.

- **minor** (`docs/architecture/modules/config_schema.md:3`) Module doc likely needs a note about the new if/then rule

  Given config_schema.py changes, consider documenting that the schema encodes the opencode max_tokens requirement with an if/then guard to keep architecture docs aligned with behavior.

- **blocking** Definition of done not met: The change is covered by tests that fail without it.

  No tests named test_c5_opencode_schema_* are present; grep finds none in tests/. The suite does not assert the new schema rule.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  docs/reference/ariane.toml.schema.json not updated with if/then; docs/architecture/modules/opencode.md bullet still omits OPENCODE_DISABLE_PROJECT_CONFIG=1; docs/architecture/modules/config.md does not mention the schema encodes the rule.

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

  No tests named test_c5_opencode_schema_* are present; grep finds none in tests/. The suite does not assert the new schema rule.

- **not met**: The documentation the change affects is updated (C25).

  docs/reference/ariane.toml.schema.json not updated with if/then; docs/architecture/modules/opencode.md bullet still omits OPENCODE_DISABLE_PROJECT_CONFIG=1; docs/architecture/modules/config.md does not mention the schema encodes the rule.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The spec mandates a specific schema change (if/then) and a docs tweak; no new open choices identified. Existing ADR 0029 already covers runtimes.

## Proposed learnings (not decided)

- When parse() enforces a rule, mirror it in the JSON Schema so tooling and examples stay consistent.
- Acceptance tests should target the generated artifacts (schema) and include helper support (const, if/then) to validate the intended constraints.
- Small doc deltas (like adding one env var to a bullet) are easy to miss; map code changes to docs and verify both narrative and lists are updated.
