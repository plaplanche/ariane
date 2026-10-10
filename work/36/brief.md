# Product brief: Run the reviewer role on opencode (C5)

- Source: issue #36 (https://github.com/plaplanche/ariane/issues/36)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Vendor independence is a requirement (ADR 0014); the second runtime, opencode, starts with the reviewer role. ADR 0015 records what opencode 1.18.35 does: `opencode run --format json` emits events, `step_finish` carries tokens and a cost computed by opencode, permissions per agent can be given inline (`OPENCODE_CONFIG_CONTENT`, which wins over the repository's `opencode.json`), `--pure` stops plugins from the working tree, `OPENCODE_DISABLE_CLAUDE_CODE=1` stops `.claude` skills and prompt, and there is no budget, schema or tool option on the command line. The owner's decision (2026-10-10): the default reviewer stays Opus on Claude Code (#33); opencode is an option, used at least for slice 3's gate (a ticket reviewed on a second runtime).

## Current state

- `src/ariane/claude_code.py` is the only runtime adapter.
- After the earlier issues, the contract has Ariane-side budget stops, answer validation and login variables per runtime; `config.load` reads `ariane.toml` at the repository root.

## Decided spec

- A new adapter `src/ariane/opencode.py` (`runtime = "opencode"` in `[agents.<role>]`, refused for the implementer role for now, with a message naming the role).
- Command: `opencode run --pure --format json --model <provider/model> --agent ariane-<role>` with the prompt as the message, run in the session's working tree.
- Environment: `OPENCODE_CONFIG_CONTENT` defines the agent `ariane-<role>` with `permission` set to `"*": "deny"` and `allow` for the role's tools only (for the reviewer: `read`, `glob`, `grep`), and `steps` as the turn cap; `OPENCODE_DISABLE_CLAUDE_CODE=1`; `OPENCODE_DISABLE_AUTOUPDATE=1`; autoupdate and sharing off in the inline configuration. Login variables declared by the adapter are the provider keys the configuration names (for example `OPENAI_API_KEY`).
- Events: the adapter sums `step_finish` tokens and cost while the session runs and stops the process tree at the cap (stop reason `budget`); an `error` event or a non-zero exit is `error`; the session ends `finished` after the last `step_finish` with reason `stop`. A cost of 0 with tokens reported counts as "cost not reported".
- The reviewer's answer is the last text part; Ariane parses the fenced JSON block and validates it (ADR 0016), with the definition-of-done items as in #33.
- The journal records the runtime, the version (`opencode --version`) and that the title call's usage is not reported.
- Choosing the runtime for one run: when `ARIANE_CONFIG` is set, Ariane reads that configuration file instead of `ariane.toml` (same validation). Ariane's own `ariane.toml` keeps the Claude Code reviewer; `docs/ariane.opencode-reviewer.example.toml` shows a configuration with the reviewer on opencode, for a run such as slice 3's gate. The README says how (PowerShell and bash).
- Event fixtures are recorded from opencode 1.18.35 against a local OpenAI-compatible test server (as in ADR 0015); the owner's session adds them to this issue before the ticket runs.

## Release note

Added: the reviewer can run on opencode, with another vendor's model; `ARIANE_CONFIG` selects a configuration file for one run.

## Acceptance criteria

- Tests named `test_c5_opencode_*` with recorded event fixtures show: tokens and cost summed from `step_finish`; a stop at the cap; an `error` event; the inline configuration denies all but the role's tools; `--pure` and `OPENCODE_DISABLE_CLAUDE_CODE=1` are always set; the implementer role is refused.
- The two recorded sessions below are kept as `tests/fixtures/opencode_review.jsonl` and `tests/fixtures/opencode_error.jsonl` (verbatim) and tests read them through the adapter: the review gives `finished`, tokens 4,240 (input 1,000, cache read 3,000, output 240) and cost 0.0075 summed from the two `step_finish` events, and an answer parsed from the last text part's fenced JSON that validates as `no-go`; a cap below that total stops the session with `budget`; the error session gives `error`.
- Tests named `test_c22_config_path_*` show that `ARIANE_CONFIG` is read and validated, and that `ariane.toml` is read without it.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c5_opencode` runs at least 5 tests and they pass.
- [ ] `uv run pytest -k c22_config_path` runs at least 2 tests and they pass.
- [ ] `tests/fixtures/opencode_review.jsonl` and `tests/fixtures/opencode_error.jsonl` are the fixtures below, unchanged, and tests read them.
- [ ] Definition of done: `docs/architecture/modules/opencode.md` added; levels 0 to 3 show opencode; the generated references updated; the README explains the opencode reviewer.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

opencode for the implementer role, installing opencode (documented in the README).

## Related

ADR 0014, ADR 0015, ADR 0016, spec C5, C22.

## Recorded fixtures

opencode 1.18.35, run in a one-commit repository where `add(a, b)` returns `a - b`, against a local OpenAI-compatible test server scripted to answer: a title request (no tools), then a `read` tool call, then the answer as a fenced JSON block (review); or HTTP 500 on every request with tools (error).

`OPENCODE_DISABLE_CLAUDE_CODE=1 OPENCODE_DISABLE_AUTOUPDATE=1 OPENCODE_CONFIG_CONTENT=<config> opencode run --pure --format json --model fake/m --agent ariane-reviewer "<prompt>"`

with `<config>`:

```json
{"autoupdate":false,"share":"disabled","provider":{"fake":{"npm":"@ai-sdk/openai-compatible","name":"fake","options":{"baseURL":"<test-server>/v1","apiKey":"x"},"models":{"m":{"name":"m","cost":{"input":3,"output":15,"cache_read":0.3}}}}},"agent":{"ariane-reviewer":{"description":"Ariane reviewer","mode":"primary","steps":20,"permission":{"*":"deny","read":"allow","glob":"allow","grep":"allow"}}}}
```

Observed:
- The model was offered only `glob`, `grep` and `read`: `"*": "deny"` removes every other tool from the request, not only at call time.
- The title request (no tools) is billed by the provider but has no `step_finish` event, so its usage is not reported (as ADR 0015 says).
- Each step ends with a `step_finish` carrying `tokens` (`input` excludes cached tokens) and `cost` computed from the configured prices; the last one has `reason: "stop"`, the one before `reason: "tool-calls"`.
- On HTTP 500, opencode retried six times, then emitted one `error` event and exited with code 1.
- Kept as recorded except: the working tree's absolute path replaced by `/work/proj`, session ids zeroed, timestamps made relative to the first event, the test server's address replaced by `<test-server>`.

<details><summary>tests/fixtures/opencode_review.jsonl</summary>

```json
{"type":"step_start","timestamp":9,"sessionID":"ses_000000000000000000000000000","part":{"id":"prt_125d0c48a001rKVAq3pP4xgBWz","messageID":"msg_125d0bbdb001olpGUENVGPzmW2","sessionID":"ses_000000000000000000000000000","snapshot":"587a9cb0dea864051245c68ffb055a5eb1e4ee65","type":"step-start"}}
{"type":"tool_use","timestamp":54,"sessionID":"ses_000000000000000000000000000","part":{"type":"tool","tool":"read","callID":"call_1","state":{"status":"completed","input":{"filePath":"calc.py"},"output":"<path>/work/proj/calc.py</path>\n<type>file</type>\n<content>\n1: def add(a, b):\n2:     return a - b\n\n(End of file - total 2 lines)\n</content>","metadata":{"preview":"def add(a, b):\n    return a - b","truncated":false,"loaded":[],"display":{"type":"file","path":"/work/proj/calc.py","text":"def add(a, b):\n    return a - b","lineStart":1,"lineEnd":2,"totalLines":2,"truncated":false}},"title":"calc.py","time":{"start":0,"end":45}},"id":"prt_125d0c490001y6SwRA1TARpj3r","sessionID":"ses_000000000000000000000000000","messageID":"msg_125d0bbdb001olpGUENVGPzmW2"}}
{"type":"step_finish","timestamp":110,"sessionID":"ses_000000000000000000000000000","part":{"id":"prt_125d0c503001oWkR68hdNvUWk9","reason":"tool-calls","snapshot":"587a9cb0dea864051245c68ffb055a5eb1e4ee65","messageID":"msg_125d0bbdb001olpGUENVGPzmW2","sessionID":"ses_000000000000000000000000000","type":"step-finish","tokens":{"total":2060,"input":500,"output":60,"reasoning":0,"cache":{"write":0,"read":1500}},"cost":0.00285}}
{"type":"step_start","timestamp":329,"sessionID":"ses_000000000000000000000000000","part":{"id":"prt_125d0c5c60016Hd1i6ZPsSG6C6","messageID":"msg_125d0c534001n7SRw6EgCB4dqN","sessionID":"ses_000000000000000000000000000","snapshot":"587a9cb0dea864051245c68ffb055a5eb1e4ee65","type":"step-start"}}
{"type":"text","timestamp":329,"sessionID":"ses_000000000000000000000000000","part":{"id":"prt_125d0c5d00017QNlyd10IRyTaH","messageID":"msg_125d0c534001n7SRw6EgCB4dqN","sessionID":"ses_000000000000000000000000000","type":"text","text":"```json\n{\n  \"verdict\": \"no-go\",\n  \"findings\": [\n    {\n      \"severity\": \"blocking\",\n      \"file\": \"calc.py\",\n      \"line\": 2,\n      \"title\": \"add() subtracts instead of adding\",\n      \"detail\": \"add(a, b) returns a - b; the issue asks for the sum.\"\n    }\n  ],\n  \"definition_of_done\": [\n    {\n      \"item\": \"The change is covered by tests that fail without it.\",\n      \"met\": false,\n      \"evidence\": \"There is no test file.\"\n    }\n  ],\n  \"learnings\": [\n    \"The repository has no tests.\"\n  ]\n}\n```","time":{"start":305,"end":316}}}
{"type":"step_finish","timestamp":386,"sessionID":"ses_000000000000000000000000000","part":{"id":"prt_125d0c6190016A6rXz5fr8xmNT","reason":"stop","snapshot":"587a9cb0dea864051245c68ffb055a5eb1e4ee65","messageID":"msg_125d0c534001n7SRw6EgCB4dqN","sessionID":"ses_000000000000000000000000000","type":"step-finish","tokens":{"total":2180,"input":500,"output":180,"reasoning":0,"cache":{"write":0,"read":1500}},"cost":0.00465}}
```

</details>

<details><summary>tests/fixtures/opencode_error.jsonl</summary>

```json
{"type":"error","timestamp":0,"sessionID":"ses_000000000000000000000000000","error":{"name":"APIError","data":{"message":"upstream failure","statusCode":500,"isRetryable":true,"responseHeaders":{"content-type":"application/json","date":"Sat, 10 Oct 2026 12:37:57 GMT","server":"BaseHTTP/0.6 Python"},"responseBody":"{\"error\": {\"message\": \"upstream failure\", \"type\": \"server_error\"}}","metadata":{"url":"<test-server>/v1/chat/completions"}}}}
```

</details>
