# Review 1

- Reviewed commit: `30477f3dd301c1e025ad5046cbb248d67fd79f39`
- Reviewer model: openai/gpt-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/config_schema.py:30`) Schema does not require max_tokens for opencode

  The agent schema still describes max_tokens as optional and there is no JSON Schema if/then to require it when runtime == "opencode". Spec requires adding an if/then on the agent object and updating the description.

- **blocking** (`docs/reference/ariane.toml.schema.json:155`) Reference schema not regenerated to reflect new rule

  The generated reference keeps "Optional cap..." for max_tokens and contains no if/then blocks on agents. It must state "required when runtime is opencode" and include the conditional requirement.

- **blocking** (`tests/test_docs_reference.py:1`) Missing acceptance tests for schema rule

  No tests named test_c5_opencode_schema_* are present to assert that an opencode agent without max_tokens fails JSON Schema validation while a claude-code agent passes, as required by the acceptance criteria.

- **blocking** (`docs/architecture/modules/opencode.md:5`) Environment variable list incomplete

  The first bullet omits OPENCODE_DISABLE_PROJECT_CONFIG=1. The paragraph above mentions it; ticket requires adding it to the bullet list.

- **blocking** (`docs/architecture/modules/config.md:16`) Runtime docs do not mention schema-level requirement

  The runtimes section does not say the generated schema enforces max_tokens for opencode via an if/then on the agent object, as per the decided spec.

- **minor** (`docs/architecture/modules/config_schema.md:7`) Module doc not updated for if/then rule

  The description of SCHEMA does not mention the agent-level if/then that requires max_tokens for opencode, which is part of the decided spec.

- **minor** (`tests/test_docs_reference.py:33`) Schema test helper lacks const and if/then support

  The local JSON Schema subset validator does not handle "const" or "if"/"then". With the new rule, it should be extended to check these keywords to keep tests meaningful.

- **blocking** Definition of done not met: The change is covered by tests that fail without it.

  No tests named test_c5_opencode_schema_* exist; tests/test_docs_reference.py’s helper does not support const/if/then and would not catch the new constraint.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  docs/architecture/modules/opencode.md line 5 omits OPENCODE_DISABLE_PROJECT_CONFIG=1; docs/architecture/modules/config.md line 16 does not mention the schema if/then; docs/reference/ariane.toml.schema.json retains the old description and lacks the conditional requirement.

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

  No tests named test_c5_opencode_schema_* exist; tests/test_docs_reference.py’s helper does not support const/if/then and would not catch the new constraint.

- **not met**: The documentation the change affects is updated (C25).

  docs/architecture/modules/opencode.md line 5 omits OPENCODE_DISABLE_PROJECT_CONFIG=1; docs/architecture/modules/config.md line 16 does not mention the schema if/then; docs/reference/ariane.toml.schema.json retains the old description and lacks the conditional requirement.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  No open choices introduced by this change; ADR 0029 already documents the opencode reviewer runtime. No additional ADR appears necessary.

## Proposed learnings (not decided)

- When parse() enforces a rule, mirror it in the JSON Schema and add a targeted test to prevent regressions.
- Keep documentation consistent across narrative paragraphs and bullet lists to avoid omissions (e.g., environment variables).
- Extend internal schema test utilities alongside schema features (e.g., support const and if/then) to ensure tests actually validate new constraints.
- Regenerate and commit reference artifacts (docs/reference) whenever schema changes, and assert equality to code to catch drift.
