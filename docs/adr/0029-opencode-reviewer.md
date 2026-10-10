# 0029. The reviewer on opencode

- Status: accepted
- Date: 2026-10-10
- Capabilities: C5, C22

## Context
ADR 0014 requires vendor independence and ADR 0015 records how opencode 1.18.35 behaves. The owner decided that the default reviewer stays on Claude Code and that opencode is an option, used for slice 3's gate. A few details were left open.

## Decision
- `[agents.<role>] runtime` is `claude-code` or `opencode`; opencode is refused for the implementer with a message naming the role. An opencode agent's model is `<provider>/<model>` and its tools are among `read`, `glob`, `grep`.
- A `RoutedRuntime` gives each role its runtime; `flow` and `verify` still take one runtime. Login variables are the union of the runtimes' ones. For opencode they are the provider's key (`<PROVIDER>_API_KEY`, with a short table for providers that differ).
- The turn cap is a constant, `steps = 20`, in the inline configuration: the configuration has no key for it yet.
- The prompt is passed as the message argument, as the issue decided. opencode has no schema option, so the schema is appended to the message and the answer is the last fenced `json` block of the last text part.
- Caps: the token cap (`max_tokens`) and, when opencode reports a cost above 0, the cost cap (`max_budget_usd`), both checked after each `step_finish`.
- `ARIANE_CONFIG`, a path relative to the repository root (or absolute), replaces `ariane.toml` for one run; its errors name `ARIANE_CONFIG (<file>)`.

## Consequences
A review on a second vendor needs no change to Ariane's own `ariane.toml`. A very large prompt may exceed the operating system's command-line limit (notably on Windows); the diff is already truncated by `review.MAX_DIFF_CHARS`.

## Alternatives considered
- Pass the prompt on standard input: rejected, `opencode run` reads its message from the arguments.
- A `steps` key in `ariane.toml`: rejected for now, one more key without a need.
