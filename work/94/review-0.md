# Review 0

- Reviewed commit: `4a555bc6878cd497ff21481f7a1a27d6b0a6df42`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/adr/0030-slice-4-measurement-and-shadow.md:51`) Rejected alternative contradicts decision 5

  'Asking the human to declare minutes per ticket' is listed as rejected, but decision 5 (`ariane judge ... --minutes N`) and the Consequences do exactly that for shadow tickets. The text is copied word for word from the ticket, which requires it, so this is not a fault of the change. A later ADR or a follow-up could reword it as 'for delivered tickets' so the record does not contradict itself.

- **minor** (`docs/adr/0030-slice-4-measurement-and-shadow.md:38`) Line breaks the ~100-column wrapping of the other ADRs

  Line 38 (`<repo>.ariane/shadow/<n>/work/<n>/metrics.json`, one line per ticket ...) is about 105 characters long; the other lines wrap before 100. It is word for word what the ticket gives, and no check enforces the width. Cosmetic only.

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

  Not applicable: the change only touches documentation (two ADR files) and the ticket says 'No code change'. No behaviour exists to test. The replayed checks, including 'docs: references', pass.

- met: The documentation the change affects is updated (C25).

  The diff adds docs/adr/0030-slice-4-measurement-and-shadow.md word for word as the ticket gives it, and changes the status line of docs/adr/0012-measurements.md to 'accepted; format amended by 0030'. This follows the partial-replacement convention in docs/adr/README.md. docs/adr/README.md has no ADR index to update. No code changed, so architecture and module docs are unaffected. This matches the checklist item 'only the two ADR files change'.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0030 records slice 4's open choices: the metrics format, human time, the shadow flag, a separate clone for shadow state, `ariane judge`, the bypass and attempt counters, and the report contents. The change makes no further choices.

## Proposed learnings (not decided)

- For a ticket that asks for ADR text word for word, compare the file against the ticket text, check the README's status convention for amended ADRs (partial replacement keeps 'accepted; ... by NNNN'), and confirm that no index lists the ADRs.
- Tickets that give ADR text word for word can carry internal contradictions (an alternative listed as rejected but partly adopted). Flag these as minor for a follow-up rather than blocking a word-for-word copy.
