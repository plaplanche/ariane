# Review 0

- Reviewed commit: `c8611378e68e780386334c2dc301c7ea6c79707a`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`src/ariane/verify.py:140`) `ariane verify` metrics are not tested

  The spec decided for this ticket requires `work/verify/<branch>/metrics.json` with mode `verify`. The code writes it: `texts[METRICS] = self.metrics.render()`, with outcome `delivered` or `stopped`. No test reads that file, though; `tests/test_c19_metrics.py` covers only `ariane start`. A regression in the verify path, such as dropping `texts[METRICS]` or the reviewer's `metrics=` argument, would pass the whole suite. Add a `test_c19_metrics_verify_*` test that runs verify and reads the committed file.

- **minor** (`docs/architecture/README.md:23`) Module index does not list the new modules

  The change adds `docs/architecture/modules/metrics.md`, `replay.md` and `stop.md`, but the "Modules" list in `docs/architecture/README.md` still stops at the old modules. Readers cannot reach the three new level-4 pages from the index (rule 11: `docs/architecture/` is part of the documentation to update).

- **minor** (`src/ariane/verify.py:140`) Verify metrics never record a "checks replayed" step

  In verify, `Metrics` gets a no-op writer and is rendered once at the end. That matches ADR 0034. But the verify file never gets the "checks replayed" step that the start flow records, so its `steps` list holds only the reviewer sessions and the outcome. The spec says verify uses "the same format". The format is the same, but a later `ariane report` comparing step sequences across modes will see different steps.

- **minor** (`src/ariane/metrics.py:28`) Timestamp is built by string-patching `ticket.now()`

  `ticket.now().replace(" ", "T")` turns the journal format into ISO-8601. If `ticket.now()`'s format ever changes, this breaks silently. A dedicated ISO helper, or `datetime.now(UTC).isoformat(timespec="seconds")` with `Z`, would be sturdier. It is cosmetic today.

## Definition of done

- met: check lint passes

  Replayed by Ariane: exit 0.

- met: check format passes

  Replayed by Ariane: exit 0.

- met: check types passes

  Replayed by Ariane: exit 0.

- met: check tests passes

  Replayed by Ariane: exit 0.

- met: check file length passes

  Replayed by Ariane: exit 0.

- met: The change is covered by tests that fail without it.

  `tests/test_c19_metrics.py` has 5 tests named `test_c19_metrics_*`. They cover a delivered ticket (2 sessions, cache tokens, duration, go, delivered), a fix round (rounds 1, first-pass no-go, session rounds), a stop (outcome stopped, stop_reason budget), unreported cost and tokens written as null, and the file being in the committed records with the exact format. Without the change, `work/7/metrics.json` would not exist and every test would fail. The verify metrics path is untested (minor finding).

- met: The documentation the change affects is updated (C25).

  Added: `modules/metrics.md`, `modules/replay.md` (the moved module) and `modules/stop.md`. Updated: `flow.md`, `verify.md`, `review_session.md` and `3-components.md`. The README mentions `work/12/metrics.json` and the verify `metrics.json`. No log events were added, so the log catalogue did not need regenerating, and the docs: references check passed. One gap: the modules index in `docs/architecture/README.md` does not list the three new modules (minor finding).

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  `docs/adr/0034-metrics-file-and-flow-split.md` records the choices the spec left open: `Metrics.run_session` as the single path for sessions, the timestamp format, writing through `TicketFolder.write` (redaction), when `outcome` is set before delivery and rewritten on a stop, what `rounds` counts, verify rendering once with outcome delivered or stopped, and the split into `replay.py` and `stop.py`, with the alternatives considered.

## Proposed learnings (not decided)

- When a ticket moves code out of a module, check the architecture README's module index as well as the per-module docs and the component diagram; it is easy to miss.
- Every output path named in the decided spec (here the `ariane verify` metrics file) needs at least one test, even when the acceptance criteria list only the main path.
- Check line-count targets (flow.py at 560 lines or fewer) by reading the final file: here it ends at 491 lines.
