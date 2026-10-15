# Product brief: Add ariane report [--since] over the tickets' metrics (C19, C23, slice 4)

- Source: issue #96 (https://github.com/plaplanche/ariane/issues/96)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

ADR 0030 item 7 and ADR 0012: a command shows where time and money go over a period (C19), first from the metrics of delivered tickets. Needs the metrics ticket of slice 4 merged first. Spec: C19, C23.

## Current state

- `src/ariane/cli.py:61`: subcommands `start`, `status`, `verify`; no `report`.
- `work/<n>/metrics.json` (after the metrics ticket) holds sessions, rounds, first-pass verdict and outcome per ticket.

## Decided spec

- `ariane report [--since YYYY-MM-DD]` reads every `work/*/metrics.json` in the current checkout (and `work/verify/*/metrics.json`), keeps tickets started on or after `--since`, and prints one line per ticket: number, mode, outcome, cost (sum of reported costs; "partly not reported" when some session's cost is null), agent time (sum of `duration_s`), rounds, first-pass verdict.
- Then totals: tickets, cost, agent time, rounds, first-pass go rate (go / reviewed tickets). One summary line ends the output (C23), exit code 0.
- No metrics file: one line saying so, exit 0. A file that cannot be read or parsed: named on one line, skipped, exit 1 at the end.
- New module `src/ariane/report.py`; `cli.py` only wires it.

## Release note

New: `ariane report [--since]` summarises cost, agent time, rounds and first-pass verdicts per ticket.

## Acceptance criteria

- Tests named `test_c19_report_*` show: totals over three fixture tickets; `--since` filtering; a null cost; no metrics files; a corrupt file (named, skipped, exit 1); the summary line is last.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c19_report` runs at least 5 tests and they pass.
- [ ] All checks in CLAUDE.md pass.
- [ ] Definition of done, documentation (C25): `docs/reference/cli.md` regenerated, `docs/architecture/modules/report.md` added, `cli.md` updated, README lists `ariane report`.

## Out of scope

Human time, gates bypassed, shadow tickets and attempts in the report (a later ticket of slice 4).

## Related

ADR 0030 (item 7), ADR 0012, spec C19, C23.
