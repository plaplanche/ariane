# Review 0

- Reviewed commit: `e0773dbfcf3191a0886b4698dfbbdb71b6b6b894`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/architecture/modules/config.md:16`) config.md still says the if/then sits on "the agent object"

  The text says "the generated schema states the rule with an `if`/`then` on the agent object". After this change only the reviewer's object carries it (config_schema.py:93-96). Both readings point to opencode agents, which today means the reviewer, so it is not wrong. But it is less precise than the updated config_schema.md. Suggested wording: "on the reviewer object".

- **minor** (`README.md:7`) Status line is longer than the wrapped lines around it

  The line "**Status:** slice 3 (review, vendor-neutral) is done: `ariane start <issue>` takes a GitHub issue to a" is about 104 characters, while the rest of the paragraph wraps near 100. This is cosmetic and no check enforces it.

- **minor** (`tests/test_docs_reference.py:175`) Implementer test relies on ariane.toml having no max_tokens

  `pop("max_tokens", None)` makes the test hold whatever ariane.toml contains, which is fine. But it only checks the implementer schema and the helper, never `config.parse`. The schema/parse agreement for an implementer without max_tokens is covered only indirectly, by test_docs_reference_config_files_validate.

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

- met: The change is covered by tests that fail without it.

  test_c5_schema_implementer_needs_no_max_tokens_and_has_no_if_then asserts that "if"/"then" are absent from the generated implementer schema, so it fails on the old schema, which merged the if/then from _AGENT. test_c5_schema_integer_refuses_fraction_and_zero_accepts_ten fails without the new `integer` branch in errors(): the old helper ignored type "integer", so 1.5 and 0 were accepted. test_docs_reference_schema_file_is_the_code_schema and the generator --check tie the regenerated JSON to config_schema.SCHEMA. `-k "c5_schema_implementer or c5_schema_integer"` selects 2 tests, and the replayed tests are green.

- met: The documentation the change affects is updated (C25).

  README.md status says slice 3 is done and slice 4 (measurement and shadow mode) is next, then slice 5. ADR 0029 has the "Amendment (slice 3 gate)" on PWD/--dir, which matches src/ariane/opencode.py:76 and :83. docs/reference/ariane.toml.schema.json is regenerated (the docs: references check passes). docs/architecture/modules/config_schema.md is updated. config.md:16 is still slightly imprecise (minor finding).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The one design choice, putting the max_tokens if/then on the reviewer only, is recorded in the new ADR 0029 amendment (lines 39-40), together with the PWD/--dir behaviour. No other open choice is introduced.

## Proposed learnings (not decided)

- When a shared schema fragment (like _AGENT) carries conditional rules, split them into a separate fragment that is merged only into the roles that can trigger them; otherwise the generated reference holds dead rules.
- A test-only JSON Schema validator should fail on unknown `type` values instead of silently accepting them, so new types (such as `integer`) cannot go unchecked.
- When moving a schema rule, grep docs/architecture/ for every mention (here config.md as well as config_schema.md), not only the module that owns the code.
