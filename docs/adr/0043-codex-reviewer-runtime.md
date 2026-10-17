# 0043. The reviewer on Codex

- Status: accepted
- Date: 2026-10-17
- Capabilities: C5, C10, C19

## Context
The reviewer must run on another model than the implementer (C10). OpenAI's Codex CLI can run one in a read-only, non-interactive session, billed to a ChatGPT plan or to an API key. Ticket #157 asked for it (ADR 0015, ADR 0029).

## Decision
- `runtime = "codex"` is for the reviewer only; the implementer is refused with opencode's message. Its tools follow the Claude Code reviewer's allow list (`Read`, `Glob`, `Grep`); `max_tokens` is optional.
- Ariane drives the official CLI only. The command (checked on codex-cli 0.163.0 with `codex exec --help`): `codex exec --json --sandbox read-only --skip-git-repo-check --ephemeral -m <model> -C <tree> -`, in the review tree, the prompt (with the answer schema, as for opencode) on standard input.
- Two logins. Plan: whatever the CLI is logged in with. Ariane never reads, copies or logs `~/.codex/auth.json` or a token; it only runs `codex login status` and stops the ticket with "Codex is not logged in; Next: run codex login, or set agents.reviewer.api_key_env" when it says "Not logged in". API key: `[agents.reviewer].api_key_env` names a variable; its value is passed as `CODEX_API_KEY` to that one process, and no login check is made. The variable is the runtime's only login variable, so the implementer never holds it. Without it, `OPENAI_*` and `CODEX_API_KEY` are removed from the process's environment, so a plan setup cannot fall back to per-token billing.
- Events: the last `agent_message` is the answer; `turn.completed.usage` is summed (`cached_input_tokens` is inside `input_tokens` and is recorded apart as cache read); `turn.failed` or `error` is `error`. `max_tokens` is applied after each completed turn, as for opencode.
- Quota: `StopReason.QUOTA`. A failure that names a usage limit stops the session as `quota`; the journal entry holds the message, the ticket stops with "reviewer quota reached; Next: restart the ticket after <time>" (the time Codex gives, else "later"), never a no-go. `SessionResult.next_step` carries the next action.
- Billing: on a plan login `cost_usd` is 0 and `billing` is `plan`; with a key `billing` is `api` and the cost stays null. `metrics.json` records `billing`; `ariane report` shows plan sessions as "covered by plan".

## Consequences
A reviewer on a strong second vendor with no per-token cost. A usage limit is a clear stop, restarted by hand (#140). The exact wording of Codex's usage-limit event is matched on "usage limit"; a different wording would be an `error`.

## Alternatives considered
- Reading `auth.json` to check the login or call the API: rejected, Ariane must not hold the credentials.
- `--output-schema` for the answer: not used, the schema in the prompt is shared with opencode.
