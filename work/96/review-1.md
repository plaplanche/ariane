# Review 1

- Reviewed commit: `b152df5319de3243e7900f34c0bf82040e18c815`
- Reviewer model: claude-opus-5-5
- Verdict: **go**

## Findings

- **minor** (`docs/architecture/README.md:23`) Module index does not list `report`

  `modules/report.md` was added, but the "Modules" list in docs/architecture/README.md was not updated. The list was already stale: `metrics`, `replay` and `stop` are also missing. `test_docs_architecture` only checks the files under `modules/`, so it does not catch this.

- **minor** (`docs/adr/0035-report-command.md:13`) ADR names the glob `work/verify/*/metrics.json`, but the code uses `work/verify/**/metrics.json`

  report.py:25 uses a recursive glob so that branch names containing a slash are found, and modules/report.md documents this. ADR 0035 still says `work/verify/*/metrics.json`. The ADR should record the recursive choice, because it is a deliberate departure from the ticket's wording.

- **minor** (`src/ariane/report.py:105`) A boolean `cost_usd` is counted as a cost

  `_cost` uses `isinstance(c, int | float)`, which accepts `True`/`False`. `_duration_of` and the integer fields explicitly reject booleans, but `cost_usd` does not, so a malformed `cost_usd: true` adds $1 instead of being reported as malformed. This is an edge case, and nothing tests it.

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

  tests/test_c19_report.py has 9 `test_c19_report_*` tests (12 cases once the parametrized test is expanded). They cover: totals over three fixture tickets, `--since` filtering, a null cost, no metrics files, a corrupt file (named, skipped, exit 1), the summary line being last, a bad date, verify records of slashed branches, and malformed fields. All of them go through `cli.main(["report", ...])`, which does not exist without the change, so they would fail without it. Ariane's replayed test check is green.

- met: The documentation the change affects is updated (C25).

  `docs/reference/cli.md` is regenerated: the docs: references check passes and the file includes `report`. `docs/architecture/modules/report.md` is added, `modules/cli.md` is updated (command list and diagram), `3-components.md` has the new edges, and the README lists `ariane report`. One minor gap: the module index in docs/architecture/README.md does not list `report`.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0035-report-command.md records the open choices: the `--since` comparison on the UTC date part of `started`, how a partial cost is shown, the first-pass go-rate denominator, where unreadable files are reported and the exit codes, and that reading from the remote was rejected. The minor gap is that it does not record the recursive glob used for verify branch names that contain slashes.

## Proposed learnings (not decided)

- When a module is added, check both the per-module file under docs/architecture/modules/ and the index list in docs/architecture/README.md. The test only checks the per-module files.
- Type checks on numeric JSON fields should exclude bool explicitly (`isinstance(x, bool)`), because bool is a subclass of int.
- When the implementation deliberately widens a path pattern from the one in the ticket (for example `*` to `**`), the ADR should say so, not only the module doc.
