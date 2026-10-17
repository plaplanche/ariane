# Review 0

- Reviewed commit: `b259bfd6ffb29f207bdf20b8271195b57e1ef39e`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/opencode.py:264`) opencode `_int` duplicate is still there (dead code)

  The decided spec says "both `_int`, `_number` and the inline copies go", and the first acceptance criterion is "No duplicate left of the helpers above (a reviewer can check with `grep`)". `grep 'def _int' src` still finds `def _int(value: Any) -> int` at opencode.py:264. Nothing calls it any more because `_step_finish` now uses `as_int(...) or 0`, so it is dead code that ruff does not flag. This acceptance criterion fails as written. Fix: delete the function.

- **minor** (`docs/architecture/modules/attempts.md:41`) Class diagram still shows `add_command(command)`

  The Public API table was updated to `add_command(command, call_id)`, but the C4 level-4 classDiagram still shows the old one-argument signature, and `AttemptTally` now also holds a `_seen` set. Update the diagram so the module doc matches the code (rule 11 / C25).

- **minor** (`docs/architecture/modules/runtime.md:54`) runtime classDiagram lacks `failed` and `usage_text`

  The Public API table lists `SessionResult.failed(...)` and `usage_text()`, but the code-view class diagram still shows only `usage()`. The docs tests pass, but the diagram is now incomplete.

- **minor** (`src/ariane/runtime.py:44`) `as_number` is added but the spec does not name it

  The spec does not name a replacement for `_number`; it only says that `_number` and the inline copy go. Adding a public `as_number` is the simplest way to meet that, and it is documented in runtime.md. It is a small open choice that has no ADR. That is acceptable for a naming detail, but it is worth noting.

- **minor** (`src/ariane/opencode.py:210`) "stopped by Ariane at {n} tokens" is still written in two places

  The Current state section lists this text as duplicated (claude_code.py:182, opencode.py:210), but the decided spec gives no helper for it, so keeping both copies follows the spec. A small `token_stop_summary(n)` would finish the deduplication before #157 adds a third copy.

- **minor** (`tests/test_runtime_cap_texts.py:1`) No test checks that dead helpers are gone

  The new tests cover the texts, `failed`, `usage_text`, `json_object`, `as_int` and the call-id dedup. Nothing guards the 'no duplicate left' criterion, so the leftover `_int` passed every check.

- **blocking** Definition of done not met: The documentation the change affects is updated (C25).

  runtime.md (Public API and collaborations), attempts.md (table), config.md and 3-components.md (generated runtime --> config arrow) were updated. The attempts.md classDiagram still shows `add_command(command)`, and the runtime.md classDiagram lacks `failed` and `usage_text`. The flagged claude_code.md, opencode.md, flow.md and review_session.md describe behaviour that has not changed ("once per block id", "once per call"), and their public APIs did not change, so they did not need edits.

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

  tests/test_runtime_cap_texts.py imports `token_cap`, `cost_cap`, `is_token_cap`, `timeout_summary`, `SessionResult.failed`, `usage_text`, `json_object` and `as_int`, and calls `AttemptTally.add_command(cmd, call_id)`. Without the change these names do not exist and the call has the wrong arity, so the tests fail. The listed behaviour tests are unchanged and pass.

- **not met**: The documentation the change affects is updated (C25).

  runtime.md (Public API and collaborations), attempts.md (table), config.md and 3-components.md (generated runtime --> config arrow) were updated. The attempts.md classDiagram still shows `add_command(command)`, and the runtime.md classDiagram lacks `failed` and `usage_text`. The flagged claude_code.md, opencode.md, flow.md and review_session.md describe behaviour that has not changed ("once per block id", "once per call"), and their public APIs did not change, so they did not need edits.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The spec fixes almost every name and signature. The only open choice is naming `as_number` as the replacement for `_number`, a trivial naming detail that is documented in runtime.md. No design choice that needs an ADR is left open.

## Proposed learnings (not decided)

- When a refactor ticket says 'X goes', grep for the old definition. Ruff does not flag an unused private function, so dead copies pass every check.
- When a module doc's Public API table changes, also check the classDiagram in the same file. The docs tests only check the table.
