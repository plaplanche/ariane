# Review 0

- Reviewed commit: `cdc276417e25af3bf11cbd85d99de156151f0519`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/review.py:228`) Agent-controlled file names reach the reviewer prompt outside the untrusted block

  With `{stem}`, the untouched-document paths are built from names of files the agent created (for example `src/ariane/<anything>.py`). They go into the reviewer prompt before the `<untrusted-ticket>` block, under the label "a fact from Ariane". Git C-quotes newlines, so an injected name stays on one line, but it can still hold free text such as instructions or backticks. Escape these paths or put them inside the untrusted block.

- **minor** (`src/ariane/config.py:283`) `**/` does not match zero folders

  `_glob_regex("src/**/*.py")` becomes `src/.*/[^/]*\.py`, which does not match `src/a.py`. Most glob users expect `**/` to also match zero folders. ADR 0026 only says that `**` crosses segments. Either handle `**/` as `(.*/)?` or state this behaviour in the ADR.

- **minor** (`docs/architecture/modules/logs.md:1`) logs module touched but its module doc not updated

  The change edits `src/ariane/logs.py`. Ariane's own map sends that file to `docs/architecture/modules/logs.md`, which was not touched. The file is still accurate, because the catalogue `docs/logs.md` was regenerated, but the new check would flag it.

- **minor** (`src/ariane/config.py:274`) Generated check names are not checked against declared checks or the definition of done

  A declared check named `docs: x` would collide with a generated one. Also, `_definition_of_done` only checks `{check=...}` items against the declared checks, so a definition-of-done item `{ check = "docs: references" }` is refused even though that check runs.

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

  `tests/test_docs_upkeep.py` has 7 `test_c25_docs_*` functions, one of them parametrized with 5 cases. They cover: loading the table and refusing bad input naming the key (`generated[0].check`, `map[0].source`); `{stem}` expansion and globs staying in a folder; the prompt listing the map; an untouched document being journaled and given to the reviewer; a changed document not being flagged; `docs: refs` failing the replay and appearing in `checks.md`; and nothing changing without the table. Each test depends on new code (`Config.documentation`, `Documentation`, `_flag_untouched_docs`, `_all_checks`).

- met: The documentation the change affects is updated (C25).

  Updated: the schema (`docs/reference/ariane.toml.schema.json`, matching `SCHEMA`), `docs/ariane.example.toml`, the catalogue `docs/logs.md` (`ticket.docs.not_updated`), and the architecture files `config`, `context`, `flow`, `checks` and `review` under `docs/architecture/modules/`. Ariane's own `ariane.toml` declares the table as the ticket asks. `modules/logs.md` was not touched, but its content is still accurate (minor finding).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  `docs/adr/0026-documentation-upkeep.md` records: glob semantics, folder documents, the 15-minute timeout and unique names, the `work/` exclusion, and that untouched documents are not blocking.

## Proposed learnings (not decided)

- Anything built from agent-controlled data (file names, `{stem}` expansions) should stay inside the untrusted block or be escaped before it goes into a reviewer prompt as a fact from Ariane.
- When a source-to-docs map is added, check the change itself against that map: a touched module whose doc is unchanged is a quick self-test.
