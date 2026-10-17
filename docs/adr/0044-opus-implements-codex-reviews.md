# 0044. Ariane's own tickets: Opus implements, Codex reviews

- Status: accepted
- Date: 2026-10-17
- Capabilities: C5, C10

## Context
Ariane's own `ariane.toml` had Sonnet implement and Opus review, since the reviewer must run on a different model from the implementer (C10). With the Codex reviewer runtime (ADR 0043), the strongest Claude model can implement while a strong model from another vendor reviews, on the owner's ChatGPT plan rather than per-token billing.

## Decision
- Implementer: `claude-code`, `claude-opus-5-5`, `max_budget_usd = 10.0` (Opus costs more per token than Sonnet; a session stopped by its budget loses the ticket).
- Reviewer: `runtime = "codex"`, `model = "gpt-6-astra"`, with no `api_key_env`: it runs on the CLI's ChatGPT login and never falls back to an API key. A machine that runs Ariane's own tickets needs `codex login` first; otherwise the ticket stops with "Codex is not logged in".

## Consequences
Every ticket of Ariane's own repository needs the Codex CLI installed and logged in. A plan usage limit stops the ticket with `quota` (ADR 0043) instead of a review. Implementer sessions cost more than with Sonnet.

## Alternatives considered
- Opus implements and Opus reviews in a separate session: refused by the config loader (C10); the same model shares the same blind spots.
- Opus implements, Sonnet reviews: a weaker reviewer than the implementer.
- `gpt-6.1-sol` as the reviewer: also accepted on the plan; `gpt-6-astra` is the one the owner chose.
