# Review 0

- Reviewed commit: `a235305c650aef5aeea48278c036d58621095cc5`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`README.md:131`) README already has a documentation list, and the new page is not in it

  The ticket's 'Current state' says the README has no documentation list. That is wrong: README.md:131-140 lists docs/spec.md, docs/architecture/, docs/reference/, docs/logs.md and docs/adr/. docs/benchmark.md is linked only from the new paragraph at README.md:16, not from this list. The ticket says 'No other change', so the implementer was right not to add it. A follow-up could add the benchmark (and docs/learnings.md, which is also missing) to that list so the index is complete.

- **minor** (`docs/benchmark.md:22`) Paragraph inside the Method list breaks it in two

  Line 22 ('Lot 1 ran three times…') is a plain paragraph between the Attempts table and the '- **Rules**' item. The Method bullet list is therefore split into two lists, and the sentence is not indented under the Attempts item. It renders fine in CommonMark/GFM. The ticket asked for a verbatim copy, so this is correct as delivered; it is noted only as a possible later cleanup.

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

  Not applicable as a code test: this is a docs-only change with no behaviour to test (src/ariane/ is out of scope and not touched). I checked the acceptance criterion by hand: docs/benchmark.md (77 lines) matches, line for line, the text between the ---8<--- markers in the ticket, and README.md:16 has the exact sentence the ticket gives. The replayed checks, including 'docs: references', are green.

- met: The documentation the change affects is updated (C25).

  README.md:16 adds the paragraph the ticket specifies, right after the status paragraph (lines 7-14), linking docs/benchmark.md. No module or generated reference is affected, so docs/architecture/, docs/reference/ and docs/logs.md need no change. Minor gap: the README's existing documentation list (lines 131-140) does not include the page, as the ticket required ('No other change').

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket fixes the whole content verbatim and the README sentence word for word, so the implementer had no open choice and no ADR is needed.

## Proposed learnings (not decided)

- A ticket's 'Current state' can be wrong (here it said the README has no documentation list, but README.md:131-140 has one). Check it against the tree before following 'No other change'.
- For verbatim-content tickets, compare the file line by line with the ticket's block; the replayed checks do not verify the content.
