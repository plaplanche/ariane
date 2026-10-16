# 0039. Generated blocks in the architecture documentation

- Status: accepted
- Date: 2026-10-15
- Capabilities: C25

## Context
ADR 0022 and ADR 0023 ask for architecture documentation that stays true to the code. The
hand-written dependency graphs drifted: missing and stale edges, and modules absent from the list.

## Decision
- `scripts/generate_docs.py` reads every `src/ariane/*.py` with `ast` and computes the import graph
  between the modules of the package (absolute, relative, nested imports; an import under
  `if TYPE_CHECKING:` is a type-only edge, drawn dashed).
- The import graph and the module list are generated inside blocks marked
  `<!-- generated: <name> -->` and `<!-- end generated -->`: `dependencies` in `3-components.md`,
  `collaborations` in each module file, `modules` in `docs/architecture/README.md`. The generator
  rewrites only what lies between the markers; a file without its markers is an error.
- The sequence diagrams and the module texts stay hand-written. A test reads every `sequenceDiagram`
  under `docs/architecture/`: a participant whose label starts with a module name is that module
  (actors and other participants are ignored), and every solid arrow `A->>B` between two different
  modules must be an edge `A -> B` of the computed graph (a type-only edge counts). Return arrows
  and self-calls are not checked. Any other arrow kind (open `->`, async `-)` and `--)`, cross `-x`
  and `--x`) fails the check, and so does an arrow written with spaces around it (`A ->> B:`), so
  that no call can escape the import check; the spec leaves these kinds open and this is the
  simplest rule. A participant used by an arrow without a declaration is an error too.

## Amendment: module file template (#124)
Each module file follows one template, sections in this order: title and purpose, `## Public API`
(a table `Name | Kind | What it does`, one row per public name: every top-level function, class and
constant defined in the module, not imported, without a leading `_`), `## Behaviour and errors`,
`## Workflow` (a Mermaid `flowchart TD`, or one line for a module with no behaviour of its own),
`## Code view (C4 level 4)` (a Mermaid `classDiagram`), `## Collaborations` (generated),
`## Reference` (optional) and `## Serves`. `flowchart` and `classDiagram` are not C4 syntax, so
ADR 0022 still holds. `tests/test_docs_module_template.py` reads each migrated module with `ast`
and fails, naming the file and the name or section, on a public name missing from the table, a
name the module does not define, a missing or misplaced section, or a diagram-less Workflow or
Code view. The list of migrated modules grows ticket by ticket until it is every module. The
simplest check that meets this: it compares names and sections, not the content of the diagrams.

## Consequences
An import added without regenerating fails `generate_docs.py --check` and its test. Hand-written
prose cannot describe an edge the code does not have inside the blocks.

## Alternatives considered
- Generating whole files: loses the hand-written prose around the diagrams.
- A test only comparing hand-written diagrams with the code: still needs a manual fix on each
  failure, and the generator already exists.
