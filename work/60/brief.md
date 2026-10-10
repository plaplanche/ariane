# Product brief: Generate the command-line reference and the configuration schema (C25, ADR 0022)

- Source: issue #60 (https://github.com/plaplanche/ariane/issues/60)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

ADR 0022: the command-line reference and the JSON Schemas of the configuration and of agents' structured answers are generated from the code, committed under `docs/reference/`, and a test fails when a committed file differs from what the code produces. There is no HTTP API, so no OpenAPI description.

## Current state

- `src/ariane/cli.py` `_parser()` builds the `argparse` parser (`start`, `status`, `--version`).
- `src/ariane/config.py` `parse()` validates `ariane.toml` by hand (tables `project`, `tracker`, `agents.implementer`, `checks`); no schema file exists.
- No agent gives a structured answer yet (the reviewer's comes with #33).

## Decided spec

- `scripts/generate_docs.py` writes `docs/reference/cli.md` (each command, its arguments and help, from `_parser()`) and `docs/reference/ariane.toml.schema.json` (JSON Schema draft 2020-12 of the configuration, built from a description kept next to `config.parse`, so the two cannot drift: a test loads `ariane.toml` and `docs/ariane.example.toml` and validates them against the schema with a small validator written for the subset used, no new dependency). `--check` exits 1 and names the files that differ.
- A test runs `generate_docs.py --check`, so CI needs no new step.
- The script is written so that #33 adds the reviewer's answer schema and the log-catalogue issue adds `docs/logs.md` to the same generator.
- `docs/architecture/modules/cli.md` and `config.md` link the generated files (if they exist when this ticket runs; otherwise the README does).

## Release note

Docs: a generated command-line reference and a JSON Schema of `ariane.toml`.

## Acceptance criteria

- Tests named `test_docs_reference_*` show: the committed files match the generator; a changed help text makes `--check` fail; both `ariane.toml` files validate against the schema; an unknown key and a wrong type are rejected by the schema as by `config.parse`.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k docs_reference` runs at least 4 tests and they pass.
- [ ] Definition of done: `docs/reference/` is generated, never edited by hand; `README.md` links it.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

The reviewer's answer schema (#33), the log catalogue, OpenAPI (no HTTP API).

## Related

ADR 0022, spec C25.
