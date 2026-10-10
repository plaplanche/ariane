# Product brief: Configure the definition of done and give it to the implementer (C26)

- Source: issue #62 (https://github.com/plaplanche/ariane/issues/62)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

C26 and ADR 0023: a project configures its definition of done in `ariane.toml`; each item is a declared check or a sentence; the implementer receives every item; the reviewer later answers each sentence item (#33). Without the table, a default list applies. This ticket adds the configuration, the default and the prompt; the reviewer's item-by-item answer comes with #33.

## Current state

- `src/ariane/config.py` `Config` has `base_branch`, `setup`, `tracker`, `implementer`, `checks`; `parse()` refuses unknown keys.
- `src/ariane/context.py` `implementer_prompt` lists the rules and the checks Ariane will replay.

## Decided spec

- `[definition_of_done]` with `items = [ { check = "<name>" } | { text = "<sentence>" }, ... ]`. A `check` item must name a declared check (refused otherwise, naming the key); an empty `text` is refused; the table is optional.
- Default when absent: `{ text = "Every blocking check passes." }`, `{ text = "The change is covered by tests that fail without it." }`, `{ text = "The documentation the change affects is updated (C25)." }`.
- `Config.definition_of_done` holds the items; `implementer_prompt` gets a section "Definition of done" listing them (check items as "check <name> passes").
- Ariane's own `ariane.toml` declares its list: the five checks as check items, plus the test and documentation sentences (CLAUDE.md rule 11). `docs/ariane.example.toml` shows the table with comments.
- The generated configuration schema (generated-references issue) includes the table; the configuration and prompt docs in `docs/architecture/` are updated.

## Release note

Added: a configurable definition of done, given to the implementer.

## Acceptance criteria

- Tests named `test_c26_dod_*` show: a valid table is loaded; a check item naming an undeclared check is refused with the key named; an empty text is refused; the default list applies without a table; the implementer prompt lists every item.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c26_dod` runs at least 5 tests and they pass.
- [ ] Definition of done: the schema and `docs/ariane.example.toml` show the table; the architecture files of `config` and `context` are updated.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

The reviewer's item-by-item answer and the pull request body listing results (#33).

## Related

ADR 0023, spec C26, C22.
