# 0015. Runtime-neutral agent contract

- Status: accepted
- Date: 2026-10-08
- Capabilities: C5, C6, C10, C21, C22

## Context
ADR 0007 delegates three guarantees to Claude Code flags: the budget cap
(`--max-budget-usd`), the stop reason (the result's `subtype`) and, in ADR 0010, the validity
of the reviewer's answer (`--json-schema`). ADR 0014 makes vendor independence a requirement,
and the second runtime, opencode, has none of these flags. `context.py` also keeps the agent's
login by prefix (`ANTHROPIC_*`, `CLAUDE_*`) and strips any other name containing `API_KEY`, so
another provider's key would be removed.

## Decision
**Ariane enforces, a runtime helps.** For every runtime:
- **Budget cap.** Where the runtime reports usage as a stream, Ariane reads it while the session
  runs and stops the process (whole process tree) when the reported cost, or the reported
  tokens when no cost is reported, reach the session's cap; the stop reason is `budget`. Where
  the runtime reports usage only at the end, Ariane cannot stop it in time: it relies on the
  runtime's own cap if there is one, and refuses the runtime for a role that needs a cap if
  there is none. The journal says which of the two applied.
- **Structured answers.** Ariane validates a role's answer (for example the reviewer's verdict
  and findings) against the role's schema itself. A runtime's native schema option is used
  when it exists, as an optimisation; an answer that fails Ariane's validation is an error,
  whatever the runtime said.
- **Stop reason.** Each runtime adapter maps the runtime's own signals (result fields, events,
  exit code, Ariane's own stop for budget or time) to `finished`, `budget`, `turns`,
  `timeout` or `error`.
- **Tokens** are recorded as input, output, cache read and cache write, as reported; cost as
  reported, `null` when the runtime reports none.
- **Login variables.** Each runtime declares the variable names it keeps for its login (exact
  names or prefixes). Everything else that looks like a credential is stripped, as in ADR 0007.
  The keep list of the runtime in use replaces the hard-coded `ANTHROPIC_*` and `CLAUDE_*`.
- **Project instructions and skills.** A runtime that loads instructions or skills on its own
  is configured so that only what the project declares loads (C6, C22); where a runtime cannot
  be configured that way, it is refused for the role.

**Claude Code 2.1.292** (checked 2026-10-08):
- `claude -p --output-format stream-json --verbose` emits one `assistant` event per message
  with `usage` (tokens) and a final `result` event with `total_cost_usd`: Ariane can stop on a
  token cap while the session runs; a cost cap is enforced by `--max-budget-usd` only.
- `usage` reports `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens` and
  `output_tokens` separately (probe: `claude -p --output-format json`, prompt "Say ok.").
- `--json-schema <schema>` returns the validated answer in the result's `structured_output`.

**opencode 1.18.35** (installed with `npm install -g opencode-ai@1.18.35`, checked
2026-10-08; its documentation read from its source repository's docs pages, the website
being unreachable from the cloud sandbox):
- `opencode run --help`: `--format json` (raw JSON events), `--model`, `--agent`, `--pure`,
  `--auto`; no budget, schema or tool option on the command line.
- Usage while running: with a local OpenAI-compatible test server as provider
  (`OPENCODE_CONFIG_CONTENT` declaring it, `opencode run --pure --format json -m fake/m`),
  each `step_finish` event carries `tokens` (`input`, `output`, `reasoning`,
  `cache.read`, `cache.write`) and `cost`. The cost is computed by opencode from its model
  price list (it was 0.001005 for the configured prices), so it is the runtime's figure, not a
  provider bill. A second model call that names the session ("title") reports no usage.
  Errors arrive as `{"type": "error"}` events; there is no final result event.
- Tool restriction per role: an agent in the configuration has a `permission` map (`allow`,
  `ask`, `deny` per tool and per bash command pattern) and `steps` (iteration cap). The default
  agent allows everything (`opencode debug agent build` shows `"*": allow`). Configuration
  given inline (`OPENCODE_CONFIG_CONTENT`) is applied after the repository's `opencode.json`
  and wins (`opencode debug agent reviewer` with both). What an `ask` does with no human is not
  documented, so Ariane only uses `allow` and `deny`.
- It reads `CLAUDE.md` when no `AGENTS.md` exists and loads `~/.claude/skills` and
  `.claude/skills` (`opencode debug skill` lists them); `OPENCODE_DISABLE_CLAUDE_CODE=1`
  removes the `.claude` skills and prompt.
- Plugins under `.opencode/plugins/` in the working tree run code in opencode's process (a
  probe plugin wrote a marker file); `--pure` prevents it (no marker).

So an opencode adapter runs `opencode run --pure --format json --agent ariane-<role>` with
the role's agent given inline (permissions, steps), `OPENCODE_DISABLE_CLAUDE_CODE=1` unless
the project declares otherwise, its own budget stop on `step_finish` costs, and its own
validation of the reviewer's answer.

This decision supersedes the "Agent runtime" part of ADR 0007 and the structured-answer part
of ADR 0010; the rest of ADR 0007 stands.

## Consequences
Adding a runtime means writing an adapter (command, event parser, login variables, ways to
restrict tools and skills) and recorded fixtures; the flow does not change. A cost cap on
Claude Code stays enforced by its flag until it streams cost.

## Alternatives considered
- Keep delegating to Claude Code flags: simplest, but no second runtime could honour the
  contract.
- Estimate cost from tokens and a price list in Ariane: C5 and C19 forbid estimates.
