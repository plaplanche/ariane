# Review 0

- Reviewed commit: `28122a54869f528288544c8eb9446e893e7b65fc`
- Reviewer model: claude-opus-5-5
- Verdict: **no-go** (the reviewer answered no-go)

## Findings

- **blocking** (`src/ariane/report.py:24`) Hand-takeover verify records of Ariane's own branches are silently missed

  `verify.relative_folder(branch)` (src/ariane/verify.py:43) writes the records to `work/verify/<branch>` with the branch name unchanged. Ariane's ticket branches are `ariane/<n>` (src/ariane/flow.py:42), so the C23 hand takeover (`ariane verify ariane/96`) writes `work/verify/ariane/96/metrics.json`. The globs `work/*/metrics.json` and `work/verify/*/metrics.json` match neither that file nor any other branch with a slash. The report then leaves those tickets out of its cost and time totals and gives no warning, which defeats C19 for the exact case the ticket asks to include. The test fixture uses a one-segment branch (`work/verify/b`), which hides the bug. Fix: search `work/verify/**/metrics.json` recursively (or ask verify to record the branch path) and add a test with `work/verify/ariane/3`.

- **minor** (`src/ariane/report.py:71`) Some malformed files crash the command instead of being named and skipped

  `_read` only checks some of the fields. A session that is not an object makes `session.get` raise AttributeError, which `build` does not catch. A non-numeric `rounds` passes `_read` and then raises TypeError in `sum(d["rounds"] ...)` (line 47), outside the try block. A `ticket` field whose type varies can also break the sort. The ticket says a file that cannot be parsed is named, skipped and gives exit 1; these cases give a traceback instead. Validate the type of each field used, and catch AttributeError.

- **minor** (`src/ariane/cli.py:41`) `--log-level` is accepted by `report` but no log file is configured

  `report` returns before any `logs.configure(level, log_path(...))`, so the `--log-level` option it advertises (docs/reference/cli.md) only affects console logging, and `report` writes no technical logs. Either log something like the other commands do, or document this.

- **minor** (`src/ariane/report.py:119`) Verify records without an issue show as ticket #0

  `verify` records ticket 0 when `--issue` is not given (verify.py:140). The report prints `#0 verify ...`, and several such records cannot be told apart. Printing the branch (from the folder path) would make each line identifiable.

- **blocking** Definition of done not met: The change is covered by tests that fail without it.

  tests/test_c19_report.py has 7 `test_c19_report_*` tests covering totals, --since, a null cost, no files, a corrupt file, the summary line being last and a bad date. They would fail without report.py. But the verify fixture uses a one-segment branch (`work/verify/b`), so the real layout `work/verify/ariane/<n>/` is untested and is in fact missed. Malformed-field cases are not tested either.

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

- **not met**: The change is covered by tests that fail without it.

  tests/test_c19_report.py has 7 `test_c19_report_*` tests covering totals, --since, a null cost, no files, a corrupt file, the summary line being last and a bad date. They would fail without report.py. But the verify fixture uses a one-segment branch (`work/verify/b`), so the real layout `work/verify/ariane/<n>/` is untested and is in fact missed. Malformed-field cases are not tested either.

- met: The documentation the change affects is updated (C25).

  docs/reference/cli.md is regenerated (the generator test passes), docs/architecture/modules/report.md is added, modules/cli.md and 3-components.md are updated, and the README lists `ariane report`. Once the glob is fixed, report.md and ADR 0035 need to describe the nested verify folders.

- met: Every choice the spec leaves open is recorded as an ADR in docs/adr/ (CLAUDE.md rule 2).

  docs/adr/0035-report-command.md records: --since compared with the UTC date part of `started`, the partial-cost wording, the go-rate denominator, the order of the error lines and the exit codes, and reading the checkout rather than the remote.

## Proposed learnings (not decided)

- `work/verify/<branch>` keeps the branch name unchanged, so Ariane's own branches (`ariane/<n>`) give nested folders: any code that scans verify records must search recursively, and its fixtures should use slashed branch names.
- When a command promises to name and skip a malformed file, every field it later uses (including in totals and sorting) has to be validated inside the try block, or a type error escapes as a traceback.
