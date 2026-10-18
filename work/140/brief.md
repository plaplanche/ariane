# Product brief: Restart a stopped or interrupted ticket with `ariane start <n> --restart`, keeping the previous branch (C5, C23, C19)

- Source: issue #140 (https://github.com/plaplanche/ariane/issues/140)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

A ticket that stopped (a blocking check, a budget stop, a reviewer failure) or whose process died (Ctrl-C, a machine restart) cannot be started again: `ariane start <n>` refuses because its working trees and its local branch exist, and the person has to find and remove `<n>`, `<n>-review`, `<n>-replay` and `ariane/<n>` by hand. In the benchmark this cleanup was needed after every stopped ticket. The stop line even says "start the ticket again", which is then refused. Resuming a stopped session where it left off is C5's "the next run resumes it" (slice 8); this ticket only gives a clean, documented restart that loses nothing (non-functional requirement: an interruption never loses work). Spec: C5, C23 (each command says the next possible action), C19 (human time to restart measured), C11 (two tickets never share a working tree).

## Current state

- `src/ariane/flow.py:83-100`: `_prepare` refuses when the working tree exists ("remove it to start over"), when the local branch `ariane/<n>` exists ("delete it to start over"), or when `ariane/<n>` exists on the remote.
- `src/ariane/replay.py:29-30` and `replay.py:63-64` refuse when `<n>-replay` or `<n>-review` is left over, for example after a killed process.
- `src/ariane/flow.py:108-110`: an interrupted ticket's next action is "check the working tree, then start the ticket again".
- Nothing tells a live `ariane start <n>` from a dead one: there is no lock (no `lock` in `src/ariane/`).
- `src/ariane/measures.py:40-51`: the human's restart time counts each stop up to the next `ariane verify` record only; a restart by `ariane start` is not seen.

## Decided spec

- **Ticket lock.** `ariane start <n>` holds an operating-system file lock on `<repo>.ariane/locks/<n>.lock` (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows) from before `_prepare` to its exit; the system releases it when the process dies. A second `ariane start <n>` while it is held refuses: "ticket #<n> is running in another Ariane process".
- **`--restart`.** New option of `ariane start`. When the ticket's lock is free and the remote has no `ariane/<n>` (a pushed ticket is never restarted; that refusal is unchanged):
  1. remove the ticket's working trees `<n>`, `<n>-review` and every `<n>-replay*` that exist (`git worktree remove --force`, then `git worktree prune`);
  2. rename the local branch `ariane/<n>`, if it exists, to `ariane-restarted/<n>-<UTC time as YYYYMMDDTHHMMSSZ>`: it is kept, never deleted;
  3. start the ticket as a new run.
  Without anything to remove it is a plain start. With `--shadow` it is refused ("--restart does not apply to shadow tickets; remove the clone").
- **Records.** The new run's journal opens with `ticket.restarted`: the trees removed, the kept branch and its head commit, and the previous run's last action read from that branch's `work/<n>/status.md` when readable. `metrics.json` gets `restarted_from: {"branch": ..., "stopped_at": ...}`, `stopped_at` being the time of the previous run's last step in its `metrics.json` (absent when unreadable); `measures.restart_seconds` adds the time from `stopped_at` to this run's `started`.
- **Next actions.** The refusals of `_prepare` and `replay.py` for leftovers, and every stop of a ticket that was not pushed, say "run `ariane start <n> --restart`" as their next action.
- A new ADR (next free number) records the lock, the kept branch's name and why nothing is deleted.

## Release note

Added: `ariane start <n> --restart` starts a stopped or interrupted ticket over, keeping the previous branch.

## Acceptance criteria

- Tests named `test_c23_restart_*` show:
  - after a stopped ticket, `ariane start <n>` refuses and names `--restart`; `--restart` removes the trees, keeps the old head under `ariane-restarted/<n>-...`, and the new run delivers;
  - leftover `<n>-replay` and `<n>-review` trees from a killed run are removed by `--restart`;
  - with the lock held by another process (a child process holding it in the test), both `start` and `start --restart` refuse and remove nothing;
  - a remote `ariane/<n>` still refuses with `--restart`;
  - `--restart --shadow` is refused;
  - `ariane report` counts the restart time from the previous stop to the new start.
- All checks in CLAUDE.md pass, on Windows too (the lock).

## Acceptance checklist

- [ ] `uv run pytest -k c23_restart` runs at least 6 tests and they pass.
- [ ] The new ADR is in `docs/adr/`.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/flow.md`, `cli.md`, `measures.md`, `metrics.md`, `replay.md` (and a module file for any new module); `docs/architecture/3-components.md` sequence of `start`; `docs/reference/cli.md` and `docs/logs.md` regenerated; README: how to restart a stopped ticket, in PowerShell and bash.

## Out of scope

- Resuming a stopped session's work (C5, slice 8).
- A ticket already pushed (see the `ariane update` drafts).
- Shadow clones.

## Related

Spec C5, C11, C19, C23; ADR 0019, ADR 0030. #142 can reuse the lock helper.


---
_Generated by [Claude Code](https://claude.ai/code)_
