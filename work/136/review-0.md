# Review 0

- Reviewed commit: `50ecbdfc9d48ea5da67877b1bb948ed6374f48f5`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/architecture/modules/review_session.md:56`) Code view still shows the old ReviewSession.run signature

  The change adds a `changed` parameter to `ReviewSession.run` (src/ariane/review_session.py:65), placed before `after_session`. The class diagram still reads `run(replay, checked, diff, results, not_updated, after_session) Review`. Ariane flagged this document as untouched. Rule 11 asks that the module doc of every touched module be updated. flow.md, replay.md and verify.md are only wiring and have no signature to fix, so this diagram is the one stale spot.

- **minor** (`tests/test_c9_not_run_locally.py:1`) Nothing tests the wiring from flow and verify to checks.md and the reviewer prompt

  The new tests call `checks.report(..., changed)` and `review.prompt(..., changed=...)` directly. No test runs `_TicketRun._check_and_deliver`, `replay.review_round` or `_Verification._review_in` and then checks that `self.changed` / `changed` reaches both. If flow.py:440 dropped `self.changed`, or replay.py:149 passed `()`, every test would still pass. The feature would then quietly do nothing. The acceptance criteria only ask for unit-level tests, so this is minor.

- **minor** (`src/ariane/review.py:258`) review.py calls the private helper context._escape

  The reviewer block escapes paths with `context._escape`, a private name from another module. It works, but it ties review.py to a private name in context.py. If review.py already escapes `not_updated` paths through a shared helper, that helper would be the cleaner choice.

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

  tests/test_c9_not_run_locally.py adds 6 test functions (9 cases with the parametrize), all named test_c9_not_run_locally_*. They cover: parsing plus schema validity; refusing [], a string, [1] and [""] with an error naming checks[0].not_run_locally; the schema refusing an empty list; checks.md listing the globs and the matching files, 'no changed file matches', and nothing for a check without the key; the reviewer block appearing only on a match; the implementer line marking the check. Without the change, each of these fails (unknown key, missing CheckResult field, missing text). The wiring through flow and verify is not tested (minor finding).

- met: The documentation the change affects is updated (C25).

  These were updated: README paragraph on checks, ADR 0042, modules/config.md, config_schema.md, checks.md, review.md and context.md, the regenerated docs/reference/ariane.toml.schema.json (matches config_schema.py), and docs/ariane.example.toml (key shown, commented). This covers every item in the ticket's documentation checklist, and the docs-references check passes. One small gap remains: the ReviewSession.run signature in the review_session.md class diagram is stale (minor finding).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0042-checks-declare-tests-not-run-locally.md uses the next free number after 0041. It records the key, the validation, the records, the reviewer and implementer prompts, and why the key is declared rather than detected, with the alternative considered. The spec left nothing else open: the implementer's own wording, 'Changed files it skips: …', still lists the matching diff files, as the spec asks.

## Proposed learnings (not decided)

- When a change adds a parameter to a method shown in a module's C4 class diagram, update that diagram's signature too. Ariane's untouched-docs flag catches these, and they are easy to miss.
- For features that pass data from the flow into records or prompts, add at least one test through flow or verify. Unit tests on the formatting functions alone do not catch a dropped argument.
- Order of side effects: `changed` is computed from start_commit before each commit, so it is cumulative across fix rounds. checks.md and the reviewer prompt therefore always use the whole ticket diff, never only the latest fix round.
