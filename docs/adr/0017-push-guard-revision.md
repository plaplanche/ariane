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

## Amendment (2026-10-11): the remote check watches only what a ticket could touch

A second user's shared repository (slice 4) has other people pushing all day, and ticket #94
stopped because the session's own branch was pushed. The check no longer compares every ref.
It watches:

- the ticket's branch `refs/heads/ariane/<n>`: any change stops;
- the base branch: a fast-forward is tolerated, any other change stops;
- every tag: a tag created, moved or deleted stops.

Every other branch is ignored, so other people's pushes no longer stop a ticket. The stop
message still names the ref. `ariane verify <branch>` applies the same rule with `<branch>` in
place of the ticket branch, comparing the remote at the start of the run and after the replayed
checks and the reviewer; it skips the check when the repository has no `origin`. An agent that
creates a branch other than its own is no longer detected; the branch rules on the repository
and the credential-free sessions above remain the protection.

## Amendment (2026-10-17): where the token lives during a run

- **Read once, then gone from the environment.** The CLI reads `tracker.token_env` and removes it
  from `os.environ`. The value then lives in the tracker, in the push, and in the copy of the
  environment handed to the run (in memory only, filtered by `untrusted_environment` before any
  agent, check or setup command).
- **Token-free git.** `git.git` and `git.out` use by default the environment without any variable
  the credential filter withholds (`TOKEN`, `SECRET`, `PASSWORD`, ... and the SSH/askpass
  channels); only `git.push` receives the authorization header. A consequence: Ariane's own
  fetches cannot use an SSH agent.
- **Not dumpable on Linux.** At start the CLI calls `prctl(PR_SET_DUMPABLE, 0)` through
  `ctypes`; a failure is journaled as a warning, never fatal.
- **Residuals.** On macOS, on Windows and when running as root, a same-user process can still read
  Ariane's memory; only the operating-system sandbox of the security slice (C21) closes it. The
  README recommends a fine-grained token limited to the one repository.

## Amendment (2026-10-17): guards that cover what Ariane reads and pushes

- **`verify` guards git like `start`.** `ariane verify` takes the git snapshot before its first
  check and compares it after every check and the reviewer, before any other git command; a
  change is refused with the wording of `start`.
- **Safer reads.** Every diff Ariane runs has `--no-ext-diff --no-textconv`, and every git
  command `-c protocol.ext.allow=never`: a configured driver or the `ext::` transport never runs.
- **The base's tracking ref is guarded.** The snapshot holds `refs/remotes/<remote>/<base>`. The
  tolerance for a fast-forward of the base branch fetches from the URL, so that it does not move
  that ref.
- **A last guard before the push.** The delivery runs the guard once more right before
  `git.push`, and any local `url.*.insteadof` or `url.*.pushinsteadof` key stops it.
