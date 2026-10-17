# Review 0

- Reviewed commit: `dbb82c756dd68cdf8eddb40d24b36642ac3a31a1`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`tests/test_review.py:267`) New test only checks the prompt for an issue with no Out of scope section

  `_scope_prompt("## Context\nc\n")` builds a prompt without an Out of scope section, so `{scope_rule}` is empty. Nothing checks that the new rule still comes right after "Be adversarial" and before the out-of-scope rule when that rule is present (the ticket asks to keep both rules, #134). Reading the f-string at src/ariane/review.py:278-288 shows the order is correct. A second assertion with an Out of scope body would lock that order in.

- **minor** (`tests/test_review.py:268`) The test collapses whitespace, so it would not catch a change in line wrapping

  The test joins the prompt with `" ".join(text.split())` before matching. That is fine for the criterion "exactly the text", because the wording and punctuation are checked word for word. It would not notice a reflow or a missing leading `- `. This is acceptable, since the prompt is wrapped by hand at about 95 columns.

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

  tests/test_review.py:267 `test_c10_prompt_checks_order_of_side_effects` checks that the "Be adversarial" rule's last sentence is immediately followed by the full new rule. Without the change in src/ariane/review.py:280-287 the rule text is missing and the assertion fails. The tests check passed (116 s).

- met: The documentation the change affects is updated (C25).

  docs/architecture/modules/review.md:34 has a new paragraph describing the rule and where it sits in the prompt. README.md:45 adds a line to the review paragraph, which lists what the reviewer checks (it already lists the out-of-scope handling). These are the documents the ticket's checklist names. No other file repeats the prompt rules (grep for 'wrong, missing or unsafe').

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket fixes the exact text, where it goes (right after "Be adversarial"), that there is no configuration, and the test name. The change leaves no choice open, so no ADR is needed.

## Proposed learnings (not decided)

- When a prompt rule is inserted between a fixed rule and a conditional one (such as scope_rule), test both prompt variants, with and without the conditional block, so the order is locked in.
- For prompt-only changes, the order-of-side-effects check is trivially met (no writes). Say so instead of inventing findings.
