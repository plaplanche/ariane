# Product brief: Replay the checks in a clean working tree at the delivered commit (C9)

- Status: draft
- Approved: not yet
- Source: issue #24 (https://github.com/plaplanche/ariane/issues/24)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The checks are replayed in the working tree the implementer used, ignored files included (the virtual environment made by the setup command, caches, anything the agent left ignored by git). An agent can change an ignored dependency so that the checks pass without the pull request showing it. Decision: ADR 0018; spec C9.

## Current state

- `src/ariane/flow.py:302` runs `checks.run_checks(self.config.checks, self.worktree, self.untrusted_env)` in the implementer's working tree.
- `src/ariane/flow.py:159` `_setup` runs the setup command in that same tree; `src/ariane/git.py:84` `add_worktree` creates working trees.

## Decided spec

- After the implementer's work is committed, Ariane creates a second working tree at that commit, detached, beside the ticket's (`<repo>.ariane/worktrees/<n>-replay`), runs the setup command there, then every check, in the untrusted environment as today.
- Only that replay counts: its results are the ones recorded in `checks.md`, decide delivery and are published. The replay tree is removed afterwards, whatever the outcome; a failure to remove it is a journaled warning.
- A setup failure in the replay tree stops the ticket like a setup failure today, with the output.
- The guard checks after the checks (`_verify`) still run on the ticket's tree, and the replay tree's branchless head must not have moved.
- The journal says where the checks ran.

## Release note

Security: checks are replayed in a clean working tree at the delivered commit, never in the tree the agent used.

## Acceptance criteria

- A test named `test_c9_clean_replay_*` shows that a file ignored by git and created by the agent in its tree (for example a module that makes a test pass) is absent from the replay, so a check that depends on it fails.
- A test named `test_c9_clean_replay_setup_failure_*` shows that a setup failure in the replay tree stops the ticket with the setup output.
- A test shows that the replay tree no longer exists after delivery and after a stop.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c9_clean_replay` runs at least 3 tests and they pass.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

The reviewer reading the replay tree (a later issue), statuses from CI (separate issue), C9's pre-change replay.

## Related

ADR 0018, ADR 0006, ADR 0020 (step 2).
