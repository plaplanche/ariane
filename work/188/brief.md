# Product brief: Survivors: a process that keeps forking escapes the /proc scan; stop and kill by process group and session (C10)

- Source: issue #188 (https://github.com/plaplanche/ariane/issues/188)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

ADR 0031 (#167) promises that nothing an agent session or a check starts outlives it on Linux: `process.kill_survivors` scans `/proc`, stops (`SIGSTOP`) the descendants that appeared since the command started, then kills them. A descendant that forks and exits faster than a `/proc` scan escapes it. CI showed it twice on `ubuntu-latest / Python 3.13` (PR #183, two different commits), in `test_c10_reviewer_integrity_a_process_that_keeps_forking_is_killed_with_all_its_children`:

```
ERROR    ariane:logs.py:210 Could not kill: none
FAILED ...a_process_that_keeps_forking_is_killed_with_all_its_children - assert {}
```

The test's process calls `setsid()` once, then forks every millisecond and lets the parent exit. Each scan finds only exited children (zombies, reparented to Ariane as the subreaper), reaps them, and never sees the running generation: by the time its `/proc/<pid>/stat` is read it has exited, and its child is not yet listed. After 5 seconds `kill_survivors` gives up with nothing found, and the process keeps running. It passes locally and on most CI runs: it depends on the speed of the machine. Spec: C10; ADR 0031.

## Current state

- `src/ariane/process.py` `kill_survivors(before, left)`: each scan builds `_process_table()` (pid → parent, state, name), reaps the exited children not in `before` (`_wait`), stops the new running descendants, kills them once all are stopped, and stops after `_REAP_SECONDS` (5 s) with `process.survivors_remaining`.
- `_process_table` reads `/proc/<pid>/stat` but keeps only the parent pid, the state and the name; the process group (field 5) and session (field 6) are dropped.

## Decided spec

- **Kill by group and session too.** `_process_table` also keeps each process's process group and session. In `kill_survivors`, every process found (running, or exited and about to be reaped) that is not in `before` adds its process group and session to a set of groups to stop, unless that group or session is Ariane's own (`os.getpgid(0)`, `os.getsid(0)`) or one that a process in `before` belongs to. Each scan sends `SIGSTOP`, then once no new process appears `SIGKILL`, to each such group with `os.killpg`, as well as to the pids found. The pids found by group are counted and returned like the others.
- **Read the group before reaping.** A zombie's stat still holds its process group and session: they are read from the scan's table before `_wait` reaps it.
- **The deadline still kills.** At `_REAP_SECONDS`, every group in the set and every pid found get `SIGKILL` before `kill_survivors` gives up (as #167 did for pids).
- **Residual, in ADR 0031:** a process that changes its session at every fork (a new `setsid()` in each generation) can still escape a scan; only an operating-system sandbox (cgroups, slice 7) closes that.
- ADR 0031 amendment for the above.

## Release note

Fixed: on Linux, a process that keeps forking and exiting no longer outlives the command that started it.

## Acceptance criteria

- Tests named `test_c10_survivor_groups_*` show:
  - the forking test above passes 20 times in a row (a loop inside the test, not a rerun), with every generation gone afterwards;
  - a group or session that a process in `before` belongs to is never signalled;
  - a zombie's process group is read before it is reaped (a table with a `Z` entry in a foreign group leads to `killpg` on that group);
  - at the deadline, the groups found get `SIGKILL`.
- All checks in CLAUDE.md pass, and CI passes on every system.

## Acceptance checklist

- [ ] `uv run pytest -k c10_survivor_groups` runs at least 4 tests and they pass.
- [ ] ADR 0031 has the amendment, with the residual.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/process.md`; `docs/logs.md` regenerated if a log line changes.

## Out of scope

- A cgroup or namespace sandbox (slice 7).

## Related

ADR 0031; spec C10; #167 (PR #181), PR #183.
