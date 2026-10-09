# Product brief: Count cached input tokens in session usage (C5)

- Status: draft
- Approved: not yet
- Source: issue #26 (https://github.com/plaplanche/ariane/issues/26)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Journals show "8 in" input tokens for sessions that read much of the repository: the input count leaves out cached tokens, which Claude Code reports separately (`cache_creation_input_tokens`, `cache_read_input_tokens`). Spec C5: tokens include cache reads and writes when the runtime reports them separately (ADR 0015).

## Current state

- `src/ariane/claude_code.py:106` reads only `usage.input_tokens`.
- `src/ariane/runtime.py:33` `SessionResult` has `input_tokens` and `output_tokens` only.
- `src/ariane/flow.py:207` journals `"{input} in, {output} out"`.

## Decided spec

- `SessionResult` gains `cache_read_tokens` and `cache_write_tokens` (`int | None`, as reported).
- The Claude Code adapter fills them from `cache_read_input_tokens` and `cache_creation_input_tokens`.
- The journal line becomes `tokens <input> in, <cache read> cache read, <cache write> cache write, <output> out`, with `not reported` for a missing value.
- The recorded fixtures under `tests/fixtures/` gain the two fields as Claude Code 2.1.292 reports them.

## Release note

Fixed: the journal counts cached input tokens.

## Acceptance criteria

- Tests named `test_c5_tokens_cache_*` show the parsed values from a fixture with cache fields, `None` when the fields are absent, and the journal line.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c5_tokens_cache` runs at least 2 tests and they pass.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Budget enforcement from streamed usage (a later issue), metrics files (C19).

## Related

ADR 0015, spec C5.
