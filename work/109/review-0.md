# Review 0

- Reviewed commit: `6287474e0c434807723ff305b6ecd39c9e35413b`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/spec.md:214`) C11's new sentence makes the clean-merge path hard to read

  The sentence reads: merge; 'a conflict or a red check after the merge goes to one implementer session, then Ariane runs the regeneration command, replays every check and reviews, and pushes only on go'. Read literally, the replay and the review come only after the implementer session. A clean merge also needs a replay and a review before the push (ADR 0033, Decision 1, first sub-bullet). The text also says a 'red check after the merge', which means a replay already ran before any implementer. Suggested wording: 'merges it into the ticket branch, runs the regeneration command if declared, replays every check and reviews; a conflict or a red check goes to one implementer session first; Ariane pushes only on go and green, otherwise …'.

- **minor** (`docs/adr/0033-branch-update-and-ticket-dependencies.md:17`) The ADR does not mention the regeneration command that spec C11 keeps

  Spec C11 still says Ariane 'runs the project's regeneration command if one is declared' as part of the update. ADR 0033's Decision, which is cited as the source of this rule, does not say so. Slice 5's implementer will read the ADR and could leave the step out. One clause in Decision 1 would fix it (for example 'after the merge, the regeneration command if declared, then the checks are replayed…').

- **minor** (`docs/spec.md:214`) Two ADR rules are not reflected in C11

  The fix-round limit of C10 and the refusal of a branch whose pull request is merged or closed appear only in the ADR. This is acceptable because the ticket asks for 'one or two sentences' and cites the ADR. A reader of the spec alone will still miss them. No action needed.

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

  This is a docs-only ticket ('No code change'). No behaviour changes, so there is nothing for a test to cover. The docs-references check and the test suite are green, and the new ADR 0033 is the next free number (0032-issue-gate.md exists).

- met: The documentation the change affects is updated (C25).

  Only docs/spec.md (C1 line 109, C11 line 214, C23 line 325, slice 5's roadmap row line 389) and the new docs/adr/0033-branch-update-and-ticket-dependencies.md change. docs/architecture/ is unchanged, as the ticket's checklist requires, and slice 5's gate is unchanged. A grep found no other spec text that mentions rebase or the optional Budget section, so nothing else is left stale.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  ADR 0033 follows the template in docs/adr/README.md: status accepted, date, capabilities C1, C11, C23, Context, Decision, Consequences and Alternatives considered. It records the owner's decisions on update by merge, implementer on conflict or red check, the fix-round limit, refusal of merged or closed branches, the 'Depends on' refusal, placement first in slice 5, and the three rejected alternatives.

## Proposed learnings (not decided)

- When a spec sentence describes a process with several paths (clean merge versus conflict), state the common path first and the exception second, so 'then …' does not read as applying only to the exception.
- A step the spec keeps, such as the regeneration command, should also appear in the ADR the spec cites for that rule, so an implementer who reads only the ADR does not leave it out.
