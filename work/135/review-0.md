# Review 0

- Reviewed commit: `ae74dde0cd93f813498edae75c162b3808d1d5d3`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/architecture/modules/shadow.md:40`) Code view still shows the old `_deliver` signature

  `ShadowRun._deliver` now takes `unchanged: int = 0` (src/ariane/shadow.py:119), but the class diagram still lists `_deliver(checked, settled, reviewed, results)`. Ariane had already flagged this document as untouched. The README also doesn't say that a shadow run whose fix round changed nothing ends as `needs a human`; that outcome is only visible in the journal.

- **minor** (`docs/architecture/3-components.md:169`) C4 component sequence diagrams do not show the new early stop

  Both loops (`at most two fix rounds, while the review is no-go` at line 169, and the shadow loop at line 215) still show every fix round as replay plus review. They don't show that a round leaving the head unchanged skips both and goes straight to delivery. Rule 11 asks for the C4 level files to be updated too. The issue's checklist names only flow.md and metrics.md, so this isn't blocking.

- **minor** (`src/ariane/flow.py:357`) An agent commit that only picks up Ariane's records counts as a change

  "Unchanged" means the head didn't move. If a fix session runs `git commit -a` with no real edit, it commits this ticket's `work/<n>/` journal, which `_commit_agent_work` tolerates (lines 370-377). The head moves, so Ariane replays and reviews the same code again: the exact cost the ticket wants to avoid. Comparing `git diff --name-only head_before HEAD` outside `work/` would catch this. It's a narrow edge case and the spec's wording ("head") is met.

- **minor** (`src/ariane/delivery.py:153`) Draft PR body still says "still no-go after the fix rounds" for an unchanged round

  The CLI stop line now says "fix round N changed nothing", but the pull request body's "Needs a human" line still says "the review is still no-go after the fix rounds". That is not wrong, since the review is still no-go, but the PR doesn't tell the human that the rounds stopped early. The spec only asks for the stop line to change.

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

  tests/test_fix_rounds.py adds three `test_c10_unchanged_fix_*` tests. The first and third fail without the change: the old loop would replay and review again (more than one reviewer session, no "changed nothing" line, no `unchanged_fix_rounds` key). The second, a session that commits by itself, guards against counting a moved head as unchanged. The conftest `edit_app` now writes a different line per fix round, so existing tests keep changing the commit.

- met: The documentation the change affects is updated (C25).

  Everything the issue's checklist names is updated: docs/architecture/modules/flow.md (fix-rounds paragraph), modules/metrics.md (`unchanged_fix_round()`, `unchanged_fix_rounds` field), docs/logs.md (`ticket.fix.unchanged`, matching logs.py; the docs-references check is green) and the README fix-rounds paragraph. Small gaps remain in shadow.md's `_deliver` signature and the 3-components.md sequence diagrams (minor findings). logs.md needs no change: it describes the mechanism, not the list of types.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0027-fix-rounds-implementation.md gains an amendment for ticket #135. It records the head-equality rule, the journal entry, the skipped replay and review, the draft delivery and stop line, the new metrics field, unchanged handling of budget, turns, timeout and error, and the rejected alternative (rerunning the fix session once).

## Proposed learnings (not decided)

- When a change adds a parameter to an overridable method (`_deliver`), also check the subclass's module doc code view (shadow.md). The mapped-docs warning pointed straight at it.
- Detecting "unchanged" from the head alone also counts commits that only touch the ticket's own records. Compare the diff outside `work/` when the cost of a needless review matters.
- Changes to fake-runtime helpers in conftest (here `edit_app` writing a per-round marker) can quietly change the behaviour of every existing test. Check that the old tests still test what they claim.
