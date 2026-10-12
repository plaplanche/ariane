# Product brief: Watch only the ticket's branch, the base branch and tags on the remote during a ticket (C11, C21)

- Source: issue #104 (https://github.com/plaplanche/ariane/issues/104)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The push guard stops a ticket when any ref of the remote changes during the agent session, except a fast-forward of the base branch. A colleague pushing any branch, or a second `ariane start` on the same repository, stops the ticket; on 2026-10-11 ticket #94 stopped because the session's own branch was pushed. `docs/learnings.md` entry 2 records the same problem. Slice 4 puts Ariane in a second user's shared repository, where other people push all day. An outside analysis of 2026-10-11 rates it blocking for slice 4. Spec: C11, C21; ADR 0017.

## Current state

- `src/ariane/flow.py:296` `_remote_changes`: compares every ref from `git ls-remote --heads --tags` (`git.remote_refs`, `src/ariane/git.py:117`) before and after, tolerating only a fast-forward of `refs/heads/<base_branch>`.
- `src/ariane/flow.py:283`: a non-empty result stops the ticket with "the remote changed during the agent session".
- `docs/adr/0017-push-guard-revision.md`: the narrower remote check of slice 2.

## Decided spec

- The remote check watches only the refs an agent of this ticket could have a reason to touch: the ticket's branch `refs/heads/ariane/<n>`, the base branch (a fast-forward still tolerated, any other change stops), and every tag (a tag created or moved during the session stops). Every other branch is ignored.
- `ariane verify <branch>` uses the same rule with `<branch>` in place of the ticket branch.
- The stop message names the ref, as today. `docs/learnings.md` entry 2 is updated: other people's branches no longer stop a ticket.
- ADR 0017 gets an amendment with this rule and why (a second user's shared repository).

## Release note

Changed: pushes to other branches during a ticket no longer stop it; the ticket's branch, the base branch and tags are still watched.

## Acceptance criteria

- Tests named `test_c11_remote_scope_*` show with a real bare remote: a push to another branch during the session does not stop the ticket; a push to `ariane/<n>`, a non-fast-forward of the base branch and a new tag do; a fast-forward of the base branch does not; the same for `ariane verify`.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c11_remote_scope` runs at least 5 tests and they pass.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): ADR 0017 amended, `flow.md` and `verify.md` module docs, `docs/learnings.md` entry 2.

## Out of scope

Claims across machines (C13); the local `.git` snapshot of the guard.

## Related

ADR 0007, ADR 0017, `docs/learnings.md` entry 2, spec C11, C21, slice 4 prerequisites.
