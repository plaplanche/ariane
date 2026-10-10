# Product brief: Require an ADR for every open choice in Ariane's definition of done (C26)

- Source: issue #67 (https://github.com/plaplanche/ariane/issues/67)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The owner asked (2026-10-10) for Ariane's own definition of done (C26, ADR 0023) to require an ADR for every choice left open. CLAUDE.md rule 2 already says it for sessions; as a definition-of-done item, the implementer receives it in its prompt and the reviewer will check it item by item (#33).

## Current state

- `ariane.toml` `[definition_of_done]` lists the five checks and two sentences (tests, documentation).
- `docs/adr/README.md` holds the ADR template.

## Decided spec

- Add one sentence item at the end of the list: `{ text = "Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2)." }`.
- Nothing else changes; the configuration schema already allows it.

## Release note

Changed: Ariane's definition of done requires an ADR for every open choice.

## Acceptance criteria

- A test named `test_c26_dod_ariane_requires_adr` loads Ariane's `ariane.toml` and finds the new item, and the implementer prompt built from it lists the sentence.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c26_dod_ariane_requires_adr` runs 1 test and it passes.
- [ ] Definition of done: no documentation is affected beyond `ariane.toml` (say so in the summary if one is).
- [ ] All checks in CLAUDE.md pass.

## Out of scope

The reviewer's item-by-item answer (#33).

## Related

ADR 0023, spec C26, CLAUDE.md rule 2.
