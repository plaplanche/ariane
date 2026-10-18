# Product brief: pi as a reviewer runtime: a read-only pi session on any provider, with a token cap (C5, C10)

- Source: issue #182 (https://github.com/plaplanche/ariane/issues/182)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The reviewer must run on a different model from the implementer (C10). Ariane's reviewer runtimes today are Claude Code, opencode (ADR 0029) and Codex (ADR 0043). The pi coding agent (`pi`, npm package `@mariozechner/pi-coding-agent`) is a CLI that drives many providers (Anthropic, OpenAI, Google, DeepSeek, OpenRouter, GitHub Copilot and others), on an API key or on a subscription login, with a non-interactive mode, a JSON Lines event stream and a tool allow list. As a reviewer runtime it gives Ariane access to models no other runtime reaches. Spec: C5 (runtimes), C10 (reviewer), C19 (metrics); ADR 0015 (runtime-neutral contract), ADR 0029 (opencode), ADR 0031 (reviewer isolation), ADR 0043 (Codex).

## Current state

- `src/ariane/config_schema.py:8-11`: `OPENCODE`, `CODEX`, `RUNTIMES = {"implementer": (CLAUDE_CODE,), "reviewer": (CLAUDE_CODE, OPENCODE, CODEX)}`.
- `src/ariane/opencode.py` and `src/ariane/codex.py` are the templates for a reviewer-only runtime: `command`, `environment`, `describe`, `run` returning a `SessionResult`, an `Events` parser of JSON Lines that applies `max_tokens`.
- `src/ariane/git.py:163-165` (`INSTRUCTION_FILES`, `INSTRUCTION_DIRS`) and `:210-228` (instruction files outside the tree, per runtime): what the reviewer tree is stripped of and what the guard watches (ADR 0031).

## Verified on pi 0.73.1 (`pi --help` and its bundled docs, 17 October 2026)

- Non-interactive: `pi -p` (`--print`), prompt as a message argument or `@file`; `--mode json` prints JSON Lines on standard output.
- Model: `--model <provider>/<id>` (or `--provider` and `--model`); `--list-models [search]`.
- Tools: `--tools read,grep,find,ls` is a read-only allow list (pi's own example for a review); `--no-tools` disables all. `bash`, `edit` and `write` are the writing tools.
- Isolation flags: `--no-session` (ephemeral), `--no-extensions`, `--no-skills`, `--no-prompt-templates`, `--no-themes`, `--no-context-files` (no `AGENTS.md` / `CLAUDE.md` discovery), `--offline` (no startup network operations, same as `PI_OFFLINE=1`); `PI_TELEMETRY=0` disables install telemetry.
- Configuration: `PI_CODING_AGENT_DIR` (default `~/.pi/agent`) holds settings and `auth.json`; a project `.pi/` folder can hold settings and extensions.
- Authentication: provider variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`, and more) or `auth.json`, filled by `/login` in interactive mode with an API key or a subscription (ChatGPT Plus/Pro, Claude Pro/Max, GitHub Copilot). Pi's docs warn that Claude Pro/Max used through pi draws from extra usage, billed per token.
- JSON events seen without credentials: a first line `{"type":"session","version":3,"id":...,"timestamp":...,"cwd":...}`; with no key the process prints "No API key found for <provider>." and exits 0. Documented events: `agent_start`, `turn_start`, `message_start` / `message_update` / `message_end` (an `AgentMessage`), `tool_execution_start` / `_update` / `_end`, `turn_end`, `agent_end` (all messages), `auto_retry_start` / `_end`, `compaction_start` / `_end`.

## Decided spec

- **New runtime `pi`, reviewer role only**, as opencode and Codex were first: `PI = "pi"` in `config_schema.py`, allowed in `RUNTIMES["reviewer"]`; `runtime = "pi"` for the implementer is refused with the message opencode and Codex get. The generated schema and `docs/ariane.example.toml` gain it. `model` is `<provider>/<id>`.
- **`src/ariane/pi.py`**, modelled on `codex.py`:
  - The session runs the official CLI only: `pi -p --mode json --no-session --no-extensions --no-skills --no-prompt-templates --no-themes --no-context-files --offline --tools read,grep,find,ls --model <model>`, in the review tree, the prompt on standard input if pi reads it there, else as an `@file` outside the tree (the implementer confirms which with the installed version and records it in the ADR). `PI_TELEMETRY=0` is set for the process. `tools` in `[agents.reviewer]` must be a subset of `read,grep,find,ls`; `bash`, `edit` and `write` are refused by the config loader (C10).
  - Authentication: Ariane never reads, copies or logs `auth.json` or a token. If `[agents.reviewer].api_key_env` names a variable, its value is passed to that one process under the provider's own variable name (the implementer maps the provider of `model` to it from pi's documented list; an unknown provider with `api_key_env` is refused at config load); otherwise the process gets no provider key variable from Ariane's environment and uses pi's `auth.json`. `max_tokens` is required for `runtime = "pi"`, since pi may bill per token whatever the login.
  - No credentials: when pi prints "No API key found for <provider>", the session does not count as a review; the ticket stops with "pi has no credentials for <provider>; Next: run pi and /login, or set agents.reviewer.api_key_env".
  - `describe()` returns `pi <version>` from `pi --version`.
  - The event parser takes the reviewer's final answer from the last assistant message of `agent_end` (or the last `message_end`), the token counts from each assistant message's usage (the implementer records the fields seen), applies `max_tokens` after each `message_end`, and records the duration and stop reason; a `cost` reported by pi is recorded as the session's cost, else it stays null. A failed `auto_retry_end` or an error message is `error`.
- **Reviewer isolation (ADR 0031):** `.pi` joins `INSTRUCTION_DIRS` (stripped from the review tree), and the guard watches `<PI_CODING_AGENT_DIR or ~/.pi/agent>/settings.json` and its `AGENTS.md` / `SYSTEM.md` if present, as for opencode and Codex.
- **ADR 0045** (number to confirm at merge): the pi reviewer runtime, the exact command, the authentication modes and why `max_tokens` is required, the isolation flags.

## Release note

Added: `runtime = "pi"` for the reviewer: a read-only `pi` session on any provider pi supports, with an API key or pi's own login, and a token cap.

## Acceptance criteria

- Tests named `test_c5_pi_*`, with a fake `pi` executable on `PATH` that prints recorded JSON Lines, show:
  - a review answered through the fake CLI, settled like any other review, with the tokens, cost when given, and duration recorded;
  - the command holds the read-only tool list, every isolation flag above, `--no-session` and the model; `bash`, `edit` or `write` in `tools` is refused by the config loader;
  - with `api_key_env` set, only the provider's variable is set for that process; without it, no provider key variable from Ariane's environment reaches the process;
  - "No API key found" stops the ticket with the credentials message and no review verdict;
  - `max_tokens` stops the session and the process tree;
  - `runtime = "pi"` for the implementer, and `runtime = "pi"` without `max_tokens`, are refused by the config loader;
  - a `.pi/` folder in the tree is not in the reviewer's tree, and a change to pi's `settings.json` during a session is a guard violation.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c5_pi` runs at least 7 tests and they pass.
- [ ] ADR 0045 (or the next free number) is in `docs/adr/`; ADR 0031 has an amendment for `.pi`.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): new `docs/architecture/modules/pi.md`; `docs/architecture/modules/config.md`, `config_schema.md`, `git.md`, `runtime.md`, `review_session.md`; `docs/architecture/2-containers.md` (pi CLI as an external system); `docs/reference/` and `docs/logs.md` regenerated; README's paragraph on runtimes, with how to install pi, log in and keep `auth.json` private.

## Out of scope

- pi as the implementer runtime.
- Which provider and model Ariane's own `ariane.toml` uses for its reviewer (an owner decision, after this ticket).
- A guard that refuses a subscription login billed per token (as #178 does for Codex): pi does not say how it bills; `max_tokens` bounds it.

## Related

ADR 0015, ADR 0029, ADR 0031, ADR 0043; spec C5, C10, C19; #157, #178.
