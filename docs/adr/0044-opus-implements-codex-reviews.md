# 0044. Ariane's own tickets: Opus implements, Codex reviews

- Status: accepted
- Date: 2026-10-17
- Capabilities: C5, C10

## Context
Ariane's own `ariane.toml` had Sonnet implement and Opus review, since the reviewer must run on a different model from the implementer (C10). With the Codex reviewer runtime (ADR 0043), the strongest Claude model can implement while a strong model from another vendor reviews, on the owner's ChatGPT plan rather than per-token billing.

## Decision
- Implementer: `claude-code`, `claude-opus-5-5`, `max_budget_usd = 10.0` (Opus costs more per token than Sonnet; a session stopped by its budget loses the ticket).
- Reviewer: `runtime = "codex"`, `model = "gpt-6-astra"`, with no `api_key_env`: it runs on the CLI's own login, and the OpenAI key variables of Ariane's environment are removed from its process (ADR 0043), so an `OPENAI_API_KEY` in the environment is never used. A machine that runs Ariane's own tickets needs `codex login --device-auth` with the ChatGPT account first; otherwise the ticket stops with "Codex is not logged in".
- `max_tokens = 2000000` on the reviewer. Ariane does not refuse a CLI that is logged in with an API key: that session is recorded as `billing: api` and billed per token, and the token cap bounds it. A review measured about 120,000 tokens (on a plan login, at no cost), so the cap does not stop a normal review.

## Consequences
Every ticket of Ariane's own repository needs the Codex CLI installed and logged in with ChatGPT; the plan is used only as long as that login is a ChatGPT one (an API-key login is billed per token, up to `max_tokens`). Refusing an API-key login outright would need a runtime option, which this ADR does not add. A plan usage limit stops the ticket with `quota` (ADR 0043) instead of a review. Implementer sessions cost more than with Sonnet.

## Alternatives considered
- Opus implements and Opus reviews in a separate session: refused by the config loader (C10); the same model shares the same blind spots.
- Opus implements, Sonnet reviews: a weaker reviewer than the implementer.
- `gpt-6.1-sol` as the reviewer: also accepted on the plan; `gpt-6-astra` is the one the owner chose.
