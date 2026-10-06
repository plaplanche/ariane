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
or `land-and-deploy`) can load (C6). The runtime sets `ARIANE_ROLE=<role>` (C22). The prompt
wraps the issue title and body in clearly delimited untrusted-data markers, and any closing
marker inside them is escaped. The whole context is written to the journal.

**Untrusted environment** (C21, basic). The agent session, and the checks that run the code it
wrote, get Ariane's environment minus every variable that can carry a credential: the tracker
token, any name containing `TOKEN`, `SECRET`, `PASSWORD`, `CREDENTIAL` or `API_KEY`, and
`SSH_AUTH_SOCK` and the askpass variables. SSH is disabled through `GIT_SSH_COMMAND`. The agent
session alone keeps the agent runtime's own login (`ANTHROPIC_*`, `CLAUDE_*`), and gets
`IS_SANDBOX=1` when Ariane runs as root (cloud sandboxes). Known secret values are also masked
in everything written to the ticket folder.

**Push guard** (C11), in layers:

1. The deny list above (prefix rules, easily bypassed: a first layer only).
2. Through `GIT_CONFIG_*` variables, so no configuration file changes, the agent's git sees an
   invalid push URL for every remote, no credential helper and no terminal prompt.
3. After the session and again after the checks, Ariane stops the ticket if the branch moved
   or was switched, if its history was rewritten, if a fingerprint of the shared git
   configuration, hooks, info files, this working tree's configuration and the local branches
   and tags changed, or if any branch or tag on the remote changed. That last rule is strict:
   a person pushing during the session also stops the ticket, until claims (C13) make it finer.
   The generated listings `info/refs` and `info/packs` are excluded: git rewrites them during
   its own housekeeping, and they cannot run code or reroute a push.
4. Ariane's own git commands run with hooks and the filesystem monitor disabled
   (`core.hooksPath` set to the null device, `core.fsmonitor=false`) and without automatic
   housekeeping (`gc.auto=0`, `maintenance.auto=false`), and the commits it makes
   run without credentials. It pushes an exact commit with the explicit remote URL.
5. The owner protects `main` on GitHub (pull request required, CI green). GitHub applies this to
   private repositories only on paid plans, which is why the repository is public (ADR 0008).

An agent with a shell can still find credentials on disk (for example `~/.git-credentials`) or
reach the network on its own: layers 1 and 2 slow it down, layer 3 detects a push to the
remote it watches (`origin`), and only layer 5 prevents a change to `main`. Real isolation
needs an operating-system sandbox and is part of slice 7 (security).

Ariane's own `ariane.toml` declares `claude-sonnet-5-5` for the implementer. Reviews by a
different model (C10) arrive in slice 2.

**Processes**: one helper runs every command as an argument list, resolved through the
absolute PATH entries only (never the current directory, so a `git.cmd` in a working tree
cannot shadow git; `.cmd` shims are found through PATHEXT). Output is decoded as UTF-8 with
replacement. When the command exits or reaches its time limit, its whole process tree is killed
(a process group on POSIX, `taskkill /T /F` on Windows, where children of a process that
already exited cannot be found).

**GitHub client**: redirects are refused (urllib would forward the token to the new host),
`tracker.api_url` must be https (or http to the local machine, for tests), and any unexpected
response becomes a tracker error.

## Consequences
Tests run the full flow with the in-memory tracker and a fake runtime, without network or model.
An agent can still reach the network through its tools; slice 7 (security) narrows that.
Checks that need a credential (for example a private package index) cannot get one in slice 1.

## Alternatives considered
- Shelling out to the `gh` CLI for the tracker: handles authentication, but adds a tool to
  install and parse; the REST calls slice 1 needs are two.
- No `Bash` for the implementer: safer, but the agent could not run the tests it writes.
- Deny rules and an after-the-fact check only: a push to `main` would be detected, not prevented.
