# 0043. The reviewer on Codex

- Status: accepted
- Date: 2026-10-17
- Capabilities: C5, C10, C19

## Context
The reviewer must run on another model than the implementer (C10). OpenAI's Codex CLI can run one in a read-only, non-interactive session, billed to a ChatGPT plan or to an API key. Ticket #157 asked for it (ADR 0015, ADR 0029).

## Decision
- `runtime = "codex"` is for the reviewer only; the implementer is refused with opencode's message. `tools` is accepted but not passed to Codex: the read-only sandbox is the restriction; `max_tokens` is optional on a plan login and required with `api_key_env` (a per-token session has no cost cap, so Ariane needs a token cap).
- Ariane drives the official CLI only. The command (checked on codex-cli 0.163.0 with `codex exec --help`): `codex exec --json --sandbox read-only --skip-git-repo-check --ephemeral -m <model> -C <tree> -`, in the review tree, the prompt (with the answer schema, as for opencode) on standard input.
- Two logins. Plan: whatever the CLI is logged in with. Ariane never reads, copies or logs `~/.codex/auth.json` or a token; it only runs `codex login status` and stops the ticket with "Codex is not logged in; Next: run codex login, or set agents.reviewer.api_key_env" when it says "Not logged in"; a status that fails otherwise is an error, and a status that does not say ChatGPT (an API-key login) is billed per token (`api`, cost null). API key: `[agents.reviewer].api_key_env` names a variable; its value is passed as `CODEX_API_KEY` to that one process, and no login check is made, and a variable that is unset is an error. The variable is the runtime's only login variable, so the implementer never holds it. Without it, `OPENAI_*` and `CODEX_API_KEY` are removed from the process's environment, so a plan setup cannot fall back to per-token billing; the key's name is matched as the other login variables are (case-insensitive, a trailing `_` is a prefix, ADR 0024).
- The review tree is stripped of Codex's own configuration as well as Claude's (ADR 0031): `AGENTS.override.md`, `.codex/` and `.agents/` join `AGENTS.md`, `CLAUDE.md` and `.claude/`, since Codex loads them from the `-C` folder.
- Events: the last `agent_message` is the answer; `turn.completed.usage` is summed (`cached_input_tokens` is inside `input_tokens` and is recorded apart as cache read); `turn.failed` or `error` is `error`, but a later `turn.completed` clears an `error` notice (a reconnect is not fatal). `max_tokens` is applied after each completed turn, as for opencode.
- Quota: `StopReason.QUOTA`. A failure that names a usage limit stops the session as `quota`; the journal entry holds the message, the ticket stops with "reviewer quota reached; Next: restart the ticket after <time>" (the time Codex gives, else "later"), never a no-go. `SessionResult.next_step` carries the next action.
- Billing: on a ChatGPT login `cost_usd` is 0 and `billing` is `plan`; with a key `billing` is `api` and the cost stays null. `metrics.json` records `billing`; `ariane report` shows plan sessions as "covered by plan".

## Consequences
A reviewer on a strong second vendor with no per-token cost. A usage limit is a clear stop, restarted by hand (#140). The exact wording of Codex's usage-limit event is matched on "usage limit"; a different wording would be an `error`.

## Alternatives considered
- Reading `auth.json` to check the login or call the API: rejected, Ariane must not hold the credentials.
- `--output-schema` for the answer: not used, the schema in the prompt is shared with opencode.
