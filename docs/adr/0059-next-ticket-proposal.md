# 0059. `ariane next`: propose the next ticket of a labelled queue, started on the owner's confirmation

- Status: accepted
- Date: 2026-10-21
- Capabilities: C11, C22, C23

## Context
The owner wants tickets to follow each other continuously instead of in fixed pairs: when one
ends, decide whether another can start safely next to what still runs, and start it. The run
slots (ADR 0050) and the parallel guard (#159) already let several tickets run at once on one
repository, but nothing in Ariane knew the order of the queue, the dependencies between issues,
or whether two tickets would touch the same files. Issue #223 decided the behaviour; this ADR
records it and the choices it left open.

## Decision
- **Queue.** The open issues (never pull requests) carrying the label `[tracker] next_label`
  (default `ariane-next`, which must differ from `ready_label`), in the order that label was
  last added: the time of its last `labeled` event, as the issue gate reads it (ADR 0032). An
  issue whose event is not listed yet takes its last change (`updated_at`) instead. Ties go to
  the lower number. The queue is read without the issue gate: `ariane next` only reads it, and
  `ariane start` still reads the issue through the gate.
- **Look-ahead.** The running tickets are left out of the queue, then its first
  `[next] look_ahead` issues (default 5) are looked at.
- **Dependencies.** A line of the body starting with `Needs #N` (a list marker allowed; several
  numbers separated by `,`, `and` or `&`) makes the issue wait until each named issue is closed
  with the reason `completed`: an open issue, or one closed as not planned, keeps it waiting.
- **Expected files.** Each word of the body, quotes, brackets and trailing punctuation removed,
  is a path when it has a `/` and its last segment has an extension or a wildcard (so `owner/name`
  or `ariane/12` are not), a folder `a/b/` standing for the glob `a/b/**`; a word without `/` is
  a path only when it names a file at the repository root (`README.md`) or a module file
  (`cli.md` is `docs/architecture/modules/cli.md`). URLs, absolute paths, `..` and words with
  placeholders (`<module>`) are never paths. Each module file adds `src/<package>/<module>.py`
  and the tests whose file name holds the module's name as whole words (`test_cli.py` and
  `test_c23_cli_x.py` for `cli`, not `test_client.py`). `[next.paths]` adds globs per label
  (`docs = ["docs/**"]`). The names are matched against the main checkout's files.
- **Running files.** A running ticket (a live entry of the run registry, ADR 0017) touches its
  branch's changes since the merge base of its branch and the base's tracking ref, its tree's
  uncommitted and untracked files included, plus its own expected files, from its issue's body
  and labels: the queue's entry, else the issue read from the tracker without the gate, so a
  ticket started by hand or no longer queued keeps its `[next.paths]` globs.
- **Unknown running files.** When a running ticket's files cannot be read (its branch does not
  exist yet because the run is still preparing it, git fails, or its issue cannot be read),
  nothing is proposed: `the files of running #M are not known (<why>)` holds every issue.
- **Shared paths.** Two lists share a path when both name it, when a glob of one matches a path
  of the other, or when two globs can match one same path: their automata are walked together
  (`docs/**` and `docs/architecture/**`, `src/**/*.py` and `src/ariane/*.py` overlap). Two
  overlapping globs are named by the files both match among the main checkout's files and the
  running tickets' changes (counted beyond three), else as the two globs; a file not created
  yet is shared all the same.
- **Already started.** An issue with a ticket tree or a local branch `ariane/<n>` is not
  proposed ("already started"): `ariane status` and `--restart` are the owner's to choose.
- **Blockers.** No free run slot (a slot taken and released at once), or a last run stopped on a
  quota, holds every issue back. The last run is the run of the registry's history (`ended.jsonl`)
  that ended last; it stopped on a quota when its `metrics.json` has the outcome `stopped` and its
  last agent session the stop reason `quota` (its stop category is `runtime`, ADR 0058). Restarting
  that ticket once the quota resets ends a new run, which lifts the blocker.
- **Proposal.** The first issue looked at with no reason, printed as one line:
  `Next: #N (no shared file with #M). Start it with ariane next --start.` (`nothing runs` when no
  ticket runs). Nothing proposed: `Nothing to start: <why>. Next: <action>.`, exit code 1.
- **Start.** `ariane next --start` proposes again and compares the proposal phrase with the
  one it may confirm: the last entry of `next.md`'s, if that entry printed a proposal (a
  `proposal`, or a `start refused` whose new proposal was just printed). Any change (another
  start, a closed issue, a new running ticket) refuses. Otherwise it removes the issue's
  `ready_label` and adds it back with the token, as a maintainer would, so the gate sees a
  fresh label on an unchanged issue, then runs `python -m ariane start <n>` detached from the
  terminal (its own session on POSIX, a detached process group on Windows, no input), with the
  token in its environment, its output appended to `<repo>.ariane/logs/<n>.out`, beside the
  ticket's technical log. The ticket's own records appear in its tree, whose folder does not
  exist before the start, so the output cannot go there.
- **Handoff.** `ariane next` and `ariane next --start` run under the lock
  `<repo>.ariane/next/.lock`, and every registration of a run (`ariane start`, by hand too)
  waits for it, except the ticket `--start` launches (the environment variable
  `ARIANE_NEXT_LAUNCH=<n>`). `--start` holds it from its check until its ticket registers as
  running, its process ends, or 60 seconds pass: two starts never confirm one proposal twice,
  and no run registers between the check and the start it confirms.
- **Reservation and intent.** Before its first external write (the relabel), `--start` writes
  a reservation `<repo>.ariane/next/<n>.json` (the ticket, a process, a time, a state) and
  appends a `start intent` entry, which consumes the confirmation: a second `--start` needs a
  new proposal printed. After the launch the reservation names the ticket's process; it is
  removed once the `start` entry is written and the ticket registered or ended. A reservation
  still pending (its ticket not registered, its process alive or the reservation younger than
  60 seconds) holds every issue back: `#N is starting (process P)`. A leftover one (a `--start`
  that crashed, or could not write its `start` entry) is recorded as `start reconciled` by the
  next `ariane next`, with whether the ticket registered. A failure after the launch says the
  ticket started (`Started #N ..., but ...`), never that nothing was done.
- **Record.** Each proposal, start intent, start, refused start and reconciled start is
  appended to `<repo>.ariane/next.md`: its time, the running tickets, the reason of every issue
  looked at, the proposal, and for a start who confirmed it (the local user name), the started
  process and whether it registered.
- **The owner confirms each start.** Ariane proposes; only `--start`, run by the owner, starts.

## Consequences
- The owner sees why each issue waits, and the proposal is reproducible from `next.md`.
- Two tickets that touch the same module are kept apart as soon as one names it in its body, or
  its branch changes it; a file neither names nor changes yet is not seen.
- A run that is still preparing its branch, or whose issue the tracker cannot return, holds the
  queue until it can be read: a missed proposal costs a later `ariane next`, a wrong one a
  conflict.
- A manual `ariane start` waits, at most about a minute, while `--start` hands a ticket over;
  it still checks no shared file itself (the owner chose it).
- Path detection is textual: a path written as an example in an issue counts. A false sharing
  only delays an issue; the owner can still run `ariane start` by hand.
- An issue already started stays in the queue until it is closed; it is listed, never proposed.

## Alternatives considered
- Starting the proposal automatically: the proposals are not trusted yet; issue #223 keeps the
  owner's confirmation, autonomy comes later.
- Removing the queue label at the start: the issue would change after its ready label, and the
  gate would refuse it.
- Reading dependencies from GitHub's sub-issues or linked issues: not reachable over the REST
  API from every sandbox, and the body line is visible and editable by the owner.
- Comparing two globs only through the files they match today: a file a ticket creates would
  be missed. The automata are walked instead, and the files only name the overlap.
- Reading a running ticket's brief for its expected files: the brief has no labels, and is not
  written yet while the run starts. The tracker returns both.
- Waiting for no registration, with only the reservation: a ticket started by hand between the
  check and the launch would be missed.
- Writing the background output in the ticket's folder: the folder is created by the start
  itself, and a file left in its tree would be an untracked change of the run.
