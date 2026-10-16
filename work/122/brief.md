# Product brief: Architecture levels 1-2 and one sequence per command, checked against the imports (C25)

- Source: issue #122 (https://github.com/plaplanche/ariane/issues/122)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

A read-only review of `docs/architecture/` against the code after slice 4 found the levels 1 and 2 and the sequences of level 3 out of date: they show nothing of slice 4 (shadow mode, `metrics.json`, `ariane report`, `ariane judge`), and the `start` sequence predates the split of the flow into `replay` and `review_session` (ADR 0034). These diagrams stay hand-written (the owner's decision, recorded in ADR 0039 with the generated import graph of #120), and a test checks that every call they draw between modules is a real import. Spec: C25, C19, C23; ADR 0022, ADR 0030, ADR 0034, ADR 0036, ADR 0037, ADR 0038.

## Current state

- `docs/architecture/1-context.md`: the user sends only `ariane start n` and `ariane verify branch`; nothing about `ariane start --shadow n` (never pushes nor writes to the tracker), `ariane report [--since]` (reads pull request states from the tracker for human time, `github.pull_request_state`), `ariane judge` or `ariane status`. Line 24, "Only `ariane start` pushes", does not exclude `--shadow`.
- `docs/architecture/2-containers.md`: no shadow clone store `<repo>.ariane/shadow/<n>/` (a separate clone with its origin removed, `shadow.py`); the ticket folder edge reads "writes brief, journal, report, status" (no `metrics.json`, no `review-<n>.md`); the verify records omit `metrics.json`; no arrow for `report` reading `work/*/metrics.json`, `work/verify/**/metrics.json` and the shadow clones, nor for `judge` writing its verdict into a shadow `metrics.json`.
- `docs/architecture/3-components.md`: two sequences, `ariane start <n>` and `ariane verify <branch>`. The `start` sequence draws the replay and the review as direct calls from `flow` to `checks` and `runtime` (they now go through `replay` and `review_session`) and never shows `metrics` (rewritten after every step). The `verify` sequence omits `metrics.json` from what it commits. There is no sequence for `start --shadow`, `report` or `judge`.
- Since #120, the import graph is computed by `scripts/generate_docs.py` (a function returning the edges `a -> b`, type-only edges marked).

## Decided spec

- **Level 1.** The user sends `ariane start [--shadow] n`, `ariane verify branch`, `ariane report [--since]`, `ariane judge n accept|reject --minutes N` and `ariane status n`. Ariane reads pull request states from GitHub for `report`. The note below says that `--shadow` and `verify` never push, and that `start --shadow` reads the issue only.
- **Level 2.** Add the shadow clone store and its records; the ticket folder holds `brief.md`, `journal.md`, `checks.md`, `review-<n>.md`, `status.md` and `metrics.json`; the verify records include `metrics.json`; `report` reads the metrics of the checkout, of the verify records and of the shadow clones, and pull request states from GitHub; `judge` writes into the shadow `metrics.json`.
- **Level 3 sequences**, one per command, under the generated dependency diagram:
  - `ariane start <n>`: as today, with the replay and review drawn through `replay` and `review_session`, and `metrics` written after each step.
  - `ariane start --shadow <n>`: `cli` to `shadow`, the separate clone, the same implementer, replay and review steps, then a stop before push, pull request and statuses; records in the clone.
  - `ariane verify <branch>`: as today, through `review_session`, committing `metrics.json` too.
  - `ariane report [--since]`: `cli` to `report`, reading metrics through `metrics` and `shadow`, pull request states through the tracker, lines and totals from `measures`.
  - `ariane judge`: `cli` to `shadow`, which writes the verdict and minutes.
- **Check.** A test reads every `sequenceDiagram` under `docs/architecture/`. A participant whose label starts with a module name of `src/ariane/` (`participant F as flow`, `participant R as runtime (claude_code or opencode)`) is that module; actors and other participants are ignored. Every solid call arrow `A->>B` between two different module participants must be an edge `A -> B` of the computed import graph (a type-only edge counts); return arrows (`-->>`) and self-calls are not checked. The test names the file, the arrow and the missing import.

## Release note

Docs: the architecture's context, container and sequence diagrams cover shadow mode, metrics, `ariane report` and `ariane judge`, and a test keeps the sequences true to the code's imports.

## Acceptance criteria

- A test named `test_c25_sequences_*` shows, on a sequence written in `tmp_path`, that an arrow between two modules without an import is reported with its file and arrow, that a return arrow, a self-call and an arrow to an actor are not checked, and that on the repository itself every sequence under `docs/architecture/` passes.
- `3-components.md` holds one sequence for each of `start`, `start --shadow`, `verify`, `report` and `judge`.
- All checks in CLAUDE.md pass, including `uv run python scripts/generate_docs.py --check`.

## Acceptance checklist

- [ ] `uv run pytest -k "c25_sequences"` runs at least 2 tests and they pass.
- [ ] `grep -c sequenceDiagram docs/architecture/3-components.md` prints 5.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `1-context.md`, `2-containers.md` and the sequences of `3-components.md` updated; `docs/architecture/README.md` says the sequences are hand-written and checked against the imports; ADR 0039 amended with this check.

## Out of scope

- The generated blocks (#120) and the module files (later tickets).
- Any change to `src/ariane/`.

## Related

ADR 0022, ADR 0039, spec C25, C19.
