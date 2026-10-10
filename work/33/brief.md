# Product brief: Review every ticket with a read-only reviewer on a different model (C10)

- Source: issue #33 (https://github.com/plaplanche/ariane/issues/33)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

C10: before delivery, an adversarial review by a different model from the implementer's, with a verdict and findings marked blocking or minor; a positive verdict that lists a blocking finding counts as negative; findings posted redacted and kept in the ticket folder with the commit they reviewed. ADR 0016 sets how, on the runtime-neutral contract of ADR 0015. C26 and ADR 0023: the reviewer also answers each sentence item of the definition of done. This issue adds one review; fix rounds are the next issue.

## Current state

- `src/ariane/flow.py` `_check_and_deliver` replays the checks and delivers; there is no review.
- `src/ariane/config.py` `Config` has `implementer` (and `definition_of_done` after #62).
- `src/ariane/claude_code.py` builds the Claude Code command; `src/ariane/context.py` builds the implementer's prompt.
- `scripts/generate_docs.py` (after #60) generates `docs/reference/`.

## Decided spec

- Configuration: a `[agents.reviewer]` table with the same keys as the implementer's, plus `runtime`. Ariane refuses a configuration whose reviewer model equals the implementer's, naming `agents.reviewer.model`. Ariane's own `ariane.toml` declares `runtime = "claude-code"`, model `claude-opus-5-5`, tools `Read`, `Glob`, `Grep`, budget 3 USD, 20 minutes: the default reviewer runs on Claude Code; opencode is an option (#36).
- After the clean replay is green, a fresh reviewer session runs in the replay's working tree (ADR 0018) with read-only tools. Its prompt holds the review instructions, the issue (untrusted data), the diff from the base commit (untrusted data), the checks' summary and the definition of done's sentence items.
- It answers `{"verdict": "go" | "no-go", "findings": [{"severity": "blocking" | "minor", "file", "line", "title", "detail"}], "definition_of_done": [{"item", "met": true | false, "evidence"}], "learnings": [...]}`. Ariane validates it itself (a small validator, no new dependency); with Claude Code it also passes `--json-schema` and reads `structured_output`. An invalid answer is retried once in a new session with the validation error; a second invalid answer stops the ticket.
- `go` with a blocking finding counts as `no-go`. A sentence item of the definition of done that is missing from the answer or `met: false` counts as a blocking finding; check items are taken from the replay's results. After the session, Ariane verifies that git, the tree and the remote did not change.
- `work/<n>/review-0.md` records the reviewed commit, the verdict, the findings, every definition-of-done item with its result, and the proposed learnings (not decided), redacted.
- On `go`, delivery continues; the pull request body carries the verdict, the definition-of-done results and a findings table when it fits in 3,000 characters, otherwise a one-line summary and the link to the review file. On `no-go` (until fix rounds exist), the ticket stops with status `needs a human` and nothing is pushed.
- The docs generator writes `docs/reference/review-answer.schema.json` from the validator's description, checked like the other references.

## Release note

Added: an adversarial review by a different model before every pull request, checking the definition of done item by item.

## Acceptance criteria

- Tests named `test_c10_review_*` with a fake runtime show: `go` delivers with the verdict in the pull request body; `go` with a blocking finding is treated as `no-go`; an invalid answer is retried once, then stops; the reviewer runs in the replay tree with read-only tools; a reviewer that edits a file is stopped; the review file is in the pushed branch; the same model for both roles is refused at load.
- Tests named `test_c26_dod_review_*` show: an item answered `met: false` or missing makes the review `no-go`; the pull request body and the review file list every item with its result.
- The recorded Claude Code session below is kept as `tests/fixtures/claude_stream_review.jsonl` (verbatim, one JSON object per line) and a test parses it through the Claude Code runtime: the answer is read from the `result` event's `structured_output`, validates, and gives `no-go` with two blocking findings and one definition-of-done item `met: false`.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c10_review` runs at least 6 tests and they pass.
- [ ] `uv run pytest -k c26_dod_review` runs at least 2 tests and they pass.
- [ ] `tests/fixtures/claude_stream_review.jsonl` is the fixture below, unchanged, and a test reads it.
- [ ] CLAUDE.md's "Developing Ariane with Ariane" says the review of tickets Ariane runs is now enforced by Ariane (C10).
- [ ] Definition of done: `docs/reference/review-answer.schema.json` generated; `docs/architecture/` updated (the new review module, `flow`, `config`, the level 3 sequence diagram).
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Fix rounds and the draft pull request (next issue), the learnings checkpoint (C18), opencode (#36).

## Related

ADR 0016, ADR 0015, ADR 0018, ADR 0023, spec C10, C26.

## Recorded fixture

Claude Code 2.1.296, on a two-commit repository where `add(a, b)` returns `a - b`:

`claude -p --output-format stream-json --verbose --model claude-opus-5-5 --tools Read Glob Grep --permission-mode bypassPermissions --strict-mcp-config --setting-sources project,local --max-budget-usd 1 --no-session-persistence --json-schema <schema>`

Observed: `--json-schema` adds a `StructuredOutput` tool to the session even though `--tools` lists only read tools (see the `init` event); the answer arrives as a `StructuredOutput` tool call and again, parsed, in the `result` event's `structured_output` (its `result` holds the same JSON as text). The fixture keeps only the fields Ariane reads; the cwd is `/work/proj` and the session id is zeroed.

<details><summary>Schema passed to --json-schema</summary>

```json
{
    "type": "object",
    "additionalProperties": false,
    "required": [
        "verdict",
        "findings",
        "definition_of_done",
        "learnings"
    ],
    "properties": {
        "verdict": {
            "type": "string",
            "enum": [
                "go",
                "no-go"
            ]
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": false,
                "required": [
                    "severity",
                    "file",
                    "line",
                    "title",
                    "detail"
                ],
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": [
                            "blocking",
                            "minor"
                        ]
                    },
                    "file": {
                        "type": "string"
                    },
                    "line": {
                        "type": "integer"
                    },
                    "title": {
                        "type": "string"
                    },
                    "detail": {
                        "type": "string"
                    }
                }
            }
        },
        "definition_of_done": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": false,
                "required": [
                    "item",
                    "met",
                    "evidence"
                ],
                "properties": {
                    "item": {
                        "type": "string"
                    },
                    "met": {
                        "type": "boolean"
                    },
                    "evidence": {
                        "type": "string"
                    }
                }
            }
        },
        "learnings": {
            "type": "array",
            "items": {
                "type": "string"
            }
        }
    }
}
```

</details>

<details><summary>tests/fixtures/claude_stream_review.jsonl</summary>

```json
{"type":"system","subtype":"init","cwd":"/work/proj","session_id":"00000000-0000-4000-8000-000000000000","tools":["Glob","Grep","Read","StructuredOutput"],"model":"claude-opus-5-5","permissionMode":"bypassPermissions","apiKeySource":"none","claude_code_version":"2.1.296"}
{"type":"assistant","message":{"model":"claude-opus-5-5","id":"msg_011CftDTzUiU1bgE2Fj8KJjA","type":"message","role":"assistant","content":[{"type":"tool_use","id":"toolu_01NprYJm94FdQiso1YxaFVQi","name":"Read","input":{"file_path":"/work/proj/calc.py"},"caller":{"type":"direct"}}],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":2,"cache_creation_input_tokens":5843,"cache_read_input_tokens":0,"output_tokens":21}},"parent_tool_use_id":null,"session_id":"00000000-0000-4000-8000-000000000000"}
{"type":"user","message":{"role":"user","content":[{"tool_use_id":"toolu_01NprYJm94FdQiso1YxaFVQi","type":"tool_result","content":"1\tdef add(a, b):\n2\t    return a - b\n3\t"}]},"parent_tool_use_id":null,"session_id":"00000000-0000-4000-8000-000000000000"}
{"type":"assistant","message":{"model":"claude-opus-5-5","id":"msg_011CftDTzUiU1bgE2Fj8KJjA","type":"message","role":"assistant","content":[{"type":"tool_use","id":"toolu_01H6ZJrexHFBiLcdMyh2k4d7","name":"Glob","input":{"pattern":"**/*","path":"/work/proj"},"caller":{"type":"direct"}}],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":2,"cache_creation_input_tokens":5843,"cache_read_input_tokens":0,"output_tokens":21}},"parent_tool_use_id":null,"session_id":"00000000-0000-4000-8000-000000000000"}
{"type":"user","message":{"role":"user","content":[{"tool_use_id":"toolu_01H6ZJrexHFBiLcdMyh2k4d7","type":"tool_result","content":".git/description\n.git/hooks/pre-applypatch.sample\n.git/hooks/pre-push.sample\n.git/hooks/sendemail-validate.sample\n.git/hooks/fsmonitor-watchman.sample\n.git/hooks/commit-msg.sample\n.git/hooks/post-update.sample\n.git/hooks/update.sample\n.git/hooks/pre-commit.sample\n.git/hooks/pre-rebase.sample\n.git/hooks/prepare-commit-msg.sample\n.git/hooks/push-to-checkout.sample\n.git/hooks/pre-merge-commit.sample\n.git/hooks/pre-receive.sample\n.git/hooks/applypatch-msg.sample\n.git/info/exclude\n.git/HEAD\n.git/config\n.git/objects/46/93ad3cf8b0903b98497fb89b8b524fbf1b93f4\n.git/objects/0b/5146d69a7f3435916ca594d9f5fe68057ea59a\n.git/objects/d8/480542e998b4b4e3bd48d29c26542260a5a398\ncalc.py\n.git/objects/58/7a9cb0dea864051245c68ffb055a5eb1e4ee65\n.git/objects/12/ee7431b8e0e3e366c904c33ef3dee767b1bc20\n.git/index\n.git/COMMIT_EDITMSG\n.git/objects/48/75a991bd9cfe99dcaed3fe6229000aaadbf2da\n.git/refs/heads/master\n.git/logs/refs/heads/master\n.git/logs/HEAD"}]},"parent_tool_use_id":null,"session_id":"00000000-0000-4000-8000-000000000000"}
{"type":"assistant","message":{"model":"claude-opus-5-5","id":"msg_011CftDUASFEmBQTKqHvDFG9","type":"message","role":"assistant","content":[{"type":"tool_use","id":"toolu_01J96z98ZZfgTmYPaexSmHhP","name":"StructuredOutput","input":{"verdict":"no-go","findings":[{"severity":"blocking","file":"calc.py","line":2,"title":"add() subtracts instead of adding","detail":"add(a, b) returns `a - b`, but the issue asks for the sum. For example, add(2, 3) returns -1 instead of 5. The fix is `return a + b`."},{"severity":"blocking","file":"calc.py","line":1,"title":"No tests accompany the change","detail":"The repository has only calc.py. There is no test file and no test for add(). Nothing would catch the wrong operator noted above."}],"definition_of_done":[{"item":"The change is covered by tests that fail without it.","met":false,"evidence":"The working tree contains only calc.py, with no test files (no test_*.py, tests/ directory or similar). Nothing exercises add(), and a correct test would currently fail because add returns a - b."}],"learnings":["The repo has a single file, calc.py, and no test infrastructure.","The add() implementation uses the wrong operator (- instead of +)."]},"caller":{"type":"direct"}}],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":2,"cache_creation_input_tokens":896,"cache_read_input_tokens":5843,"output_tokens":24}},"parent_tool_use_id":null,"session_id":"00000000-0000-4000-8000-000000000000"}
{"type":"user","message":{"role":"user","content":[{"tool_use_id":"toolu_01J96z98ZZfgTmYPaexSmHhP","type":"tool_result","content":"Structured output provided successfully"}]},"parent_tool_use_id":null,"session_id":"00000000-0000-4000-8000-000000000000"}
{"type":"result","subtype":"success","is_error":false,"result":"{\"verdict\":\"no-go\",\"findings\":[{\"severity\":\"blocking\",\"file\":\"calc.py\",\"line\":2,\"title\":\"add() subtracts instead of adding\",\"detail\":\"add(a, b) returns `a - b`, but the issue asks for the sum. For example, add(2, 3) returns -1 instead of 5. The fix is `return a + b`.\"},{\"severity\":\"blocking\",\"file\":\"calc.py\",\"line\":1,\"title\":\"No tests accompany the change\",\"detail\":\"The repository has only calc.py. There is no test file and no test for add(). Nothing would catch the wrong operator noted above.\"}],\"definition_of_done\":[{\"item\":\"The change is covered by tests that fail without it.\",\"met\":false,\"evidence\":\"The working tree contains only calc.py, with no test files (no test_*.py, tests/ directory or similar). Nothing exercises add(), and a correct test would currently fail because add returns a - b.\"}],\"learnings\":[\"The repo has a single file, calc.py, and no test infrastructure.\",\"The add() implementation uses the wrong operator (- instead of +).\"]}","structured_output":{"verdict":"no-go","findings":[{"severity":"blocking","file":"calc.py","line":2,"title":"add() subtracts instead of adding","detail":"add(a, b) returns `a - b`, but the issue asks for the sum. For example, add(2, 3) returns -1 instead of 5. The fix is `return a + b`."},{"severity":"blocking","file":"calc.py","line":1,"title":"No tests accompany the change","detail":"The repository has only calc.py. There is no test file and no test for add(). Nothing would catch the wrong operator noted above."}],"definition_of_done":[{"item":"The change is covered by tests that fail without it.","met":false,"evidence":"The working tree contains only calc.py, with no test files (no test_*.py, tests/ directory or similar). Nothing exercises add(), and a correct test would currently fail because add returns a - b."}],"learnings":["The repo has a single file, calc.py, and no test infrastructure.","The add() implementation uses the wrong operator (- instead of +)."]},"total_cost_usd":0.0686966,"usage":{"input_tokens":4,"cache_creation_input_tokens":6739,"cache_read_input_tokens":5843,"output_tokens":680},"num_turns":4,"stop_reason":"tool_use","duration_ms":6948,"permission_denials":[],"terminal_reason":"completed","session_id":"00000000-0000-4000-8000-000000000000"}
```

</details>
