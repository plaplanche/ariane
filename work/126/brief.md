# Product brief: Module files to the template: flow, replay, review and delivery modules (C25)

- Source: issue #126 (https://github.com/plaplanche/ariane/issues/126)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

#124 set the template of a module file (public API, behaviour and errors, workflow, code view at C4 level 4, generated collaborations) and the test that checks it, `tests/test_docs_module_template.py`, on 11 modules listed in `MIGRATED`. This second of three tickets applies the template to the modules of a ticket's flow. Spec: C25; ADR 0022, ADR 0039.

## Current state

- `tests/test_docs_module_template.py:12`: `MIGRATED` lists the 11 modules of #124.
- `docs/architecture/modules/` for `checks`, `delivery`, `flow`, `git`, `replay`, `review`, `review_session`, `stop` and `verify` still have the old shape (`## Main types and functions` bullets). Public names named in no module file, among them: `git.current_branch`, `git.diff`, `git.fetch`, `git.ignored`, `git.local_branch_exists`, `git.path_exists_on_branch`, `git.push_url`, `git.remote_refs`, `git.remotes`, `git.repo_root`, `git.show_on_branch`, `git.status`, `git.untracked`; `review.Review`, `review.Finding`, `review.DoneResult`, `review.Settled`, `review.findings_table`.

## Decided spec

- The 9 module files above follow the template of #124 exactly (sections, order, public API table matching the code, a workflow `flowchart TD` of the main function or functions, a `classDiagram` code view).
- `MIGRATED` gains these 9 modules.
- No change to the template or to the test's rules.

## Release note

Docs: the module files of a ticket's flow (flow, replay, review, delivery, git and their neighbours) show a workflow and a code view, checked against the code.

## Acceptance criteria

- `uv run pytest -k "c25_module_template"` passes with the 20 migrated modules, and fails if a public function is added to one of the 9 modules without its row (shown by the existing test on a module written in `tmp_path`).
- All checks in CLAUDE.md pass, including `uv run python scripts/generate_docs.py --check`.

## Acceptance checklist

- [ ] `uv run pytest -k "c25_module_template"` passes.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): the 9 module files rewritten to the template.

## Out of scope

- The 8 remaining modules (`attempts`, `claude_code`, `measures`, `metrics`, `opencode`, `report`, `runtime`, `shadow`: next ticket).
- Any change to `src/ariane/`.

## Related

#124, ADR 0022, ADR 0039, spec C25.
