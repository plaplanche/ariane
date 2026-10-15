# 0035. The `ariane report` command

- Status: accepted
- Date: 2026-10-14
- Capabilities: C19, C23

## Context
ADR 0030 item 7 asks for a command showing where time and money go over a period, from the
metrics files of the tickets.

## Decision
- `report.py` reads `work/*/metrics.json` and `work/verify/*/metrics.json` of the current
  checkout. `--since YYYY-MM-DD` compares with the date part of `started` (UTC).
- Cost of a ticket is the sum of the reported session costs; when some session's cost is null,
  the line says "partly not reported" (with the known part, if any). Agent time is the sum of
  `duration_s`.
- First-pass go rate is go / tickets with a verdict other than `not reviewed`.
- An unreadable or malformed file is named on one line before the tickets and skipped; the exit
  code is 1. No file at all gives one line and exit 0. The summary line is always last.

## Consequences
Only tickets whose records are in the checkout are counted. Human time, bypassed gates, shadow
tickets and attempts are left to a later ticket.

## Alternatives considered
Reading merged tickets from the remote: needs network access and a fetch; rejected for a first version.
