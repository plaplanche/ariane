# 0024. Login variable entries: exact names and prefixes

- Status: accepted
- Date: 2026-10-10
- Capabilities: C5, C21

## Context
ADR 0015 has each runtime declare the variables it keeps for its login. The spec does not say
how one list tells an exact name from a prefix.

## Decision
`AgentRuntime.login_variables` is a tuple of strings, compared case-insensitively. An entry
ending in `_` is a prefix; any other entry is an exact name. `ClaudeCodeRuntime` declares
`("ANTHROPIC_", "CLAUDE_")`. `untrusted_environment` takes `login_variables` in place of
`keep_agent_login`: an empty list keeps nothing (the checks' environment). The tracker token never
passes, even if declared. `known_secrets` is unchanged: it already includes every credential-like
name, kept or not.

## Consequences
A runtime whose exact variable ends in `_` cannot be declared; none is expected.
