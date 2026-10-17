# Review 0

- Reviewed commit: `5e551c27a4e87a8ccfdc39a61d90ad60355aa036`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/claude_code.py:182`) "stopped by Ariane at {n} tokens" is still written twice

  The issue's Current state lists this text as duplicated in claude_code.py and opencode.py. It is still written out in both, at claude_code.py:182 and opencode.py:210. The Decided spec names no helper for it, so the change follows the spec. Still, a grep for the acceptance criterion "No duplicate left of the helpers above" will find this text twice. A shared helper (for example `token_stop_summary(n)`) would close the gap before #157 adds a third copy.

- **minor** (`src/ariane/runtime.py:45`) `as_number` was added beyond the Decided spec without a test

  The spec lists `as_int` but not `as_number`. The diff adds `as_number` to replace `_number` and the inline cost check in opencode. That is the reasonable reading of "`_number` and the inline copies go", and it is documented in runtime.md. However, test_runtime_cap_texts.py does not test it (bool rejection, int converted to float).

- **minor** (`tests/test_runtime_cap_texts.py:40`) The deduplication test does not check that a different call id is counted

  The test only checks that a repeated call id counts once. It does not check that a second call id with the same command adds another push. Without that check, an implementation that deduplicated by command text would also pass.

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

  tests/test_runtime_cap_texts.py imports token_cap, cost_cap, is_token_cap, timeout_summary, json_object, as_int and SessionResult.failed/usage_text, and calls add_command with a call id. None of these exist on the base, so the test fails there. It checks the cap texts byte for byte. The existing adapter, review and flow tests still pass unedited (the replayed test check is green).

- met: The documentation the change affects is updated (C25).

  runtime.md's Public API table and class diagram list every new name. attempts.md shows the new `add_command(command, call_id)`. The new runtime --> config edge appears in 3-components.md, config.md and runtime.md. The four flagged module docs (claude_code, flow, opencode, review_session) reference no moved or removed name, and their dependency edges are unchanged: they already import runtime. The docs reference check passes.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The issue's Decided spec fixes the names, signatures and locations. The only extras are `as_number` (the replacement the spec implies for `_number`) and the runtime --> config import that `session_for(agent: AgentConfig, ...)` needs. Neither changes behaviour, and neither is an open design choice that needs an ADR.

## Proposed learnings (not decided)

- When an issue's Current state lists more duplicates than its Decided spec gives helpers for, check each listed text with grep: the acceptance criterion's 'no duplicate left' may still not hold.
- When a helper moves into runtime.py and needs a new import (here config), check that config does not import runtime back, to rule out an import cycle.
