# Product brief: Kill the agent's process tree on any exit, Ctrl-C included, and record the interruption (C5, C23)

- Source: issue #102 (https://github.com/plaplanche/ariane/issues/102)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

An outside analysis of Ariane (2026-10-11) found that an interrupted run leaves the agent running: `kill_tree` runs only after `proc.wait` returns normally, so a `KeyboardInterrupt` (Ctrl-C) or any other exception skips it, and the child, started in its own session, never sees the SIGINT. The agent keeps running with `bypassPermissions` in the background, and the ticket stays at its last status. This is a prerequisite of slice 4: a second user will interrupt runs. Spec: C5, C23.

## Current state

- `src/ariane/process.py:163-167` (`_execute`, used by `run` at line 85 and `stream` at line 102): `try: proc.wait(timeout=timeout_s) except subprocess.TimeoutExpired: timed_out = True` then `kill_tree(proc.pid)` outside any `finally`.
- `src/ariane/flow.py:572`: `_stopped(exc: BaseException)` records a stop; `flow.py:498` catches `BaseException` around the replay.

## Decided spec

- In `_execute`, the process tree is killed in a `finally` that covers the wait and the readers, so it is killed on normal exit, timeout, `KeyboardInterrupt` and any other exception; the exception is then re-raised.
- `ariane start` and `ariane verify` interrupted by Ctrl-C record the stop ("interrupted by the user") in the ticket's journal and `status.md` when the ticket folder exists, commit the record like any stop, print one line and exit 130.

## Release note

Fixed: Ctrl-C during a run stops the agent's process tree and records the stop.

## Acceptance criteria

- Tests named `test_c5_interrupt_*` show: a `KeyboardInterrupt` raised while waiting kills a real child process tree (a child and a grandchild started by a fake binary are gone afterwards) and is re-raised; the ticket records "interrupted by the user" and the command exits 130.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c5_interrupt` runs at least 2 tests and they pass.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/process.md` and `flow.md` updated, log catalogue regenerated if an event is added.

## Out of scope

Resuming an interrupted ticket (slice 8).

## Related

Spec C5, C23, slice 4 prerequisites.
