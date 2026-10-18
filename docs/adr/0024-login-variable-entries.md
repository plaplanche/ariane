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

## Amendment (2026-10-17): an allow list, and `[project] env`
Ticket #168, from a security review: the environment of agents, checks and setup commands was a
deny list (every variable passed unless its name looked like a secret), so a credential under
another name reached untrusted code. The owner decided on an allow list.

`untrusted_environment` now passes only:

- the base set (`context.BASE_VARIABLES`): `PATH` (without Ariane's scripts directory, ADR
  0040), `HOME`, `USER`, `LOGNAME`, `SHELL`, `LANG`, `LANGUAGE`, `LC_*`, `TZ`, `TERM`, `TMPDIR`,
  `TMP`, `TEMP`, the proxy variables `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`, `ALL_PROXY` (any
  case, as every name) and the certificate variables `SSL_CERT_FILE`, `SSL_CERT_DIR`,
  `REQUESTS_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS`, `CURL_CA_BUNDLE`; on Windows only, also
  `context.WINDOWS_VARIABLES` (`SYSTEMROOT`, `SYSTEMDRIVE`, `WINDIR`, `COMSPEC`, `PATHEXT`,
  `USERPROFILE`, `USERNAME`, `HOMEDRIVE`, `HOMEPATH`, `APPDATA`, `LOCALAPPDATA`, `PROGRAMDATA`,
  `PROGRAMFILES`, `PROGRAMFILES(X86)`, `COMMONPROGRAMFILES`, `NUMBER_OF_PROCESSORS`,
  `PROCESSOR_ARCHITECTURE`, `OS`, `COMPUTERNAME`);
- for agent sessions only, the runtime's login variables (as above);
- the entries of a new optional key `[project] env` (a list of strings, default empty), with the
  same entry rule: an entry ending in `_` is a prefix, any other is an exact name.

The tracker token, `ARIANE_*` and Ariane's virtual environment never pass, even if declared.
Ariane's own additions stay: `GIT_SSH_COMMAND`, `IS_SANDBOX` and the push-blocking git config.

Proxies and certificates are in the base set because checks behind a proxy cannot download
anything without them; a proxy URL that carries credentials is the project's to declare instead:
`HTTP_PROXY`, `HTTPS_PROXY` or `ALL_PROXY` whose value has a user or password before `@`
(`http://user:pass@host`) does not pass unless `[project] env` names it, and is then journaled
by name as a declared secret and masked in every record (its whole value and its `user:pass`).

A declared name that looks like a secret passes (the project asked for it); `flow` journals
`ticket.env.declared_secret` once per run, names only (`context.declared_secrets`). `verify` has no
journal kept on the branch, so it does not record it.

The secret patterns (`git.SECRET_NAME`, used by `known_secrets` and by the environment of
Ariane's own git commands) gain `PAT`, `_KEY$`, `DSN`, `DATABASE_URL`, `_AUTH`, `KUBECONFIG` and
`DOCKER_AUTH_CONFIG`. Choices left open, taken as the simplest that meets the decision:

- `PAT` and `_AUTH` must be a whole part of the name (`(^|_)PAT(_|$)`, `_AUTH(_|$)`), otherwise
  `PATH`, `PATHEXT` and `GIT_AUTHOR_NAME` would count as secrets and be masked or withheld.
- `known_secrets` masks every variable whose name matches, declared or not (unchanged).
- Ariane's own commits of the ticket records run in the untrusted environment (no hooks, no
  credential); since `GIT_AUTHOR_*`, `GIT_COMMITTER_*` and `EMAIL` are no longer in it, `git.commit`
  adds Ariane's own values of these variables to its `git commit` only.
- The journal entry is a warning: it is a deliberate exception to the rule.

Consequence: a check that needs a variable outside the base set (a database URL, a tool's
settings, `GIT_CONFIG_*`) gets it only once the project declares it; Ariane's own `ariane.toml` and
`docs/ariane.example.toml` declare `env = []`. The reviewer gets the same allow list and nothing
more.
