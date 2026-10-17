# Review 0

- Reviewed commit: `d2cb38b3ef7ac37768c965ff8c9460fb4e591871`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/review.py:272`) The out-of-scope rule is always in the reviewer prompt, but the issue says it appears only when the section exists

  The decided spec says: "When the issue's Out of scope section is not empty, the prompt shows it again as its own untrusted block ... and the rules gain: ...". The acceptance criterion repeats it: the prompt holds "the out-of-scope block and the rule when the body has the section, and neither when it has none". In the change, the rule sits in the fixed Rules text (lines 272-274), so every reviewer prompt has it, including one for an issue with no Out of scope section. Only the block depends on the section. Fix: build the rule line inside the same `if out_of_scope` branch as `scope`.

- **blocking** (`tests/test_review.py:268`) The no-section test does not check that the rule is absent

  `test_c10_out_of_scope_prompt_without_section_has_neither_block` only asserts that `kind="out-of-scope"` is missing. It never asserts that the rule (for example "never blocking" or "Work listed under Out of scope") is missing. That is why the test passes even though the rule is always there, and why the "neither" part of the acceptance criterion is untested. The test name says "neither" but checks only one thing.

- **minor** (`docs/architecture/modules/ticket.md:27`) ticket.md: the Behaviour section and the code view do not include `section`

  The acceptance checklist asks for ticket.md's "public API row for `section`, behaviour". Only the API row was added. The Behaviour and errors list says nothing about `section` (for example that it stops at the next `## ` line, ignores `###` headings and never raises). The `ticket` function list in the classDiagram (lines 66-77) also leaves out `section(body, title) str`.

- **minor** (`src/ariane/ticket.py:29`) `section` treats a `## ` line inside a fenced code block as a heading

  An Out of scope section whose code block contains a line starting with `## ` (for example a Markdown sample) is cut short at that line. This is acceptable under the decided spec, which defines the section by level-2 headings. It is worth a test or a line in the docs.

- **minor** (`tests/test_review.py:257`) The `section` test does not cover a section that runs to the end of the body

  The spec says "up to the next level-2 heading or the end". Only the case that stops at a heading is tested. The case where the last section has no heading after it is not.

- **blocking** Definition of done not met: The change is covered by tests that fail without it.

  Five `test_c10_out_of_scope_*` tests exist (4 in tests/test_review.py, 1 in tests/test_context.py), and they would fail without the change. But the acceptance criterion "neither when it has none" is not tested: the no-section test checks only that the block is absent, not the rule. The implementation also does not meet that criterion (the rule is always present).

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  Updated: README review paragraph, review.md (behaviour paragraph and collaborations), context.md behaviour, ticket.md API row and collaborations, 3-components.md. Not updated: ticket.md's Behaviour and errors and its code-view diagram, which the issue's checklist names explicitly ("behaviour"). review.md and the README say the rule comes with the section, which matches the spec but not the code (the code always adds the rule).

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

- **not met**: The change is covered by tests that fail without it.

  Five `test_c10_out_of_scope_*` tests exist (4 in tests/test_review.py, 1 in tests/test_context.py), and they would fail without the change. But the acceptance criterion "neither when it has none" is not tested: the no-section test checks only that the block is absent, not the rule. The implementation also does not meet that criterion (the rule is always present).

- **not met**: The documentation the change affects is updated (C25).

  Updated: README review paragraph, review.md (behaviour paragraph and collaborations), context.md behaviour, ticket.md API row and collaborations, 3-components.md. Not updated: ticket.md's Behaviour and errors and its code-view diagram, which the issue's checklist names explicitly ("behaviour"). review.md and the README say the rule comes with the section, which matches the spec but not the code (the code always adds the rule).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The issue says "No ADR": `section`'s behaviour, the block kind and the rule texts are all decided in the issue, and the change makes no other open design choice.

## Proposed learnings (not decided)

- When an acceptance criterion says "X and Y when ..., neither when ...", the negative test must assert that both X and Y are absent, not only one of them.
- A conditional prompt rule (one that appears only when some issue data exists) must be built in the same branch as that data's block, not added to the fixed Rules text.
