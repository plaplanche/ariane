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
- The sequence diagrams and the module texts stay hand-written.

## Consequences
An import added without regenerating fails `generate_docs.py --check` and its test. Hand-written
prose cannot describe an edge the code does not have inside the blocks.

## Alternatives considered
- Generating whole files: loses the hand-written prose around the diagrams.
- A test only comparing hand-written diagrams with the code: still needs a manual fix on each
  failure, and the generator already exists.
