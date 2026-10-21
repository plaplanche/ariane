# Product brief: ariane next: propose the next ticket that can start safely next to the running ones, start it on the owner's confirmation (C11, C22, C23)

- Source: issue #223 (https://github.com/plaplanche/ariane/issues/223)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

The owner wants tickets to follow each other continuously instead of in fixed pairs: when a ticket ends, decide whether another can start safely next to what still runs, propose it, and start it once the owner confirms. A first experiment does this by hand: the session that drives the series reads the queue, the dependencies, the files each ticket is expected to touch and the free run slots, and proposes the next ticket. This issue puts that analysis in Ariane, with the owner still confirming; autonomy comes later, once the proposals are trusted. Spec: C11 (isolation), C22 (configuration), C23 (command line).

## Current state

- `ariane start <n>` runs one ticket; the machine-wide run slots (ADR 0050) and the parallel guard (#159) let two run at once on one repository.
- Nothing in Ariane knows the order of the queue, the dependencies between issues, or whether two tickets would touch the same files.

## Decided spec

- **Queue.** The queue is the open issues carrying the label `[tracker] next_label` (default `ariane-next`), in the order the label was added (its event time, as the issue gate reads it).
- **Dependencies.** An issue body line `Needs #N` (one or several numbers, also `Needs #N and #M`) makes it wait until each named issue is closed as completed.
- **Expected files.** The paths an issue is expected to touch are the file paths and `docs/architecture/modules/<module>.md` names written in its body, mapped to the source files of those modules (`src/<package>/<module>.py`) and their tests by name; a project can add globs per label in `[next] paths`. A running ticket's files are its branch's changed files against its start base, plus its own expected files.
- **`ariane next`.** Prints, for the first issues of the queue (up to `[next] look_ahead`, default 5), whether each can start now and why not: waits on `#N`, shares `<paths>` with running `#M`, no free run slot, or a stop of the last run with the `quota` category. It proposes the first one that can start, with one line: `Next: #N (no shared file with #M). Start it with ariane next --start.` Nothing is started without `--start`.
- **`ariane next --start`.** Recomputes the proposal, refuses if it changed since it was printed (another start, a closed issue), then removes and adds the issue's `ariane` label as a maintainer would and runs `ariane start <n>` in the background, detached from the terminal, writing its output next to the ticket's records. It prints the ticket number and where its journal is.
- **Record.** Each proposal and each start is appended to `<repo>.ariane/next.md` (time, proposal, reasons for the others, who confirmed).
- New ADR: the queue label, the `Needs` syntax, how expected files are found, and why the owner confirms each start for now.

## Release note

Added: `ariane next` proposes the next ticket that can start safely next to the running ones (dependencies, shared files, run slots), and `ariane next --start` starts it after the owner's confirmation.

## Acceptance criteria

- Tests named `test_c23_next_*` show:
  - the queue follows the label order; closed or unlabelled issues are left out;
  - an issue with `Needs #N` waits while `#N` is open and becomes startable once it is closed as completed;
  - an issue that shares an expected file with a running ticket's branch or expected files is not proposed, with the shared paths named;
  - no free run slot, or a last run stopped with `quota`, proposes nothing and says why;
  - `--start` refuses a proposal that changed since it was printed, and otherwise relabels the issue and starts it (a fake runtime);
  - every proposal and start is recorded in `next.md`.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c23_next` runs at least 6 tests and they pass.
- [ ] A new ADR in `docs/adr/`.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): a new `docs/architecture/modules/<module>.md`, `cli.md`, `config.md`, `config_schema.md`, `tracker.md`; the container and component views in `docs/architecture/`; `docs/logs.md` regenerated; the README's section on running several tickets.

## Out of scope

- Starting a ticket without the owner's confirmation (later, once proposals are trusted).
- Merging pull requests (C11: the owner merges) and replaying them together (#195).

## Related

Needs #145 and #146. #142 (run slots), #159 (parallel guard), #195 (`ariane queue`); spec C11, C22, C23.
