# Product brief: Generate the module dependency graphs of the architecture docs from the code (C25)

- Source: issue #120 (https://github.com/plaplanche/ariane/issues/120)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The architecture documentation (ADR 0022) is written by hand, and a read-only review of `docs/architecture/` against the code after slice 4 found it out of date: the dependency graph of `3-components.md` misses 7 real imports and keeps 1 stale one, 20 of the 28 module files have a "Collaborations" diagram that misses real edges, and `docs/architecture/README.md` does not list 7 of the 28 modules. No test compares any of these with the code. The owner decided that the module dependency graph is generated from the code and checked, like the references. Spec: C25; ADR 0022, ADR 0023.

## Current state

- `docs/architecture/3-components.md:8-116`: a hand-written `flowchart TD` of module imports. Missing: `shadow -> checks`, `shadow -> config`, `shadow -> metrics`, `shadow -> review`, `shadow -> runtime`, `shadow -> ticket`, `replay -> flow` (under `TYPE_CHECKING` only). Stale: `replay --> metrics`. Duplicate: `git --> process` (lines 81 and 92).
- `docs/architecture/modules/<m>.md`: each has a `## Collaborations` section with a hand-written `flowchart LR` of the modules it imports and the modules that import it. Incomplete in `checks`, `config`, `delivery`, `flow`, `git`, `metrics` (stale `replay --> metrics`), `replay`, `review`, `runtime`, `shadow`, `stop`, `ticket`, `tracker` and others.
- `docs/architecture/README.md:23-45`: a hand-written "Modules" list without `attempts`, `measures`, `metrics`, `replay`, `report`, `shadow`, `stop`.
- `scripts/generate_docs.py` generates `docs/logs.md` and `docs/reference/*` from the code; `--check` exits 1 and names the files that differ; `tests/test_docs_reference.py` runs it. It writes whole files only.
- `tests/test_docs_architecture.py` checks only that each module has a file and each file has a Mermaid block.

## Decided spec

- **Import graph from the code.** A function in `scripts/generate_docs.py` reads every `src/ariane/*.py` with `ast` and returns the edges `a -> b` where module `a` imports module `b` of the package: `from ariane import b`, `from ariane.b import ...`, `import ariane.b`, relative imports, at any depth (inside functions too). An import under `if TYPE_CHECKING:` is a type-only edge. `ariane/__init__` is not a node. Edges are sorted and unique.
- **Generated blocks inside hand-written files.** A generated block is delimited by `<!-- generated: <name> -->` and `<!-- end generated -->`; `generate_docs.py` rewrites only what lies between the markers and leaves the rest of the file untouched. `--check` reports a file whose block differs, as it does for whole files. A file that lacks its markers is an error naming the file.
- **Blocks.**
  - `3-components.md`: the dependency diagram becomes the generated block `dependencies`: a `flowchart TD` with every edge, `a --> b`, and `a -.-> b` for a type-only edge.
  - `modules/<m>.md`: the diagram of `## Collaborations` becomes the generated block `collaborations`: a `flowchart LR` with the edges where `m` is either end (same arrow styles). The sentence above it says: "Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only."
  - `docs/architecture/README.md`: the module list becomes the generated block `modules`: one line per module, in alphabetical order, `` - [`m`](modules/m.md) ``.
- **ADR.** A new ADR records the choice: the import graph and module list are generated from the code inside marked blocks; the sequences and the module texts stay hand-written.
- The prose of `3-components.md` and of each module file outside the blocks is unchanged by this ticket, except the sentence above each collaborations diagram.

## Release note

Docs: the module dependency graphs of the architecture documentation are generated from the code and checked, so they can no longer drift from it.

## Acceptance criteria

- A test named `test_c25_import_graph_*` builds the graph of a small package written in `tmp_path` and shows that a `from x import y`, an import inside a function, a relative import and an import under `if TYPE_CHECKING:` (type-only) are found, and that an import of a module outside the package is not.
- A test named `test_c25_generated_block_*` shows that rewriting a block leaves the text before and after the markers byte-identical, that `--check` names a file whose block differs, and that a file without its markers is reported.
- A test named `test_c25_architecture_graph_*` shows that, on the repository itself, the edges drawn in `3-components.md` and in every `modules/<m>.md` equal the computed graph (so it fails if an import is added without regenerating), and that the README lists every module.
- All checks in CLAUDE.md pass, including `uv run python scripts/generate_docs.py --check`.

## Acceptance checklist

- [ ] `uv run pytest -k "c25_import_graph or c25_generated_block or c25_architecture_graph"` runs at least 3 tests and they pass.
- [ ] `uv run python scripts/generate_docs.py --check` exits 0 on the branch.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `3-components.md`, the 28 `modules/<m>.md` and `docs/architecture/README.md` regenerated; `docs/architecture/README.md` says which parts are generated and how to regenerate them; the new ADR; `docs/architecture/modules/` unchanged elsewhere.

## Out of scope

- The levels 1 and 2 and the sequence diagrams (next ticket).
- Workflow diagrams, code views and public API tables per module (later tickets).
- Any change to `src/ariane/`.

## Related

ADR 0022, ADR 0023, spec C25.
