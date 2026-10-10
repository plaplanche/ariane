# Product brief: Document Ariane's architecture with Mermaid, from the landscape to each module (ADR 0022)

- Source: issue #59 (https://github.com/plaplanche/ariane/issues/59)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Spec, non-functional requirement "Documentation of Ariane", and ADR 0022: `docs/architecture/` explains how Ariane works with Mermaid diagrams at every C4 level, one file per module at level 4, and a check fails when a module has no file. Nothing exists yet. This ticket creates the baseline for the code as it is; later tickets keep it up to date (CLAUDE.md rule 11).

## Current state

- `src/ariane/` has 15 modules: `__main__`, `checks`, `claude_code`, `cli`, `config`, `context`, `delivery`, `flow`, `git`, `github`, `process`, `redact`, `runtime`, `ticket`, `tracker` (plus `__init__`).
- `docs/` holds `spec.md`, `adr/`, `ariane.example.toml`, `learnings.md`; `README.md` links the spec and the ADRs.

## Decided spec

- `docs/architecture/README.md`: what each level shows and an index of the files.
- `0-landscape.md`: the owner, the second user, GitHub (issues, pull requests, statuses, Actions), the agent runtimes (Claude Code, opencode to come), the model vendors, the cloud sandbox.
- `1-context.md`: Ariane as one system and what it exchanges with each of them (read an issue, push one branch, open a pull request, publish statuses, start agent sessions).
- `2-containers.md`: the `ariane` command, the repository and its ticket working trees and replay trees (`<repo>.ariane/`), the ticket folder `work/<n>/`, the agent session processes, the CI workflows (`ci.yml`, `check-statuses.yml`).
- `3-components.md`: the modules and their dependencies (a Mermaid flowchart), and a sequence diagram of `ariane start <n>` from reading the issue to the pull request (setup, session, guard checks, clean replay, one push, statuses).
- `modules/<module>.md` for every module under `src/ariane/` except `__init__`: its role in two or three sentences, its main types and functions, what it calls and what calls it (a small Mermaid diagram), and the capabilities (C-numbers) and ADRs it serves.
- Diagrams are Mermaid flowcharts or sequence diagrams (ADR 0022), not the experimental C4 syntax.
- A test fails when a module under `src/ariane/` (other than `__init__`) has no `docs/architecture/modules/<module>.md`, or a file there names a module that does not exist.
- `README.md` links `docs/architecture/README.md`.

## Release note

Docs: architecture documentation with Mermaid diagrams, from the system landscape to each module.

## Acceptance criteria

- Tests named `test_docs_architecture_*` show the module-to-file check passing now, and failing for a missing file and for a file without a module (on a temporary copy).
- Every file in `docs/architecture/` holds at least one Mermaid diagram.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k docs_architecture` runs at least 3 tests and they pass.
- [ ] Definition of done: `docs/architecture/` covers levels 0 to 3 and every module; `README.md` links it.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Generated references and the log catalogue (separate issues).

## Related

ADR 0022, spec "Documentation of Ariane", CLAUDE.md rule 11.
