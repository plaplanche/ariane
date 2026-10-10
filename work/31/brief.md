# Product brief: Enforce a token cap from streamed usage and map stop reasons in Ariane (C5)

- Source: issue #31 (https://github.com/plaplanche/ariane/issues/31)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

ADR 0015 makes the agent contract runtime-neutral: Ariane enforces the budget cap, classifies the stop reason and keeps cost and tokens as reported, whatever the runtime; a runtime's flag is an optimisation. Today Claude Code's `--max-budget-usd` is the only budget guarantee and usage is read once, at the end. Claude Code streams usage per message with `--output-format stream-json --verbose` (tokens per `assistant` event, cost only in the final `result`).

## Current state

- `src/ariane/claude_code.py` `command` uses `--output-format json` and `--max-budget-usd`.
- `src/ariane/claude_code.py` `parse_result` reads the final result only.
- `src/ariane/runtime.py` `Session` has `max_budget_usd`; no token cap.
- `src/ariane/process.py` runs a command and returns when it ends.
- Probe on Claude Code 2.1.296 (2026-10-10), recorded below: one model message is streamed as several `assistant` events (one per content block: `thinking`, then `tool_use` or `text`), all with the same `message.id` and the **same** `usage`; the `output_tokens` of these events are partial (3), while the final `result` reports the session totals (`output_tokens` 191, `total_cost_usd` 0.0133076). Summing every `assistant` event's usage would count each message twice or more.

## Decided spec

- `Session` gains `max_tokens` (`int | None`); `[agents.<role>] max_tokens` in `ariane.toml` is optional and validated (positive integer), and the journal states the caps applied.
- The process helper gains a way to read a command's standard output line by line while it runs and to stop the whole process tree on request.
- The Claude Code adapter uses `--output-format stream-json --verbose`, keeps `--max-budget-usd` as the runtime's own cost cap, and keeps a running total of tokens: for each `message.id`, the latest `usage` seen (input, cache read, cache write, output) counts once. It stops the session when the total reaches `max_tokens`; the stop reason is then `budget` and the journal says "stopped by Ariane at <n> tokens".
- The final `result` event gives the stop reason (`subtype`), the cost, the summary and the session's token totals (which replace the running total), as today; a stream that ends without a `result` is `error`.
- The journal says which cap applied: Ariane's token cap, or the runtime's cost cap.

## Release note

Changed: Ariane enforces a token cap on agent sessions itself.

## Acceptance criteria

- Tests named `test_c5_budget_stream_*` with a fake streaming agent show: a session stopped by Ariane when the counted tokens reach the cap (reason `budget`, process tree gone); a session finishing under the cap; a stream without a final result classified `error`; events repeating a `message.id` counted once; the journal line naming the cap.
- The recorded session below is kept as `tests/fixtures/claude_stream_success.jsonl` (verbatim, one JSON object per line) and a test parses it: stop reason `finished`, cost 0.0133076, tokens from the `result`.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c5_budget_stream` runs at least 5 tests and they pass.
- [ ] Definition of done: `docs/architecture/modules/claude_code.md`, `process.md`, `runtime.md` and `config.md` updated; the generated configuration schema and log catalogue regenerated if they change.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Login variables per runtime (separate issue), the reviewer, opencode.

## Related

ADR 0015, spec C5.

## Recorded fixture

`claude -p --output-format stream-json --verbose --model claude-haiku-4-5-20251001 --tools Read --permission-mode bypassPermissions --setting-sources project,local --no-session-persistence --max-budget-usd 0.2`, prompt "Read a.txt and answer with its content only.", in a fresh repository whose `a.txt` holds `hello`. Kept: the `system` init, `assistant`, `user` and `result` events, trimmed to the fields Ariane reads; working directory and session id replaced, thinking signatures removed.

<details><summary>tests/fixtures/claude_stream_success.jsonl</summary>

```json
{"type":"system","subtype":"init","cwd":"/work/proj","session_id":"00000000-0000-4000-8000-000000000000","tools":["Read"],"model":"claude-haiku-4-5-20251001","permissionMode":"bypassPermissions","apiKeySource":"none","claude_code_version":"2.1.296"}
{"type":"assistant","message":{"model":"claude-haiku-4-5-20251001","id":"msg_011Cft2CCdEz9ctuE9E8fS8t","type":"message","role":"assistant","content":[{"type":"thinking","thinking":"","signature":"<removed>"}],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":9,"cache_creation_input_tokens":5656,"cache_read_input_tokens":0,"output_tokens":3}},"parent_tool_use_id":null,"session_id":"00000000-0000-4000-8000-000000000000","uuid":"8d9bbf88-6619-4a51-8e5e-77005ff9ced8","timestamp":"2026-10-10T05:41:23.144Z"}
{"type":"assistant","message":{"model":"claude-haiku-4-5-20251001","id":"msg_011Cft2CCdEz9ctuE9E8fS8t","type":"message","role":"assistant","content":[{"type":"tool_use","id":"toolu_0181aQ7JiUXyh6rbVDZPsJnK","name":"Read","input":{"file_path":"/work/proj/a.txt"},"caller":{"type":"direct"}}],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":9,"cache_creation_input_tokens":5656,"cache_read_input_tokens":0,"output_tokens":3}},"parent_tool_use_id":null,"session_id":"00000000-0000-4000-8000-000000000000","uuid":"9b4ab70d-c722-4de4-ad21-32e5e4a15ef5","timestamp":"2026-10-10T05:41:23.522Z"}
{"type":"user","message":{"role":"user","content":[{"tool_use_id":"toolu_0181aQ7JiUXyh6rbVDZPsJnK","type":"tool_result","content":"1\thello\n2\t"}]},"parent_tool_use_id":null,"session_id":"00000000-0000-4000-8000-000000000000","uuid":"672bf9ab-2113-49e8-9848-a30c0ce9a38d","timestamp":"2026-10-10T05:41:23.549Z","tool_use_result":{"type":"text","file":{"filePath":"/work/proj/a.txt","content":"hello\n","numLines":2,"startLine":1,"totalLines":2}}}
{"type":"assistant","message":{"model":"claude-haiku-4-5-20251001","id":"msg_011Cft2CJqo8dfbfWmeKUoy4","type":"message","role":"assistant","content":[{"type":"thinking","thinking":"","signature":"<removed>"}],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":8,"cache_creation_input_tokens":229,"cache_read_input_tokens":5656,"output_tokens":3}},"parent_tool_use_id":null,"session_id":"00000000-0000-4000-8000-000000000000","uuid":"7cc05c8e-eb7f-4cfc-b053-de314993b6ea","timestamp":"2026-10-10T05:41:24.488Z"}
{"type":"assistant","message":{"model":"claude-haiku-4-5-20251001","id":"msg_011Cft2CJqo8dfbfWmeKUoy4","type":"message","role":"assistant","content":[{"type":"text","text":"hello"}],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":8,"cache_creation_input_tokens":229,"cache_read_input_tokens":5656,"output_tokens":3}},"parent_tool_use_id":null,"session_id":"00000000-0000-4000-8000-000000000000","uuid":"5afde90c-67b3-44e5-9231-9c52c28a208a","timestamp":"2026-10-10T05:41:24.519Z"}
{"type":"result","subtype":"success","is_error":false,"result":"hello","total_cost_usd":0.0133076,"usage":{"input_tokens":17,"cache_creation_input_tokens":5885,"cache_read_input_tokens":5656,"output_tokens":191},"num_turns":2,"stop_reason":"end_turn","duration_ms":3731,"permission_denials":[],"terminal_reason":"completed","session_id":"00000000-0000-4000-8000-000000000000"}
```

</details>
