# Product brief: Declare a project's documentation and flag documents a ticket left untouched (C25)

- Source: issue #70 (https://github.com/plaplanche/ariane/issues/70)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

C25 (Documentation upkeep, ADR 0022): a project declares its documentation and the commands that regenerate its generated documents; a stale generated document fails a check; the implementer is told which documentation covers the files it changes, and the reviewer checks that the ticket updated it. Today only Ariane's own repository checks its documentation, through a test (`scripts/generate_docs.py --check`, #60, #61); nothing lets another project declare its documentation, and the implementer only gets the generic definition-of-done sentence.

## Current state

- `src/ariane/config.py` `Config` has `definition_of_done` (#62) but no documentation settings.
- `src/ariane/context.py` `implementer_prompt` lists the checks and the definition of done.
- `src/ariane/flow.py` replays the declared checks in the clean tree (`_replay`); the journal records the agent's changed files ("Agent work committed").
- The reviewer (#33) receives the diff, the checks' summary and the definition-of-done items.

## Decided spec

- `ariane.toml` gains an optional `[documentation]` table:
  - `paths`: the documentation files and folders (for example `["docs/", "README.md"]`), for `ariane docs-review` later.
  - `[[documentation.map]]` entries `{ source = "<glob>", docs = ["<path>", ...] }`: which documentation covers which source files; in `docs`, `{stem}` stands for the matched file's name without extension (for example `{ source = "src/ariane/*.py", docs = ["docs/architecture/modules/{stem}.md"] }`).
  - `[[documentation.generated]]` entries `{ name = "<name>", check = [argv] }`: a command that exits non-zero when a generated document is stale.
- The implementer's prompt gets a section "Documentation" with the map, so the agent knows which documents to update for the files it changes.
- After the agent's work is committed, Ariane lists the mapped documents for the changed source files that the ticket did not change, journals them (`ticket.docs.not_updated`, a functional log type) and passes the list to the reviewer as a fact; it does not stop the ticket by itself (the reviewer judges the definition-of-done item).
- Each `generated` entry runs in the clean replay like a blocking check named `docs: <name>`, without credentials, and appears in `checks.md` and the statuses.
- Ariane's own `ariane.toml` declares `paths = ["docs/", "README.md"]`, the map above, and `generated = [{ name = "references", check = ["uv", "run", "python", "scripts/generate_docs.py", "--check"] }]`.
- The configuration schema, `docs/ariane.example.toml`, the log catalogue and `docs/architecture/` (`config`, `context`, `flow`, `checks` files) are updated.

## Release note

Added: a project declares its documentation; Ariane tells the implementer which documents cover its changes, flags the ones left untouched, and checks generated documents in the replay.

## Acceptance criteria

- Tests named `test_c25_docs_*` show: the table is loaded and validated (a `generated` entry without `check`, a map entry without `source`, are refused naming the key); `{stem}` expands; the prompt lists the map; a changed source file whose mapped document is untouched is journaled and given to the reviewer, and one whose document changed is not; a stale generated document fails the replay as `docs: <name>`; without the table nothing changes.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c25_docs` runs at least 6 tests and they pass.
- [ ] Definition of done: schema, example configuration, log catalogue and the architecture files of `config`, `context`, `flow` and `checks` updated; any open choice recorded as an ADR.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

`ariane docs-review` (slice 6); the reviewer's item-by-item answer (#33).

## Related

ADR 0022, ADR 0023, spec C25, C26, C9.
