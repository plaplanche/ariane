# 0052. Independent checks replayed in parallel, each in its own tree and slot

- Status: accepted
- Date: 2026-10-19
- Capabilities: C9, C11

## Context
Since ADR 0041 each check is replayed in its own clean working tree, so the setup runs once per
check, and the checks still run one after another. In the benchmark on a reference project, an
Ariane ticket took two to three times the wall-clock time of the implementing agent used alone,
the replay a large part of it. Checks in separate trees can run at the same time, as CI jobs do,
if they do not collide on the machine's local resources: the run slot of ADR 0050 gives the
project a way to keep them apart. C9 asks that all checks run, one section per check and a final
summary; the non-functional "Cost" requirement asks Ariane not to waste the owner's time. Issue
#143 decided the behaviour; this ADR records it.

## Decision
- **Key.** `project.parallel_checks`, a positive integer, 1 by default: the number of checks
  replayed at the same time. 1 is the order of ADR 0041, one by one in the calling thread. All
  declared checks (with the documentation checks) are taken as independent.
- **Workers.** Above 1, `replay.replay_each` starts one thread per worker (at most one per
  check); each takes the next check in declared order and replays it in its own tree: create the
  tree, its setup, that check only, the guard's verification, removal. The results are returned in
  the declared order whatever the order they finish in, so `checks.md`, the summary, the journal's
  list of trees and the commit statuses are as before. Creating and removing a tree are done one
  worker at a time (git's list of working trees); the setups, the checks and the verifications
  run concurrently. `ariane start` (shadow included) and `ariane verify` follow the same key.
- **Threads, not processes.** Each worker runs its commands through `process.run`, which already
  waits for an external process; the time is spent in those processes, not in Python. Threads
  share the run's guard snapshot, metrics, journal and process registry without serialising them,
  and the process stays the subreaper of everything the checks start. Two process-wide changes
  make commands of several threads safe: a spawn and a survivor scan never overlap (one lock),
  and a scan (`kill_survivors`, and what a command left when it ended) spares the commands other
  threads still wait for, their descendants and their process groups and sessions; it never reaps
  another thread's child either. A process that left both its command's tree and its group is a
  survivor whichever worker's scan finds it; it is killed and counted as today.
- **Slots.** The run keeps its own slot (ADR 0050) for its first worker; each further worker takes
  the lowest free slot as the run did (`slots.several`, the same lock files) and holds it until
  the replay ends. Each worker gives its slot as `ARIANE_SLOT` to its setup and its check, so two
  checks of one run never share a slot, nor share one with another run. When fewer slots are free
  than wanted, the replay uses as many workers as it got slots, at least the run's own, and never
  waits. With more than one worker wanted, the journal's `ticket.checks.parallel` entry (and, for
  `ariane verify`, the `Run` section of `review.md`) says how many ran at once and in which slots,
  and that fewer slots were free when it is so; the journal's list of trees names each tree's slot.
- **Stop.** A stop in one worker (a failing setup, a guard violation, any error), Ctrl-C in the
  calling thread, or a worker thread that fails to start stops the others: no worker takes a new check, the process trees of their running
  commands are killed and their next commands refused (`process.cancel`), except creating and
  removing a tree (`process.shielded`), so every tree is removed before the replay raises the
  first stop, as it does for one check. The calling thread waits for an event each worker sets
  once its tree is removed, not for `Thread.join`: on Python 3.11, Ctrl-C during a join can mark a
  thread stopped while it still runs, which would release the slots before the trees are removed.

## Consequences
- With `parallel_checks = N`, the replay takes about as long as its slowest group of checks
  instead of their sum, plus the guard's verification of each tree.
- A project that runs checks at the same time must derive from `ARIANE_SLOT` anything two checks
  would share (ports, a local database); a check that needs another's output must not be declared
  with `parallel_checks` above 1, since declaring dependencies between checks is out of scope.
- A run holds up to `parallel_checks` slots during its replay, so fewer of the 16 are free for
  other runs at that time.
- Ariane's own `ariane.toml` keeps the default; the owner chooses.

## Alternatives considered
- A process pool (`multiprocessing`): each worker would need the run's state (guard snapshot,
  journal, metrics) passed and merged back, would not be the subreaper of what its check starts
  without more work, and a Ctrl-C would reach every worker at once with no single place to clean up.
- Starting every check at once without a limit: a project's checks may each use all cores, and
  the slots would run out for other runs.
- Sharing the run's one slot between its checks: two checks starting the same local service would
  collide, the very failure ADR 0050 removed between runs.
- Waiting for free slots before replaying: a run that cannot get them would wait on others,
  where running fewer at once always ends.
