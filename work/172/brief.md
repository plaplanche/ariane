# Product brief: Security hardening: verify guards git like start; safer git reads; a last guard before the push (C11, C23)

- Source: issue #172 (https://github.com/plaplanche/ariane/issues/172)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Hardening from an internal security review (17 October 2026, main at be82d05). `ariane start` checks that agents and checks did not change git itself (the push guard, ADR 0017), but `ariane verify` (C23), which runs the same untrusted checks on a hand-finished branch, takes no such snapshot. A few other gaps let git configuration or refs change between the last guard and what Ariane reads or pushes. Spec: C11, C23; ADR 0017, ADR 0028.

## Current state

- `src/ariane/verify.py:195-216` replays the checks, then runs `git.diff` (`:212`) and adds the reviewer worktree; `verify.py:274-283` runs `git.status` (`:279`) and the remote check. No `git.config_snapshot` is taken anywhere in `verify.py`.
- `src/ariane/git.py:20-27` `_SAFE_OPTIONS` does not disable external diff or textconv drivers, nor the `ext` transport.
- The snapshot (`git.py:187-227`) covers the shared config, hooks, info, configuration scopes, `refs/heads` and `refs/tags`, not the remote-tracking ref of the base branch; the reviewer's base-branch instructions are read from that local ref (`git.py:176-180`, `:219-221`; `replay.py:144`; `verify.py:241`).
- `src/ariane/delivery.py:71-76`: no guard between the records commit and the push.
- `verify.py:317-331` writes its records with `write_text` on paths inside the branch, without the symlink checks `TicketFolder` has (`src/ariane/ticket.py:108-133`).

## Decided spec

- **verify guard:** take `git.config_snapshot(repo_root, ignore_ref=branch)` before the first check and compare it in `_unchanged`, before any other git command; refuse on change with the same wording as `start`.
- **Safer git reads:** add `--no-ext-diff --no-textconv` to every diff Ariane runs, and `-c protocol.ext.allow=never` to `_SAFE_OPTIONS`.
- **Base instructions:** read the base branch's instruction files once in `flow._prepare` (`flow.py:83-100`), right after the fetch and before any agent runs, keep them in memory for every review round; `verify` does the same before its first check. Add `refs/remotes/<remote>/<base_branch>` to the snapshot.
- **Last guard before the push:** run the guard again right before `git.push` in `delivery.py`; any local `url.*.insteadof` or `url.*.pushinsteadof` key stops the delivery.
- **Records in verify:** written through the same symlink-safe logic as `TicketFolder` (a symlinked target is removed, never followed). The committed record is a regular file (mode `100644`) on every platform: before writing, each record path is removed from the index of the commit tree (`git rm --cached --quiet --ignore-unmatch -- <path>`), so that a link committed on the branch is not kept as a link when git checks it out as a plain file (`core.symlinks=false`, the default on Windows).
- ADR 0017 and ADR 0028 amendments.

## Release note

Security: `ariane verify` guards git like `ariane start`; diffs never run external drivers; the reviewer's base instructions are read before any agent runs; the push is guarded once more.

## Acceptance criteria

- Tests named `test_c11_guard_hardening_*` show:
  - `verify` refuses when a check changes `.git/config`, and runs no further git command;
  - Ariane's diffs ignore a configured external diff or textconv driver;
  - a `url.*.pushinsteadof` key added after the last agent session stops the delivery before the push;
  - the reviewer's base instructions are those of the fetched base, even if the remote-tracking ref is moved during the session (which also stops the run);
  - a symlinked `work/verify/<branch>/checks.md` is replaced, not followed, and committed as a regular file (`100644`), also when the tree is checked out with `core.symlinks=false` (the test forces it, so Linux CI covers the Windows case).
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c11_guard_hardening` runs at least 5 tests and they pass.
- [ ] ADR 0017 and ADR 0028 have the amendments.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/git.md`, `verify.md`, `delivery.md`, `flow.md`; `docs/logs.md` regenerated if a log line changes.

## Out of scope

- Changes to what the guard tolerates for parallel runs (#159; whichever lands second rebases).

## First attempt

This issue replaces #166. Its first attempt (PR #171: review go, checks replayed green on Linux) was red on Windows (Python 3.11 and 3.13), one test failing:

```
FAILED tests/test_c11_guard_hardening.py::test_c11_guard_hardening_verify_records_replace_a_symlinked_checks_file
assert mode.startswith("100644")
'120000 blob 422c2fa...\twork/verify/hand/fix/checks.md'
```

Cause: on Windows, git checks the committed link out as a plain file holding the target path (`core.symlinks=false`); `is_symlink()` is then false, the record is written into that file, and git keeps the index mode `120000`, so the record is committed as a link again. The outside file is not touched; only the committed mode is wrong. The decided spec above now covers it.

## Related

ADR 0017, ADR 0028; spec C11, C23; #159, #162; replaces #166 (PR #171).


---
_Generated by [Claude Code](https://claude.ai/code)_
