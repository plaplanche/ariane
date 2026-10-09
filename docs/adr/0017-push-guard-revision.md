# 0017. Push guard: no credential for agents, one pusher, a narrower remote check

- Status: accepted
- Date: 2026-10-08
- Capabilities: C11, C21

## Context
ADR 0007's push guard has five layers; only layer 5 (the protection of `main` on GitHub)
prevents a push to `main`, and layers 1 and 2 can be bypassed by an agent with a shell. Layer 3
stopped real tickets twice for reasons unrelated to agents: a person's git command in the
repository during a ticket, and git's background housekeeping (#10). In a cloud sandbox, the
outbound git proxy supplies its own credentials to any push: checked on 2026-10-08 with
`git push --dry-run https://github.com/plaplanche/ariane HEAD:refs/heads/<new>` run with an
empty `credential.helper`, `GIT_TERMINAL_PROMPT=0` and no token in the environment, which was
accepted. Removing credentials from the agent's environment is therefore not enough there.

## Decision
- **No git credential for agents.** Agent sessions and the checks keep running without any
  credential variable, SSH agent, askpass or credential helper (ADR 0007), unchanged.
- **Only Ariane pushes, with its own token.** Ariane pushes with the tracker token
  (`tracker.token_env`), passed to its own git through `GIT_CONFIG_*` variables as an HTTP
  authorization header for that push only, never in the URL, the argument list or a file. It no
  longer depends on the machine's credential helper.
- **One fallback push.** When the push with the token header is refused for authentication, or
  no token is set, Ariane pushes once more, once only, without the header: a cloud sandbox's
  proxy may supply credentials. The credential helpers stay disabled for that push, and the
  journal says which way the push went.
- **Branch rules on the repository.** The owner adds a ruleset on all branches that blocks
  deletions and force pushes (free on a public repository); `main` keeps its protection.
- **Narrower remote check (layer 3).** After a session and after the checks, Ariane compares
  the remote's branches and tags with the snapshot taken at the start, ignores a fast-forward
  advance of the base branch (a merge by the human), and stops on any other change: a created,
  deleted or rewritten ref, or any change to the ticket's own branch. The local git snapshot
  (configuration, hooks, local refs) is unchanged.
- **The stop message says why.** A stop caused by a change to git while a ticket runs says
  that nobody runs git commands in the repository or pushes to it while a ticket runs.
- **Cloud sandboxes: detected, not prevented.** Where the network supplies credentials, an
  agent can still create branches until the operating-system sandbox of the security slice
  (C21); Ariane detects it after the session and stops the ticket, and `main` stays protected.
  The README and the journal say so.

This decision supersedes the "Push guard" part of ADR 0007.

## Consequences
On a person's machine, an agent's push fails for lack of credentials. Merging a pull request
no longer stops a running ticket. A person pushing another branch still does.

## Alternatives considered
- An operating-system sandbox or a credential-free container now, on three operating systems:
  the real fix, kept for the security slice because of its cost.
- The agent runtime's own network sandbox in the cloud: specific to one runtime (ADR 0014).
