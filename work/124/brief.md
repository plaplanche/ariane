# Product brief: Module files: template with public API, workflow and code view, checked; entry, configuration and tracker modules (C25)

- Source: issue #124 (https://github.com/plaplanche/ariane/issues/124)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

A read-only review of `docs/architecture/modules/` after slice 4 found that no module file has a workflow diagram or a code view (C4 level 4), that about thirty public functions and classes are named in no module file, and that two signatures are wrong (`measures.shadow_lines(shadows)` is `shadow_lines(shadows, recent)` in the code; `report.md` describes `build` as two functions). The owner asked for, in each module file, a Mermaid workflow diagram of what the module does and a code view, kept true to the code. This is the first of three tickets: it sets the template and its test, and applies it to the entry, configuration and tracker modules. Spec: C25; ADR 0022, ADR 0039.

## Current state

- Every `docs/architecture/modules/<m>.md` has: a title, a purpose paragraph, `## Main types and functions` (bullets), `## Collaborations` (a block generated since #120), an optional `## Reference`, and `## Serves`.
- `tests/test_docs_architecture.py` checks that each module has a file and each file a Mermaid block; nothing compares the names in a module file with the code.
- ADR 0022 rules out Mermaid's experimental C4 syntax; `flowchart` and `classDiagram` are not C4 syntax.
- Public names named in no module file, among the modules of this ticket: `process.decode`, `ticket.now`; the others are listed by the test this ticket adds.

## Decided spec

- **Template** of a module file, sections in this order:
  1. `# Module \`ariane.<m>\`` and a purpose paragraph (what it is for, which command or capability it serves).
  2. `## Public API`: a table `| Name | Kind | What it does |`, one row per public name of the module: every top-level function, class and constant defined in the module (not imported) whose name does not start with `_`. Kind is `function`, `class`, `dataclass`, `protocol`, `exception` or `constant`. Signatures in the Name column as in the code (`build(root, since, tracker=None)`).
  3. `## Behaviour and errors`: files read and written with their paths, errors raised and when (bullets; what used to be in the purpose paragraph or the bullets of `## Main types and functions`).
  4. `## Workflow`: a Mermaid `flowchart TD` of the module's main function or functions: steps, decisions, the errors it raises and what it returns. A module with no behaviour of its own (only types or constants) says so in one line instead of a diagram.
  5. `## Code view (C4 level 4)`: a Mermaid `classDiagram` of the module's public classes (fields and methods) and functions (as `<<function>>` classes), and their links to the types of other modules they take or return.
  6. `## Collaborations`: the generated block, unchanged.
  7. `## Reference` when the module has one, and `## Serves` (C numbers then ADRs, both ascending).
- **Check.** A test lists the modules migrated to the template (this ticket: `__main__`, `cli`, `config`, `config_schema`, `context`, `github`, `logs`, `process`, `redact`, `ticket`, `tracker`). For each, it reads the module with `ast` and fails when a public name is missing from the `## Public API` table or the table names something the module does not define, when a section is missing or out of order, or when `## Workflow` or `## Code view (C4 level 4)` holds no Mermaid block (except the one-line case above for `## Workflow`). The test names the file and the name or section. Later tickets add the other modules to the list; the last one replaces the list by every module.
- `docs/architecture/README.md` describes the template, which sections are generated (collaborations) and which are checked (public API, section order).

## Release note

Docs: the module files of the entry, configuration and tracker modules show what each module does as a workflow and a code view, and a test keeps their public API true to the code.

## Acceptance criteria

- A test named `test_c25_module_template_*` shows, on a module and a module file written in `tmp_path`, that a missing public name, a name the module does not define, a missing or misplaced section and a section without its diagram are each reported with the file and the name or section; and that on the repository itself every migrated module file passes.
- The 11 module files of this ticket follow the template, with correct signatures.
- All checks in CLAUDE.md pass, including `uv run python scripts/generate_docs.py --check`.

## Acceptance checklist

- [ ] `uv run pytest -k "c25_module_template"` runs at least 2 tests and they pass.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): the 11 module files rewritten to the template; `docs/architecture/README.md` describes the template; ADR 0039 amended with the template and its check.

## Out of scope

- The other 17 module files (next two tickets).
- The levels 1 to 3 (#122) and the generated blocks (#120).
- Any change to `src/ariane/`.

## Related

ADR 0022, ADR 0039, #120, #122, spec C25.
