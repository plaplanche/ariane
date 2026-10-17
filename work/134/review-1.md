# Review 1

- Reviewed commit: `5ca5841d27a308116ac74a6aa6346b20334d51f7`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`README.md:44`) README states as a guarantee what is only a prompt instruction

  The README says a finding about out-of-scope work "is never blocking". The spec says this is a framed opinion: `settle` is unchanged, so a reviewer that still marks such a finding blocking will produce a no-go. The module doc (review.md:32) states this limit correctly. The README could say "the reviewer is told that ..." so it does not promise something Ariane does not enforce. The sentence also leaves out that implementer and fix sessions get the matching rule. The ticket's checklist only asks for the review paragraph, so this is not blocking.

- **minor** (`src/ariane/ticket.py:30`) section() misses some level-2 heading forms

  Only lines starting with "## " count as headings. A bare "##", "##\t", "## Out of scope ##" (closing hashes) or a heading indented by 1–3 spaces is not seen. If one of these is the next heading, the section runs past it; if one is the Out of scope heading, the section is not found and the rule is silently dropped. The fenced-code limit is documented in ticket.md, but these cases are not. Issue bodies follow the C1 template, so the risk is low.

- **minor** (`tests/test_review.py:267`) Prompt test does not check the block's content or the full rule text

  `test_c10_out_of_scope_prompt_holds_the_block_and_the_rule` checks only `kind="out-of-scope"` and "never blocking". It does not check that "- later work" sits inside the block, or that the rule's "out of scope" title convention and "Doing out-of-scope work is a finding only when it breaks something" appear. A regression that empties the block or cuts the rule short would still pass.

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

  tests/test_review.py:254-283 has four `test_c10_out_of_scope_*` tests: `ticket.section` (case, stop at the next heading, `###` kept, missing section, fenced code), the reviewer prompt with and without the section, and escaping of a closing tag. tests/test_context.py has one more for the implementer and fix-round prompts. All of them fail on the base: `ticket.section` does not exist there, and neither rule text nor the block is in the prompts. `-k c10_out_of_scope` selects 5 tests (at least 4 were required), and the replayed tests pass.

- met: The documentation the change affects is updated (C25).

  Updated: docs/architecture/modules/ticket.md (API row for `section`, behaviour, class diagram, dependency graph), review.md (prompt behaviour, dependency graph), context.md (implementer rule), 3-components.md (review --> ticket edge) and README.md:44. The change affects no generated reference (cli, schemas), and the 'docs: references' check is green. One minor wording point on the README is noted in the findings.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket's decided spec settles every choice: the function signature, heading matching, the block kind, the exact rule texts, and no change to `settle`. It also says explicitly "No ADR". The one leftover detail, line-based parsing that treats a `## ` line inside fenced code as a heading, is a documented limit in ticket.md, not a design choice that needs an ADR.

## Proposed learnings (not decided)

- When a behaviour is only a prompt instruction (a framed opinion), user-facing docs should say the agent is told X, not that X is guaranteed.
- Prompt tests should check the content inside an injected untrusted block, not just that the block's tag is there.
