# Review 0

- Reviewed commit: `42a0ca9c863a03a8c8f31727bcdd0626e70940a1`
- Reviewer model: openai/gpt-5
- Verdict: **go**

## Findings

- **minor** (`tests/test_docs_reference.py:65`) Schema helper does not validate 'integer' type

  The minimal JSON Schema validator in tests handles 'number' but not 'integer'. This means integer-only constraints (like type errors or exclusiveMinimum on integers) are not checked by this helper. It doesn't impact this ticket because the test asserts the 'required' constraint via if/then, but expanding the helper to support 'integer' would improve coverage fidelity.

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

  Added tests test_c5_opencode_schema_requires_max_tokens and test_c5_opencode_schema_claude_code_agent_needs_no_max_tokens in tests/test_docs_reference.py (lines 146-161). They validate the generated schema: opencode without max_tokens fails (missing), claude-code without it passes. Without the schema change (if/then) the first test would fail.

- met: The documentation the change affects is updated (C25).

  docs/reference/ariane.toml.schema.json regenerated with if/then for both agents; docs/architecture/modules/opencode.md bullet now lists OPENCODE_DISABLE_PROJECT_CONFIG=1 (line 6); docs/architecture/modules/config.md mentions the schema rule (line 16); docs/architecture/modules/config_schema.md documents the if/then (line 7).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The spec was fully decided (require max_tokens for opencode in schema; list the env var). No open choices remained to record beyond existing ADR 0029 referenced in the docs.

## Proposed learnings (not decided)

- When runtime-specific validation exists in code, encode it in the generated schema too so config files fail early and consistently.
- Testing against the generated reference artifacts (schema files) catches drift between code and docs.
- For external runtimes, keep environment variable documentation consistent across introduction and bullet lists to avoid confusion.
