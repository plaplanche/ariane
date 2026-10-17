# Product brief: Codex as a reviewer runtime: read-only codex exec on a ChatGPT plan or an API key, with a quota stop (C5, C10)

- Source: issue #157 (https://github.com/plaplanche/ariane/issues/157)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Ariane's reviewer must run on a different model from the implementer (C10). To let the implementer use the strongest Claude model, the reviewer needs another strong model; OpenAI's Codex CLI can run one in a read-only, non-interactive session (`codex exec`), and it can bill the owner's ChatGPT subscription instead of per-token API usage. OpenAI documents both modes for automation: an API key (recommended for most CI) and a ChatGPT-managed account on trusted private infrastructure (`~/.codex/auth.json`, created by `codex login`, refreshed by Codex, treated like a password). The benchmark (`docs/benchmark.md`, #130) will compare "Claude implements, a Codex model reviews" with today's setups. Spec: C5 (runtimes), C10 (reviewer), C19 (metrics); ADR 0015 (runtime-neutral contract), ADR 0029 (opencode reviewer).

## Current state

- Runtimes are declared in `src/ariane/config_schema.py:7-10`: `CLAUDE_CODE = "claude-code"`, `OPENCODE = "opencode"`, `RUNTIMES = {"implementer": (CLAUDE_CODE,), "reviewer": (CLAUDE_CODE, OPENCODE)}`.
- `src/ariane/config.py:253-281` reads `[agents.<role>]` (`runtime`, `model`, `tools`, `max_budget_usd`, `timeout_minutes`, `max_tokens`) and has opencode-specific branches (`:257`, `:267`, `:269`).
- `src/ariane/opencode.py` is the template for a reviewer-only runtime: `OpenCodeRuntime` with `command`, `environment`, `describe` (`opencode --version`) and `run` returning a `SessionResult`; an `Events` parser reads its JSON events and applies Ariane's token cap (`:141-250`).
- `src/ariane/runtime.py:14-19`: `StopReason` is `finished`, `budget`, `turns`, `timeout`, `error`; nothing describes a subscription quota being exhausted.
- `src/ariane/review_session.py:87`, `:167-172`: runtime-specific wording of the cost cap.

## Decided spec

- **New runtime `codex`, reviewer role only** (as opencode was first): `CODEX = "codex"` in `config_schema.py`, allowed in `RUNTIMES["reviewer"]`; `runtime = "codex"` for the implementer is refused with the same message opencode gets today. The generated schema and `docs/ariane.example.toml` gain it.
- **`src/ariane/codex.py`**, modelled on `opencode.py`:
  - The session runs the official CLI only: `codex exec` in the review tree, non-interactive, JSON Lines output, the read-only sandbox, the configured `model`, the prompt passed on standard input. The implementer confirms the exact flags with `codex exec --help` of the installed version and records them in the ADR.
  - Ariane never reads, copies or logs `~/.codex/auth.json` or any token. Authentication is whatever the CLI is logged in with; if `[agents.reviewer].api_key_env` names a variable, its value is passed as `CODEX_API_KEY` to that one process only (never set job-wide), otherwise no OpenAI key is put in the environment: `OPENAI_API_KEY`, `CODEX_API_KEY` and any other OpenAI key variable inherited from Ariane's own environment are removed from the process's environment, so a plan-billed setup can never fall back to per-token billing by accident. If the CLI is not logged in (`codex login status` or the equivalent the implementer finds in `codex --help` says so) and no `api_key_env` is set, the session does not start: the ticket stops with "Codex is not logged in; Next: run codex login, or set agents.reviewer.api_key_env".
  - `describe()` returns `codex <version>` from `codex --version`.
  - The event parser takes the reviewer's final answer, the token counts reported when a turn completes, the duration and the stop reason; `max_tokens` is applied as for opencode.
- **Quota stop.** A new `StopReason.QUOTA = "quota"`. When Codex reports a usage limit, the session stops with `quota`; the journal entry names the runtime and, if Codex gives it, the time the limit resets. The ticket stops with a clear status ("reviewer quota reached; Next: restart the ticket after <time>"), never a no-go.
- **Cost.** When the CLI is logged in with a ChatGPT account (no `api_key_env`), the session's `cost_usd` is recorded as 0 and the session gets `"billing": "plan"`; with an API key, `"billing": "api"` and the cost stays unknown (null) unless Codex reports it. `ariane report` shows the plan-billed sessions as "covered by plan" instead of a dollar amount.
- **ADR 0042** (number to confirm at merge): the Codex reviewer runtime, the two authentication modes and why Ariane only drives the official CLI, the quota stop, plan billing in metrics.

## Verified on a ChatGPT Plus account (codex-cli 0.163.0, 17 October 2026)

- Login: `codex login --device-auth` (device-code login must be enabled in the ChatGPT account's security settings); `codex login status` prints `Logged in using ChatGPT` or `Not logged in`. The credentials are in `~/.codex/auth.json` (mode 600).
- Command that works for a read-only review, prompt on standard input: `codex exec --json --sandbox read-only --skip-git-repo-check --ephemeral -m <model> -C <tree> -`.
- JSON Lines events seen: `thread.started` (`thread_id`), `turn.started`, `item.started` / `item.completed` with `item.type` `agent_message` (`text`) or `command_execution` (`command`), `turn.completed` with `usage` = `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`, `reasoning_output_tokens`, and `turn.failed` with an `error` object (an unsupported model gives a 400 `invalid_request_error` there). The model is not echoed in the events: record the configured one.
- Models accepted on that plan: `gpt-6-astra` and `gpt-6.1-sol`; `gpt-5.6` is refused with Codex.
- A small review (a 118-line diff) used 64,747 input tokens (58,752 cached) and 322 output tokens.

## Release note

Added: `runtime = "codex"` for the reviewer: a read-only `codex exec` session, on a ChatGPT plan or an API key, with a clear stop when the plan's quota runs out.

## Acceptance criteria

- Tests named `test_c5_codex_*`, with a fake `codex` executable on `PATH` that prints recorded JSON Lines, show:
  - a review answered through the fake CLI, settled like any other review, with the tokens and duration recorded;
  - the command holds the read-only sandbox, the model and no write permission; the prompt goes on standard input;
  - with `api_key_env` set, `CODEX_API_KEY` is set for that process only; without it, no OpenAI key is in the process environment even when `OPENAI_API_KEY` is set in Ariane's own environment;
  - not logged in and no `api_key_env`: the session does not start and the ticket stops with the login message;
  - a usage-limit event stops the session with `quota`, the ticket stops with the quota status, and no review verdict is recorded;
  - `max_tokens` stops the session as for opencode;
  - `runtime = "codex"` for the implementer is refused by the config loader.
- `ariane report` shows plan-billed sessions as covered by plan.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c5_codex` runs at least 6 tests and they pass.
- [ ] ADR 0042 (or the next free number) is in `docs/adr/`.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): new `docs/architecture/modules/codex.md`; `docs/architecture/modules/runtime.md`, `config.md`, `review_session.md`, `metrics.md`, `report.md`; `docs/architecture/2-containers.md` (Codex CLI as an external system); `docs/reference/` and `docs/logs.md` regenerated; README's paragraph on runtimes, with how to log in (`codex login`) and the warning to keep `auth.json` private.

## Out of scope

- Codex as the implementer runtime.
- Reading or refreshing Codex credentials by Ariane itself.
- Waiting for a quota reset and resuming automatically (restart is #140).

## Related

#130 (benchmark), #139 (token caps), #140 (restart a stopped ticket), #137 (review sized to the change); ADR 0015, ADR 0029; spec C5, C10, C19.


---
_Generated by [Claude Code](https://claude.ai/code)_
