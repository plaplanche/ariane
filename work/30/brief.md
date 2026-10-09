# Product brief: Push with Ariane's own token and ignore base-branch fast-forwards in the remote check (C11)

- Source: issue #30 (https://github.com/plaplanche/ariane/issues/30)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

ADR 0017 revises the push guard: agents hold no git credential and only Ariane pushes, with its own token; a merge on the base branch during a ticket must not stop it; other remote changes still do. Today Ariane pushes with the machine's credentials, and any change to any remote ref stops the ticket.

## Current state

- `src/ariane/git.py:212` `push` runs `git push <url> <sha>:refs/heads/<branch>` with the machine's credential helper.
- `src/ariane/git.py:74` `remote_refs` lists the remote's branches and tags; `src/ariane/flow.py:243` stops when they differ in any way from the start.
- The tracker token is read from `tracker.token_env` (`src/ariane/flow.py:101` onwards, `src/ariane/context.py:48`).

## Decided spec

- Ariane's push sends the tracker token as an HTTP authorization header for that single push, through `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n` (`http.extraHeader`), with the machine's credential helpers disabled for that push. The token never appears in the URL, the argument list, a file or an error message (redacted).
- The remote comparison after a session and after the checks ignores a fast-forward advance of the base branch (the old head is an ancestor of the new one, checked after fetching it) and stops on any other change: a created, deleted or rewritten ref, a non-fast-forward move of the base branch, or any change to the ticket's own branch. The stop line names the refs.
- The README says that in a cloud sandbox whose proxy supplies its own credentials, an agent's push is detected after the session, not prevented (ADR 0017), and how to check what the proxy does.
- When no token is set, or a push with the header is refused for authentication, Ariane pushes once more without the header and its own credential helpers disabled (a cloud sandbox's proxy may supply credentials), and journals which way the push went.

## Release note

Security: only Ariane pushes, with its own token; a merge during a ticket no longer stops it.

## Acceptance criteria

- Tests named `test_c11_push_token_*` show that the push passes the token as a header (seen by a test remote over a local HTTP server, or by inspecting the environment given to git) and that the token appears in no argument, URL or record; and that the fallback push without the header happens once, and is journaled.
- Tests named `test_c11_remote_check_*` show: a fast-forward of the base branch during the session does not stop the ticket; a new branch, a deleted branch, a rewritten base branch, or a change to the ticket branch does.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k "c11_push_token or c11_remote_check"` runs at least 5 tests and they pass.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

The operating-system sandbox (security slice), the GitHub ruleset (the owner sets it).

## Related

ADR 0017, ADR 0007.
