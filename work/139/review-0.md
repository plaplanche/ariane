# Review 0

- Reviewed commit: `b49985d1b0234f92360a5e03b19b6a914e5450d3`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/review_session.py:138`) Cap key chosen by matching the cap text's prefix

  The code picks `agents.reviewer.max_tokens` or `max_budget_usd` by checking whether `result.cap` starts with "Ariane token cap". That string is built separately in opencode.py:207 and claude_code.py:186. If either wording changes, the stop silently names the cost key. A structured cap kind on SessionResult would hold up better. It works today, and the tests cover both branches.

- **minor** (`tests/test_c5_opencode.py:431`) Cost-cap test asserts less than the token-cap test

  test_c5_reviewer_cap_cost_cap_names_the_budget_key does not check `outcome.exit_code != 0`. It also does not check that the reason reads "stopped at runtime cost cap (0.003 USD)". The token-cap test checks both.

- **minor** (`docs/adr/0029-opencode-reviewer.md:47`) No blank line before the new amendment heading

  `## Amendment (2026-10-17, #139)` comes straight after the previous amendment's list item. It still renders as a heading, but the rest of the ADR puts a blank line between sections.

- **minor** (`docs/architecture/modules/flow.md:32`) flow.md describes ticket.review.stopped without the new cap line

  flow.md still says the entry holds only cost and tokens. It now starts with "Cap reached: <cap>." when a cap applied. review_session.md was updated (it was the module the ticket named), but flow.md now gives a partial description.

- **minor** (`tests/test_c5_opencode.py:21`) Test module imports a helper from another test module

  `from test_flow import worktree` couples the two test files. A shared helper belongs in conftest.py.

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

  There are three `test_c5_reviewer_cap_*` tests in tests/test_c5_opencode.py, so `-k c5_reviewer_cap` selects at least 3. Before this change the journal had no "Cap reached: ..." line, the stop line did not name the key, and the example file said 400000. All three tests would have failed on the base commit. The tests check passed.

- met: The documentation the change affects is updated (C25).

  The ticket names three documents and all are updated. docs/architecture/modules/review_session.md has a new bullet. The README "Reviewer on opencode" paragraph explains why the cap is 1,500,000. docs/ariane.opencode-reviewer.example.toml has the new value and comment. ADR 0029 has the amendment. The event and its level are unchanged, so docs/logs.md stays valid. flow.md only gives a partial description now (minor finding).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket's decided spec fixes the value, the journal wording, the reason and next-action text, and the hard-stop behaviour. The dated amendment in ADR 0029 records them. The change takes no other design choice.

## Proposed learnings (not decided)

- When a stop message must name a config key, carry the cap kind as structured data on the session result rather than parsing the human-readable cap text.
- When a ticket changes what a journal entry contains, search docs/architecture for every module file that describes that entry, not only the one the ticket names.
