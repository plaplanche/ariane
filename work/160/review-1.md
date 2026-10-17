# Review 1

- Reviewed commit: `bb48a98c57ab7fc67ac0667ce27327fbaf8c8efe`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/opencode.py:210`) "stopped by Ariane at {n} tokens" is still written twice

  The issue's Current state lists this text as duplicated (claude_code.py:182 and opencode.py:210). The Decided spec gives it no helper, so leaving it is not a spec violation. But a grep still finds a copy, and the Codex runtime (#157) will copy it a third time. A small `token_stop_summary(n)` helper next to `token_cap` would close it.

- **minor** (`src/ariane/runtime.py:161`) session_for takes **extra: Any, so mypy no longer checks Session fields

  Before, flow and review_session built `Session(...)` with typed keyword arguments. Now `json_schema`/`add_dirs` pass through `**extra: Any`, so a misspelled keyword only fails at runtime. The spec does call for `**extra`. Explicit keyword-only `json_schema=None, add_dirs=()` parameters would keep type checking.

- **minor** (`src/ariane/runtime.py:44`) as_number added beyond the decided spec, without an ADR

  The spec names `as_int` and says the inline `_number` copies go, but it doesn't name `as_number`. Adding it is the simplest way to meet the spec and it is documented in runtime.md's Public API. It is a small open choice; an ADR line would satisfy rule 2 strictly. The new `runtime --> config` import (for AgentConfig) creates no cycle (config.py imports nothing from runtime), and the diagrams were regenerated.

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

  tests/test_runtime_cap_texts.py imports token_cap, cost_cap, is_token_cap, timeout_summary, json_object, as_int and SessionResult.failed, and calls add_command(command, call_id). None of these exist on the base, so the file fails there. It checks the exact texts ('Ariane token cap (5000 tokens)', 'runtime cost cap (2 USD)', 'killed after 90 s (time limit)'), usage_text and call-id deduplication. The listed regression tests are not edited in the diff, and Ariane's replayed tests passed.

- met: The documentation the change affects is updated (C25).

  runtime.md: Public API table gains every new name, and the class and dependency diagrams are updated. attempts.md: add_command(command, call_id). config.md and 3-components.md: runtime --> config arrow regenerated. The flagged claude_code.md, flow.md, opencode.md and review_session.md list no removed private helper and no changed public name; their prose (e.g. 'stopped by Ariane at <n> tokens', runtime.describe) is still accurate. docs: references and the test_docs_* tests pass.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  The ticket's Decided spec fixes the helper names, signatures and locations. The one small addition (as_number, the inline cost check's replacement) is a direct consequence of 'the inline copies go'. It is documented in runtime.md and is not a behaviour choice, so no new ADR is needed (minor note in the findings).

## Proposed learnings (not decided)

- When a refactor ticket lists duplicated texts in Current state, check that the Decided spec gives each one a helper; otherwise a grep-based 'no duplicate left' criterion leaves gaps.
- A factory with **extra: Any loses mypy's checking of dataclass keyword arguments; prefer explicit keyword-only optional parameters.
- Moving a dedup set into a shared tally (AttemptTally) keeps behaviour only if each runtime passes the same key it used before; check the call-id expressions line by line.
