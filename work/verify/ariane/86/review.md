# Review 0

- Reviewed commit: `95e654e4036d601b0b5c79984fd8312c60c5b28f`
- Reviewer model: openai/gpt-5
- Verdict: **go**

## Findings

- **minor** (`docs/reference/ariane.toml.schema.json:120`) Redundant if/then on implementer schema

  The generated schema for agents.implementer includes an if/then block that requires max_tokens when runtime == 'opencode', but implementer.runtime is restricted to 'claude-code'. This is harmless (JSON Schema 'if' is non-assertive) but adds noise. It could be removed by not inheriting the agent-level if/then for implementer.

- **minor** (`tests/test_docs_reference.py:146`) Implementer path not explicitly tested

  Acceptance criteria focus on the reviewer, and the added tests cover reviewer/opencode and reviewer/claude-code. Consider adding a small test that an implementer (always claude-code) does not require max_tokens to guard against future regressions.

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

  tests/test_docs_reference.py adds test_c5_opencode_schema_requires_max_tokens and test_c5_opencode_schema_claude_code_agent_needs_no_max_tokens (lines 146-161). Removing the if/then constraint from src/ariane/config_schema.py would make the first test fail.

- met: The documentation the change affects is updated (C25).

  docs/architecture/modules/opencode.md now lists OPENCODE_DISABLE_PROJECT_CONFIG=1 in the environment bullet (line 5). docs/architecture/modules/config.md mentions the if/then requirement in the Runtimes bullet (line 16). docs/architecture/modules/config_schema.md notes the agent-level if/then (line 7). docs/reference/ariane.toml.schema.json regenerated with updated max_tokens description and if/then.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The spec is fully decided (require max_tokens for opencode and update the opencode module docs). No new open choices arose; existing ADR 0029 covers the runtime policy.

## Proposed learnings (not decided)

- Express runtime-specific constraints in the generated schema to keep parser and schema behavior aligned; add tests that assert both layers agree.
- When narrative docs and bullet lists describe environment variables, keep them strictly consistent with the implementation to avoid subtle drift.
