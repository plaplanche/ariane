# Module `ariane.claude_code`

Claude Code as an agent runtime: it starts the `claude` CLI for one session and turns its structured output into a `SessionResult`.

## Public API

| Name | Kind | What it does |
| --- | --- | --- |
| `DENIED_TOOLS` | constant | The shell commands denied to the agent: first layer of the push guard (`git push`, `checkout`, `switch`, `rebase`, `reset`, `gh`). |
| `schema_argument(schema)` | function | The session's schema as given to `--json-schema`, without its `$schema` key. |
| `ClaudeCodeRuntime` | class | `ClaudeCodeRuntime(executable=("claude",))` implements `AgentRuntime`; it declares `ANTHROPIC_` and `CLAUDE_` as its login variables; `command(session)` builds the command line, `run(session)` runs it. |
| `TokenTally` | class | `TokenTally(max_tokens)`: the running token total of a stream (`parts`, `total`), fed by `add_line(line)`; `stopped_result()` is the result when the cap was reached. |
| `parse_result(stdout, stderr, returncode)` | function | Maps the final `result` event (or a single JSON result), stderr and the exit code to a `SessionResult` and a stop reason; a stream without a result is `error`. |

## Behaviour and errors

- It reads `--output-format stream-json --verbose` line by line, counts tokens per `message.id` (the latest usage of each id counts once) and stops the session when the total reaches `Session.max_tokens` (stop reason `budget`, "stopped by Ariane at <n> tokens"); `--max-budget-usd` stays the runtime's own cost cap, and `SessionResult.cap` names the cap that applied.
- A session with a `json_schema` passes it to `--json-schema` without its `$schema` key (Claude Code rejects the draft 2020-12 identifier) and gets the parsed answer back in `SessionResult.structured_output`.
- A `reviewer` session (ADR 0031) starts with `--restricted` and one `--add-dir` per `Session.add_dirs`, from an empty working directory, with no `--permission-mode bypassPermissions` and no `--setting-sources`; every other role keeps `bypassPermissions` and `--setting-sources project,local`.
- Attempts (C19, ADR 0036): `TokenTally` also reads the `tool_use` blocks of the assistant messages and counts, once per block id, the `Bash` commands that push or open a pull request (`attempts` module); `run` puts the counts on `SessionResult.attempts`, whatever the stop reason.
- Errors become a `SessionResult` with stop reason `error` (or `timeout`); none is raised.

## Workflow

```mermaid
flowchart TD
A[Session] --> B[command: claude CLI arguments]
  B --> C[process: run and read lines]
  C --> D[TokenTally.add_line: tokens and attempts]
  D -->|cap reached| E[stop the process: budget]
  D -->|stream ends| F[parse_result]
  E --> G[SessionResult]
  F --> G
```

## Code view (C4 level 4)

```mermaid
classDiagram
class ClaudeCodeRuntime {
  name str
  login_variables tuple
  command(session) list
  run(session) SessionResult
}
class TokenTally {
  max_tokens int
  attempts AttemptTally
  parts tuple
  total int
  add_line(line) bool
  stopped_result() SessionResult
}
ClaudeCodeRuntime ..|> AgentRuntime
ClaudeCodeRuntime --> TokenTally
ClaudeCodeRuntime ..> parse_result
ClaudeCodeRuntime ..> schema_argument
TokenTally --> AttemptTally
```

## Collaborations

Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only.

<!-- generated: collaborations -->
```mermaid
flowchart LR
  claude_code --> attempts
  claude_code --> process
  claude_code --> runtime
  cli --> claude_code
```
<!-- end generated -->

## Serves

C5, C10; ADR 0007, ADR 0015, ADR 0016, ADR 0036. See [the component view](../3-components.md).
