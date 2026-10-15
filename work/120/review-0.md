# Review 0

- Reviewed commit: `74355fbd55bd58b67e09e2d6f2ba0ee18f647e45`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/architecture/3-components.md:5`) Prose outside the block changed beyond what the ticket allows

  The ticket says the prose of 3-components.md outside the blocks stays unchanged except the sentence above each collaborations diagram, and that sentence belongs to the module files. The change rewrites the intro sentence of 3-components.md anyway ("An arrow goes from a module to a module it imports" becomes the importing/imported wording plus the note on dashed arrows). The new wording is accurate and matches the dashed arrows, so this is harmless, but it goes past the ticket's scope.

- **minor** (`scripts/generate_docs.py:160`) Undocumented rendering of a module with no edges

  render_collaborations falls back to a single bare node (`  m`) when a module has no edges. The spec does not cover this case. No module hits it today, but it is a small open choice that neither ADR 0039 nor a test records.

- **minor** (`scripts/generate_docs.py:104`) Relative imports of level 2 or more and `if not TYPE_CHECKING` are silently ignored

  `_imported` only handles `node.level == 1`, and `_is_type_checking` only matches a bare `TYPE_CHECKING` test. In a flat package a level-2 import leaves the package, so this is correct today. If subpackages appear, edges would be dropped without any error.

- **minor** (`tests/test_docs_graph.py:103`) README test checks only inclusion, not equality

  test_c25_architecture_graph_readme_lists_every_module checks that each module line is present. It does not check that the generated block lists only real modules, in alphabetical order. The generate_docs --check test covers that indirectly, so the acceptance criterion is met.

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

  tests/test_docs_graph.py adds test_c25_import_graph_* (from-import, nested import, relative imports, TYPE_CHECKING type-only edge, stdlib and third-party imports excluded, __init__ not a node), test_c25_generated_block_* (before and after text byte-identical, including CRLF; --check names a differing file and a missing marker) and test_c25_architecture_graph_* (repository docs equal the computed graph; the README lists every module). All of them call import_graph, replace_block or main's block handling, which do not exist on the base, and the architecture graph test would fail against the old hand-written diagrams (stale replay --> metrics, missing shadow edges). tests/test_docs_reference.py was adapted for the new architecture inputs.

- met: The documentation the change affects is updated (C25).

  3-components.md has the generated `dependencies` block. All 28 modules/<m>.md have a `collaborations` block with the required sentence (measures.md gains it). docs/architecture/README.md has the `modules` block with the 7 missing modules and a paragraph saying which parts are generated and how to regenerate and check them. The module docstring of scripts/generate_docs.py is updated. No other prose in modules/ changes.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0039-generated-architecture-blocks.md records the generated marked blocks, the import-graph rules, that sequences and texts stay hand-written, and the alternatives considered. Only a trivial rendering detail (a module with no edges drawn as a bare node) is not recorded; see the minor finding.

## Proposed learnings (not decided)

- When a generator starts reading extra inputs (src/, docs/architecture/), tests that run it on an empty tmp_path root have to copy those inputs; check that existing generator tests were adapted.
- For graph-from-code tickets, check the type-only merge rule: an edge imported both at runtime and under TYPE_CHECKING must come out as a runtime edge.
