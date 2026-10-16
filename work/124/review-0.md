# Review 0

- Reviewed commit: `76d769364b2d85d0b8397ddc46dd8f3dc968fb6b`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/architecture/modules/logs.md:47`) Workflow reuses node X for two different errors

  Line 41 declares `X[raise ValueError]` and line 47 declares `X[raise KeyError]`. In Mermaid this is the same node, so the last label wins. The rendered diagram then shows the unknown-level path of `parse_level` raising KeyError, which is wrong (`parse_level` raises ValueError). Use two different node ids.

- **minor** (`docs/architecture/modules/logs.md:70`) Code view gives FUNCTIONAL_TYPES/TECHNICAL_TYPES the wrong type

  In `src/ariane/logs.py` both are `dict[str, LogType]` built by `_declare` and indexed by id (`FUNCTIONAL_TYPES[type_id]`), but the class diagram says `tuple~LogType~`. Also, `configure` clears the registered secrets (`_redactor.secrets.clear()`), so `add_secrets` only takes effect after `configure`. Behaviour and errors does not say this.

- **minor** (`docs/architecture/modules/config.md:97`) DoneItem.label is a property, not a method

  `config.py:62` defines `label` as a `@property`, and `context.py` uses `item.label` without calling it. The Public API row (line 15) and the code view both write `label()`, which is the kind of signature drift this ticket is meant to remove.

- **minor** (`docs/architecture/modules/cli.md:28`) cli workflow leaves out two early exits

  `main` returns EXIT_USAGE when no command is given (it prints help) and when `--log-level`/`ARIANE_LOG_LEVEL` is invalid, before it looks for the repository root. The flowchart only shows a generic 'usage error' and the 'not a git repository' exit. It also leaves out the per-command log file that `configure` sets up. This is acceptable as a simplification, but the diagram is not complete.

- **minor** (`tests/test_docs_module_template.py:66`) The check compares names only, not signatures or the title line

  `documented_names` takes only the leading identifier, so a wrong argument list in the Name column (the `shadow_lines(shadows)` defect that motivated the ticket) still passes. The `# Module` title (template section 1) is not checked either. The decided spec only asks for names and sections, and ADR 0039 records this limit, so this is not blocking. Comparing signatures with `ast` arguments would be a cheap later improvement.

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

  tests/test_docs_module_template.py adds 8 `test_c25_module_template_*` tests. They cover these cases on tmp_path: a conforming file, a missing public name, a name the module does not define, a missing section, a misplaced section, a missing Code view diagram, a missing Workflow diagram, and the allowed one-line workflow. The `migrated_module_files_pass` test would fail on the base branch, because the old files use `## Main types and functions` and leave out names such as `process.decode` and `ticket.now`. Every expected message names the file and the name or section.

- met: The documentation the change affects is updated (C25).

  All 11 module files (__main__, cli, config, config_schema, context, github, logs, process, redact, ticket, tracker) are rewritten to the template. docs/architecture/README.md gains a 'Module file template' section that names the generated and checked parts. ADR 0039 is amended. I checked the signatures against src/ariane and they match, apart from the minor `label()` and dict-vs-tuple inaccuracies reported. No src/ change, so no generated reference needs regenerating, and the docs: references check is green.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0039-generated-architecture-blocks.md gains 'Amendment: module file template (#124)'. It records the template, the check file, the growing MIGRATED list, and the open choice to compare names and sections rather than diagram content.

## Proposed learnings (not decided)

- In hand-written Mermaid flowcharts, reusing a node id (e.g. `X`) with a different label silently merges the nodes; use a distinct id for each error.
- A docs-vs-code check that compares only names will not catch signature drift; consider comparing parameter names from `ast` arguments when the Name column has a signature.
- Python `@property` members should be documented without `()` in module files and class diagrams.
