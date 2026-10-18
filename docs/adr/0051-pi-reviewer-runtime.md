# 0051. The reviewer on pi

- Status: accepted
- Date: 2026-10-18
- Capabilities: C5, C10, C19

## Context
The reviewer must run on another model than the implementer (C10). The pi coding agent (`pi`, npm
package `@mariozechner/pi-coding-agent`) drives many providers (Anthropic, OpenAI, Google,
DeepSeek, OpenRouter, GitHub Copilot and others) on an API key or a subscription login, with a
non-interactive mode, a JSON Lines event stream and a tool allow list. As a reviewer runtime it
reaches models no other runtime of Ariane reaches. Ticket #182 asked for it (ADR 0015, ADR 0029,
ADR 0043). The ticket named this ADR 0045; that number was taken, so it is 0051.

## Decision
- `runtime = "pi"` is for the reviewer only; the implementer is refused with the message opencode
  and Codex get. `model` is `<provider>/<id>`. `tools` is a subset of pi's read-only tools `read`,
  `grep`, `find`, `ls`; `bash`, `edit`, `write` and any other name are refused by the config loader
  (C10). `max_tokens` is required: pi may bill per token whatever the login (its docs say a Claude
  Pro/Max login used through pi draws from extra usage, billed per token), and pi caps no cost.
- Ariane drives the official CLI only. The command (checked on pi 0.73.1 with `pi --help`, its
  bundled docs and a run without credentials): `pi -p --mode json --no-session --no-extensions
  --no-skills --no-prompt-templates --no-themes --no-context-files --offline --tools <tools>
  --model <model>`, in the review tree. The prompt (with the answer schema, as for opencode and
  Codex) goes on standard input: in print mode pi merges piped input into the prompt, which the
  run showed as the user message of the stream; no prompt file is written. `PI_TELEMETRY=0` is set
  for the process.
- Authentication. Ariane never reads, copies or logs `auth.json` or a token. With
  `[agents.reviewer].api_key_env`, that variable's value is passed to the one process under the
  provider's own variable, from pi's documented list (`anthropic` gets `ANTHROPIC_API_KEY`,
  `openrouter` `OPENROUTER_API_KEY`, ...: `config_schema.PI_PROVIDER_KEYS`); a provider outside
  that list with `api_key_env` is refused at config load, as is a small reviewer's model on such a
  provider. An unset variable is an error before pi starts. Without `api_key_env`, pi uses its own
  `auth.json`. Either way the process gets no provider key from Ariane's environment: the listed
  variables, any `*_API_KEY`, `AWS_*` and `GOOGLE_APPLICATION_CREDENTIALS` are removed, and so is
  `api_key_env` itself. The runtime's login variables are `PI_CODING_AGENT_DIR` (where pi keeps its
  settings and `auth.json`) and `api_key_env`.
- No credentials. pi 0.73.1 prints "No API key found for <provider>." on standard error (and exits
  1 when the prompt comes on standard input). With no assistant message in the stream, the session
  is an `error` with "pi has no credentials for <provider>" and the next step "run pi and /login,
  or set agents.reviewer.api_key_env"; the ticket stops with that, never a review verdict.
- Events. Each assistant `message_end` adds its `usage`: `input`, `output`, `cacheRead`,
  `cacheWrite` (recorded as input, output, cache read, cache write tokens) and `cost.total` (the
  fields of pi's `Usage`); `max_tokens`, and `max_budget_usd` against the summed reported cost,
  are applied after each one, and reaching either kills the process tree (`budget`). The summed
  cost is the session's cost when at least one message reported `cost.total` (0 included, as for
  a free model), else it stays null. The answer is
  the last assistant message of `agent_end` (else of the last `message_end`): its text blocks, from
  which the last fenced `json` block is read. An assistant message whose `stopReason` is `error` or
  `aborted` is `error`, unless an `auto_retry_start` follows and a later message succeeds; a failed
  `auto_retry_end` is `error` with its `finalError` (pi exits 0 in that case); a non-zero exit, or a
  last assistant message that did not stop with `stop`, is `error`. The duration is the flow's, as
  for every session.
- Isolation (ADR 0031, amendment #182): `.pi/` is removed from the review tree, and the guard
  watches pi's global `settings.json`, `models.json`, `AGENTS.md`, `SYSTEM.md` and
  `APPEND_SYSTEM.md`.
- `describe()` gives `pi <version>` from `pi --version`.

## Consequences
A reviewer on any provider pi supports, on an API key or a subscription, with a token cap Ariane
enforces, and the dollar cap applied to the cost pi reports (ADR 0015). Whether a pi login bills per token is not known to Ariane: `max_tokens` bounds it, and
there is no plan-only guard as for Codex (#178). The provider key list is pi 0.73.1's; a provider
added later works with pi's own login, and needs this list updated to work with `api_key_env`.
The "No API key found" wording is matched; another wording would be a plain `error`.

## Alternatives considered
- The prompt as an `@file` outside the tree: not needed, since pi reads standard input in print
  mode; a file would be one more thing to write and remove.
- `--no-tools` and the diff alone in the prompt: rejected, the reviewer reads the tree (C10).
- Passing the key under every provider variable: rejected, the process gets one key, for its
  provider only.
- Reading `auth.json` to check the login: rejected, Ariane must not hold the credentials.
