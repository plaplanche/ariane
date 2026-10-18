# Module `ariane.config_schema`

The description of `ariane.toml` as a JSON Schema, and the runtimes each role may use (C22, C5). `config.parse` is the validation; a test checks that both agree.

## Public API

| Name | Kind | What it does |
| --- | --- | --- |
| `CLAUDE_CODE` | constant | The runtime name `claude-code`. |
| `OPENCODE` | constant | The runtime name `opencode`. |
| `RUNTIMES` | constant | The runtimes allowed per role: `claude-code` for both, `opencode`, `codex` and `pi` for the reviewer only (ADR 0029, ADR 0043, ADR 0051). |
| `CODEX` | constant | The runtime name `codex`, for the reviewer only (ADR 0043); the agent schema gains the optional `api_key_env`. |
| `PI` | constant | The runtime name `pi`, for the reviewer only (ADR 0051). |
| `OPENCODE_TOOLS` | constant | The tools of an opencode agent: `read`, `glob`, `grep`. |
| `PI_TOOLS` | constant | The tools of a pi reviewer, its read-only ones: `read`, `grep`, `find`, `ls` (C10). |
| `PI_PROVIDER_KEYS` | constant | pi's documented provider key variables, by provider (`anthropic`: `ANTHROPIC_API_KEY`, ...), from pi 0.73.1's provider list. |
| `agent_problem(role, runtime, model, tools, api_key_env, max_tokens)` | function | The first runtime rule an `[agents.<role>]` table breaks, as `(key, message)`, or None: `api_key_env` only with `codex` or `pi` and with `max_tokens`; opencode and pi tools from their own list, a valid `model` and `max_tokens` set; a Claude Code or Codex reviewer's tools within `REVIEWER_TOOLS`; no `Skill`. `config.parse` raises it. |
| `model_problem(runtime, model, api_key_env)` | function | For opencode and pi, `<provider>/<model>`; for pi with `api_key_env`, a provider in `PI_PROVIDER_KEYS`; None when the model is fine. |
| `REVIEWER_TOOLS` | constant | The tools a Claude Code reviewer may be given: `Read`, `Glob`, `Grep` (ADR 0031). |
| `SCHEMA` | constant | The JSON Schema of the file, with `checks[].not_run_locally` (ADR 0042), written to `docs/reference/ariane.toml.schema.json` by `scripts/generate_docs.py`. |

## Behaviour and errors

- Reads and writes no file itself; `scripts/generate_docs.py` writes `SCHEMA` to `docs/reference/ariane.toml.schema.json`.
- The reviewer, the only role that may run on opencode or pi, carries an `if`/`then` that requires `max_tokens` when `runtime` is `opencode` or `pi`, as `config.parse` does; the implementer has none.
- The reviewer alone accepts the optional `small` object (`[agents.reviewer.small]`, ADR 0046): required `max_lines` (positive integer), optional `model`, `max_budget_usd`, `max_tokens`, `timeout_minutes`, no other key.
- The reviewer also carries an `if`/`then` limiting a Claude Code reviewer's `tools` to `REVIEWER_TOOLS` (ADR 0031), and one limiting a pi reviewer's `tools` to `PI_TOOLS` (ADR 0051).
- `agents.<role>.idle_minutes` is an optional positive number (ADR 0045); that it is below `timeout_minutes` is checked by `config.parse` only.
- `checks[].setup` is an optional argument list.
- `project.env` is an optional list of non-empty strings, default `[]` (ADR 0024).
- Raises nothing.

## Workflow

This module declares constants and the schema built from them; `agent_problem` and `model_problem` only compare their arguments with those constants.

## Code view (C4 level 4)

```mermaid
classDiagram
class config_schema {
  <<module>>
  CLAUDE_CODE str
  OPENCODE str
  CODEX str
  PI str
  RUNTIMES dict
  OPENCODE_TOOLS tuple
  PI_TOOLS tuple
  PI_PROVIDER_KEYS dict
  agent_problem() tuple
  model_problem() str
  REVIEWER_TOOLS tuple
  SCHEMA dict
}
class config
config ..> config_schema : SCHEMA, RUNTIMES, agent_problem
class pi
pi ..> config_schema : PI_PROVIDER_KEYS
```

## Collaborations

Arrows go from the importing module to the imported module; a dashed arrow is an import for type checking only.

<!-- generated: collaborations -->
```mermaid
flowchart LR
  config --> config_schema
  pi --> config_schema
```
<!-- end generated -->

## Serves

C22, C5; ADR 0003, ADR 0022, ADR 0029, ADR 0031. See [the component view](../3-components.md).
