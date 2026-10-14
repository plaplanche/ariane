# 0034. The metrics file and the split of `flow`

- Status: accepted
- Date: 2026-10-14
- Capabilities: C19

## Context
ADR 0030 item 1 (amending ADR 0012) asks for `work/<n>/metrics.json`, rewritten at each step.
`flow.py` was at the 600-line limit, so the ticket needs room first.

## Decision
- `metrics.py` owns the file. `Metrics.run_session` runs a session and records it, so the
  implementer, fix and reviewer sessions share one path. Timestamps are ISO-8601 UTC
  (`2026-10-14T12:00:00Z`).
- The file goes through `TicketFolder.write`, so it is redacted and restored like the other
  records, and committed by `_commit_record`.
- `outcome` is `delivered`, or `needs a human` for a draft pull request, and is set just before
  delivery (which commits the records); a later failure rewrites it as the stop's status.
  `rounds` counts fix rounds begun; `first_pass_verdict` is the first review's verdict.
- `ariane verify` renders the same format with mode `verify` once, at the end, into its
  records; outcome `delivered` when green and `stopped` otherwise (a refused verify commits nothing).
- `flow.py` is split behaviour-unchanged: the replay and review round move to `replay.py`
  (functions taking the ticket run), and `Stop` to `stop.py`, which both need without importing
  the flow. The run's `verify`, `setup` and `all_checks` become public for `replay`.

## Consequences
`flow.py` ends at about 490 lines. `replay.py` reaches into the ticket run's attributes, a
coupling accepted to keep the move mechanical.

## Alternatives considered
- A mixin class on `_TicketRun`: keeps `self.` calls but hides the dependency.
- Lazy import of `Stop` from `flow`: avoids `stop.py` but is a circular import.
