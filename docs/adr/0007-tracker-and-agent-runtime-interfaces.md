# 0007. Tracker and agent runtime interfaces

- Status: accepted
- Date: 2026-10-06
- Capabilities: C1, C5, C11, C22, C21 (basic)

## Context
The tracker and the agent runtime are abstractions from day one (founding decisions), with
GitHub and Claude Code first and an in-memory tracker for tests.

## Decision
**Tracker** (`typing.Protocol`): `read_issue` and `open_pull_request` in slice 1; comments,
labels and claims arrive with the slices that need them. Implementations: `GitHubTracker` over
the REST API with `urllib.request` and a token read from the variable named by
`tracker.token_env`; `InMemoryTracker` for tests.

**Agent runtime** (`typing.Protocol`): `run(session) -> SessionResult`, where the session holds
role, model, tools, budget, time limit, working directory and prompt, and the result holds the
stop reason (`finished`, `budget`, `turns`, `timeout`, `error`), cost, tokens and permission
denials as reported. `ClaudeCodeRuntime` runs:

```
claude -p --output-format json --model <model> --tools <tools...>
       --disallowedTools "Bash(git push:*)" "Bash(git checkout:*)" "Bash(git switch:*)"
                         "Bash(git rebase:*)" "Bash(git reset:*)" "Bash(gh:*)"
       --permission-mode bypassPermissions --strict-mcp-config
       --max-budget-usd <budget> --no-session-persistence
```

with the prompt on standard input. The stop reason comes from the result's `subtype`
(`success`, `error_max_budget_usd`, `error_max_turns`, anything else is `error`), checked on
Claude Code 2.1.291; a session Ariane kills at its time limit is `timeout`. Recorded results are
kept as test fixtures.

The implementer's tools never include `Skill`: no user-level skill (for example gstack's `ship`
or `land-and-deploy`) can load (C6). Its environment holds `ARIANE_ROLE=<role>` (C22), loses
the tracker token variables, and gets `IS_SANDBOX=1` when Ariane runs as root (cloud sandboxes).
The prompt wraps the issue title and body in clearly delimited untrusted-data markers. The whole
context is written to the journal.

**Push guard** (C11). The deny list above is only a first layer: prefix rules are bypassed by
`git -C . push` or a script. Before the session, Ariane:

- sets, for the ticket's working tree only (`extensions.worktreeConfig`), every remote's push
  URL to an invalid value, so a plain `git push` fails;
- runs the agent with `GIT_TERMINAL_PROMPT=0` and an empty `credential.helper` (through
  `GIT_CONFIG_COUNT`), so no stored credential is offered.

Ariane itself pushes with the explicit remote URL. After the session it checks that the branch,
the starting commit and the remote branches did not change. The owner protects `main` on GitHub
(pull request required): it is the only guard that also holds where the network layer
authenticates git on its own, as in cloud sandboxes.

Ariane's own `ariane.toml` declares `claude-sonnet-5-5` for the implementer. Reviews by a
different model (C10) arrive in slice 2.

**Processes**: one helper runs every command as an argument list resolved with `shutil.which`
(so `.cmd` shims work), decodes output as UTF-8 with replacement, and on timeout kills the whole
process tree (`taskkill /T /F` on Windows, a process group on POSIX).

## Consequences
Tests run the full flow with the in-memory tracker and a fake runtime, without network or model.
An agent can still reach the network through its tools; slice 7 (security) narrows that.

## Alternatives considered
- Shelling out to the `gh` CLI for the tracker: handles authentication, but adds a tool to
  install and parse; the REST calls slice 1 needs are two.
- No `Bash` for the implementer: safer, but the agent could not run the tests it writes.
- Deny rules and an after-the-fact check only: a push to `main` would be detected, not prevented.
