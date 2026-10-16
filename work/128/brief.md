# Product brief: Module files to the template: runtimes and measurement modules; check every module (C25)

- Source: issue #128 (https://github.com/plaplanche/ariane/issues/128)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

#124 set the template of a module file and its test (`tests/test_docs_module_template.py`, list `MIGRATED`); #126 applied it to the modules of a ticket's flow. This last of three tickets applies it to the remaining modules and makes the test cover every module. Spec: C25, C19; ADR 0022, ADR 0039.

## Current state

- `MIGRATED` lists 20 modules. `docs/architecture/modules/` for `attempts`, `claude_code`, `measures`, `metrics`, `opencode`, `report`, `runtime` and `shadow` still have the old shape.
- Known errors in them: `measures.md` documents `shadow_lines(shadows)`, the code is `shadow_lines(shadows, recent)`; `report.md` describes `build` as two functions, the code has one `build(root, since, tracker=None)`. Public names named in no module file: `measures.moment`, `measures.clock`, `measures.judgement`, `measures.attempts`, `measures.waiting`, `metrics.step`, `opencode.agent_name`.

## Decided spec

- The 8 module files above follow the template of #124 exactly, with signatures as in the code.
- The test no longer uses a list: it checks every module of `src/ariane/` (except `__init__`). `MIGRATED` is removed.
- `docs/architecture/README.md` says the template is checked on every module.

## Release note

Docs: every module file of Ariane shows a workflow and a code view, and a test keeps every module's public API true to the code.

## Acceptance criteria

- `uv run pytest -k "c25_module_template"` passes and covers all 28 modules; adding a module without a file following the template fails it (shown by the existing test in `tmp_path`, adapted if it relied on `MIGRATED`).
- All checks in CLAUDE.md pass, including `uv run python scripts/generate_docs.py --check`.

## Acceptance checklist

- [ ] `uv run pytest -k "c25_module_template"` passes on every module.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): the 8 module files rewritten to the template; `docs/architecture/README.md` updated.

## Out of scope

- Any change to `src/ariane/`.

## Related

#124, #126, ADR 0022, ADR 0039, spec C25.
