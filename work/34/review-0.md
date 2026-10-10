# Review 0

- Reviewed commit: `1610397f55f4dbf1c51233af65734b8c37864822`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/architecture/modules/delivery.md:3`) Module summary still says only tickets with passing checks are delivered

  Delivery can now open a draft pull request when blocking checks still fail after the last fix round (ADR 0027 and test_c10_fix_round_checks_failing_after_the_last_round_give_a_draft). The first line, 'Delivers a ticket whose blocking checks passed', is now inaccurate.

- **minor** (`docs/architecture/3-components.md:46`) Component diagram leaves out some review_session dependencies

  modules/review_session.md lists review_session -> checks, config and tracker. The level 3 diagram shows only review, runtime and ticket.

- **minor** (`src/ariane/delivery.py:99`) The draft docstring does not cover the failing-checks case

  The `draft` property docstring mentions only a review still no-go. A draft also results when checks fail after the last round, because `settled` is then the earlier no-go review. The behaviour is correct; only the reason is undocumented.

- **minor** (`src/ariane/delivery.py:162`) Draft pull request body still says 'Closes #N'

  Merging the draft after a hand finish closes the issue, which is probably what the owner wants. Still, a 'needs a human' draft that says 'Closes' may surprise; a follow-up could decide this.

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

  tests/test_fix_rounds.py has 6 test_c10_fix_round_* tests. They check no-go then go (a normal pull request, review-1.md, one push), three no-go (a draft, exactly 3 reviews, findings in the body, one push), the findings in the fix prompt in an untrusted block, failing checks after a fix round counting as negative, and failing checks after the last round giving a draft. test_github covers the draft field in the request. All depend on the new 'draft' key, review-<n>.md and the fix sessions, so they fail without the change.

- met: The documentation the change affects is updated (C25).

  The flow, review, delivery, tracker, github, context and ticket module docs are updated. review_session.md is added. The 3-components sequence diagram shows the fix-round loop. docs/logs.md is regenerated with ticket.fix.round (the docs: references check is green). The CLAUDE.md C10 line is updated. modules/logs.md needed no change: it describes the declaration mechanism, not individual types, and links the regenerated catalogue. Small inaccuracies are listed as minor findings.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0027-fix-rounds-implementation.md records the open choices: fix session config and prompt, failing checks as a negative round, review file numbering, draft delivery and exit code 1, tracker `draft` parameter, alternatives rejected.

## Proposed learnings (not decided)

- When a flow can now deliver in a new state (here a draft with failing checks), recheck the module summaries that state delivery preconditions.
- Keep the component diagram's edges for a new module in step with its module file's collaboration diagram.
