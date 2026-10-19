# Product brief: Guard: tolerate a fast-forward of the base's tracking ref, so tickets can run back to back while pull requests are merged (C11)

- Source: issue #222 (https://github.com/plaplanche/ariane/issues/222)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The owner wants to run tickets continuously: as soon as one ends, the next starts while another may still run, and finished pull requests are merged in between. Today that stops the running ticket. Each `ariane start` fetches the base branch (`git fetch origin +refs/heads/<base>:refs/remotes/origin/<base>`), and the guard's snapshot holds `refs/remotes/origin/<base>` (ADR 0017, "The base's tracking ref is guarded"). When a pull request was merged after a running ticket started, the next start's fetch moves that ref, and the running ticket stops on it. ADR 0017 lists this as not covered. Spec: C11 (isolation, push guard), C9.

## Current state

- `flow._TicketRun.state` watches `refs/remotes/<remote>/<base>`; any change to it is a guard stop.
- On the remote, a fast-forward of the base branch is already tolerated (`git.remote_changes`, `git.fast_forwarded`, which fetches from the URL so as not to move the tracking ref).
- The parallel guard (#159, `runs.foreign_changes`) tolerates another registered run's own branch and config keys, not the tracking ref.

## Decided spec

- **Tolerate a fast-forward of the tracking ref.** When the only difference on `refs/remotes/<remote>/<base>` between two snapshots is a move from `old` to `new` where `new` descends from `old` and `new` is the commit the remote's base branch points to now (or pointed to at the remote check of the same verification), the guard does not stop. Any other change to that ref (a move backwards or sideways, a commit the remote's base does not have, a deletion) still stops, with the same reason as today.
- The tolerance applies whether or not another run is registered: the check is against the remote, which an agent cannot change without the remote check seeing it.
- The ticket keeps the base it started from: its diff, its review range and its delivery are computed from the base commit recorded at the start, never from the moved tracking ref. A test shows the reviewer's diff is unchanged after the ref moved.
- ADR 0017's "Not covered" line is replaced by a pointer to the new ADR, which records the rule and why the remote is the witness.

## Release note

Changed: a ticket no longer stops when another run fetches a base branch that advanced by a merge; tickets can run back to back while pull requests are merged.

## Acceptance criteria

- Tests named `test_c11_tracking_ref_*` show:
  - a run that fetches the base branch after a merge (fast-forward on the remote) does not stop a running ticket, and that ticket delivers with its own start base;
  - the tracking ref moved backwards, to a sibling commit, to a commit the remote's base does not point to, or deleted, still stops the ticket;
  - the reviewer's diff and the delivered commit range are the same with and without the move.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c11_tracking_ref` runs at least 4 tests and they pass.
- [ ] A new ADR, and ADR 0017's "Not covered" line updated.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/git.md`, `flow.md`, `runs.md` if touched; `docs/logs.md` regenerated if an event changes.

## Out of scope

- Bringing the merged base into the running ticket (#145, #146).
- Running more than the machine's run slots (ADR 0050).

## Related

ADR 0017 (push guard), #159 (parallel guard), #142 (run slots), #145, #146 (`ariane update`); spec C9, C11.
