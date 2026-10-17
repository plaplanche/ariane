# Product brief: Codex reviewer: without api_key_env, run only on a ChatGPT login (C5, C10)

- Source: issue #178 (https://github.com/plaplanche/ariane/issues/178)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Without `api_key_env`, the Codex reviewer runs on whatever the CLI is logged in with (ADR 0043). When `codex login status` reports an API-key login rather than ChatGPT, `CodexRuntime.run` records `billing: api` and starts `codex exec`, billed per token. `max_tokens` does not bound that: Codex reports usage only when a turn completes, so a single turn can go far past the cap before Ariane checks it. A setup that means to use a ChatGPT plan (no `api_key_env`) must never bill per token. Found by the reviewer when Ariane's own config was switched to a Codex reviewer (branch `claude/opus-codex-agents`, two `no-go` reviews). Spec: C5 (runtimes), C10 (reviewer), C19 (billing in metrics); ADR 0043.

## Current state

- `src/ariane/codex.py` `login()` returns `none`, `chatgpt`, `api` or an error from `codex login status`; `run()` (around line 95) accepts `api` without `api_key_env` and sets `billing = API`.
- `tests/test_c5_codex.py:134` `test_c5_codex_an_api_key_login_is_billed_per_token_not_by_plan` asserts that path runs.

## Decided spec

- **Without `api_key_env`, only a ChatGPT login runs.** When `codex login status` says the CLI is logged in but not with ChatGPT, the session does not start (no `codex exec` process) and the ticket stops with: "Codex is logged in with an API key, not ChatGPT; Next: run codex login --device-auth with the ChatGPT account, or set agents.reviewer.api_key_env". It is a stop, never a review verdict.
- **Per-token billing only on request.** `api_key_env` stays the only way to run a per-token Codex review (it already requires `max_tokens`).
- ADR 0043 amendment: plan login only without `api_key_env`; why (usage arrives at the end of a turn, so `max_tokens` cannot bound a per-token turn).
- README, "Reviewer on Codex": say that without `api_key_env` the CLI must be logged in with ChatGPT, and what happens otherwise.

## Release note

Changed: without `api_key_env`, the Codex reviewer runs only on a ChatGPT login; a CLI logged in with an API key stops the ticket instead of billing per token.

## Acceptance criteria

- Tests named `test_c5_codex_plan_only_*`, with the fake `codex` executable, show:
  - an API-key login without `api_key_env` stops the session before any `codex exec` runs, with the message above, and no review verdict is recorded;
  - a ChatGPT login runs the review as today, with `billing: plan`;
  - with `api_key_env` set, the review runs per token as today (`billing: api`).
- `test_c5_codex_an_api_key_login_is_billed_per_token_not_by_plan` is replaced by the first test above.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c5_codex_plan_only` runs at least 3 tests and they pass.
- [ ] ADR 0043 has the amendment.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/codex.md`; README's "Reviewer on Codex"; `docs/logs.md` regenerated if a log line changes.

## Out of scope

- Switching Ariane's own `ariane.toml` to a Codex reviewer (done by hand after this ticket, branch `claude/opus-codex-agents`).
- A token cap that acts before a turn completes.

## Related

ADR 0043; spec C5, C10, C19; #157 (PR #177).
