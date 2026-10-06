# Product brief: Git guard: ignore info/refs and info/packs, and turn off git's background housekeeping (C11)

- Status: draft
- Approved: not yet
- Source: issue #10 (https://github.com/plaplanche/ariane/issues/10)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The git guard (ADR 0007, layer 3) stops a ticket when its snapshot of git changes during the agent session or the checks. On Windows CI it sometimes stops with `.git/info/refs` as the changed part (PR #9, job `windows-latest / Python 3.11`, test `test_c11_a_plain_push_from_the_agent_working_tree_fails`; the same failure happened earlier on main). Neither the agent nor the checks caused it. `info/refs` (and `info/packs`) are listings that `git update-server-info` regenerates. Git runs that by itself during automatic housekeeping (`gc --auto` runs `repack`, which updates them), in the background after commits. On slow runners, that housekeeping can end in the middle of a ticket.

## Current state

- `src/ariane/git.py`, `config_snapshot`: digests every file under the common directory's `hooks/` and `info/` folders, including `info/refs` and `info/packs`.
- `src/ariane/git.py`, `_SAFE_OPTIONS`: the `-c` options of every git command Ariane runs (`core.hooksPath`, `core.fsmonitor`, `core.quotepath`). Automatic housekeeping stays on.

## Decided spec

1. `config_snapshot` leaves out `info/refs` and `info/packs`. They are generated listings for the dumb HTTP transport: they cannot run code or reroute a push. Every other file under `hooks/` and `info/` (for example `info/exclude` and `info/attributes`) stays in the snapshot.
2. `_SAFE_OPTIONS` adds `-c gc.auto=0` and `-c maintenance.auto=false`, so that the git commands Ariane runs during a ticket never start background housekeeping.
3. ADR 0007, layer 3, says in one sentence that these two generated files are excluded, and why.

## Release note

Fixed: a ticket no longer stops when git's own background housekeeping rewrites `.git/info/refs`.

## Acceptance criteria

- A flow test whose fake agent runs `git update-server-info` (which writes `info/refs`, and `info/packs` when the repository has packs) and edits a file ends delivered, exit code 0.
- A flow test whose fake agent writes `.git/info/attributes` is still stopped by the guard, which names that file.
- A test checks that a git command Ariane runs carries `gc.auto=0` and `maintenance.auto=false` (for example through `git config --get gc.auto` run with Ariane's helper).
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] The three tests above exist in `tests/test_flow_guards.py` or `tests/test_flow.py`.
- [ ] ADR 0007 is updated.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

- Any other relaxation of the guard.
- Changing the repository's own housekeeping settings: Ariane only passes options on its own commands.
