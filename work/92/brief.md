# Product brief: Close slice 3: README status, ADR 0029 on --dir/PWD, no opencode rule for the implementer (C5, C25)

- Source: issue #92 (https://github.com/plaplanche/ariane/issues/92)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Slice 3's gate is met: #86 was reviewed on opencode (`work/verify/ariane/86/review.md`, verdict go), a branch finished by hand was verified with `ariane verify`, the documentation checks pass and the reviewer answers the definition of done item by item. This ticket closes the slice: the README status, and the minor findings left by the reviews of #86 (PR #89) and #90 (PR #91). Spec: C5, C10, C25, roadmap.

## Current state

- `README.md:7`: the status line says "slice 3 (review, vendor-neutral): …" and "Measurement and shadow mode (slice 4) and approvals (slice 5) come next".
- `docs/adr/0029-opencode-reviewer.md`: the amendment "(slice 3 fix round)" does not say that opencode takes its directory from `PWD`, nor that Ariane passes `--dir` and sets `PWD` to the tree under review (#90).
- `src/ariane/config_schema.py:35`: `_AGENT` carries an `if`/`then` (`runtime` = `opencode` requires `max_tokens`); the implementer (`config_schema.py:85`) inherits it although its `runtime` can only be `claude-code`, so `docs/reference/ariane.toml.schema.json` holds a dead `if`/`then` under `agents.implementer`.
- `tests/test_docs_reference.py:65`: the test's schema helper handles `number` but not `integer`, so `max_tokens` (`"type": "integer"`) is not type-checked by the tests; no test covers an implementer without `max_tokens`.

## Decided spec

- `README.md`: the status line says slice 3 is done (same description of what Ariane does) and that slice 4, measurement and shadow mode, is next; approvals (slice 5) after it.
- `docs/adr/0029-opencode-reviewer.md`: a new amendment "(slice 3 gate)": opencode takes its directory from `PWD`, not from the process's working directory; Ariane passes `--dir` with the absolute path of the tree under review and sets `PWD` to it (#90), so the reviewer cannot read the directory Ariane was started from.
- `src/ariane/config_schema.py`: the implementer's schema has no `if`/`then` (only the reviewer, which may run on opencode, keeps it); `docs/reference/ariane.toml.schema.json` is regenerated.
- `tests/test_docs_reference.py`: the helper checks `integer` (an `int` that is not a `bool`, with `exclusiveMinimum`).

## Release note

Docs: slice 3 is done; the configuration schema no longer carries a dead rule for the implementer.

## Acceptance criteria

- A test named `test_c5_schema_implementer_*` shows that an implementer without `max_tokens` validates against the generated schema and that the implementer's schema holds no `if`/`then`.
- A test named `test_c5_schema_integer_*` shows that the helper refuses `max_tokens = 1.5` and `max_tokens = 0` and accepts `max_tokens = 10`.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k "c5_schema_implementer or c5_schema_integer"` runs at least 2 tests and they pass.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `README.md` status updated; ADR 0029 amended; `docs/reference/ariane.toml.schema.json` regenerated; `docs/architecture/modules/config_schema.md` updated if it describes the `if`/`then`.

## Out of scope

- Slice 4's work (C19, shadow mode, `ariane report`).
- #40 (statuses from base-branch code), which touches a workflow file.

## Related

#86, #89, #90, #91, ADR 0029, spec C5, C10, C25.
