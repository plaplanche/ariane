# 0044. Ariane's own tickets: Opus implements, Codex reviews

- Status: accepted
- Date: 2026-10-17
- Capabilities: C5, C10

## Context
Ariane's own `ariane.toml` had Sonnet implement and Opus review, since the reviewer must run on a different model from the implementer (C10). With the Codex reviewer runtime (ADR 0043), the strongest Claude model can implement while a strong model from another vendor reviews, on the owner's ChatGPT plan rather than per-token billing.

## Decision
- Implementer: `claude-code`, `claude-opus-5-5`, `max_budget_usd = 10.0` (Opus costs more per token than Sonnet; a session stopped by its budget loses the ticket).
- Reviewer: `runtime = "codex"`, `model = "gpt-6-astra"`, with no `api_key_env`: it runs only on the CLI's ChatGPT login (#178). The OpenAI key variables of Ariane's environment are removed from its process (ADR 0043), so an `OPENAI_API_KEY` in the environment is never used, and a CLI logged in with an API key stops the ticket instead of billing per token. A machine that runs Ariane's own tickets needs `codex login --device-auth` with the ChatGPT account first; with no login at all the ticket stops with "Codex is not logged in".

## Consequences
Every ticket of Ariane's own repository needs the Codex CLI installed and logged in with ChatGPT; a usage limit of the plan stops the ticket with `quota` (ADR 0043) instead of a review. Implementer sessions cost more than with Sonnet.

## Alternatives considered
- Opus implements and Opus reviews in a separate session: refused by the config loader (C10); the same model shares the same blind spots.
- Opus implements, Sonnet reviews: a weaker reviewer than the implementer.
- `gpt-6.1-sol` as the reviewer: also accepted on the plan; `gpt-6-astra` is the one the owner chose.
