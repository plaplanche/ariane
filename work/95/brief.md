# Product brief: Record each ticket's measurements in work/<n>/metrics.json (C19, slice 4)

- Source: issue #95 (https://github.com/plaplanche/ariane/issues/95)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

First code ticket of slice 4 (ADR 0030 item 1, amending ADR 0012): every ticket keeps machine-readable measurements, the base of `ariane report`, of shadow mode and of the success measure (spec "Measuring Ariane"). Spec: C19.

## Current state

- `src/ariane/runtime.py:35`: `SessionResult` carries `stop_reason`, `cost_usd`, input, output, cache read and cache write tokens of each session; nothing persists them except the journal text.
- `src/ariane/flow.py`: sessions run in `_implement` (line 226) and `_review` (line 507); records are committed by `_commit_record` (line 581); a stop goes through `_stopped` (line 586). `src/ariane/verify.py` runs the review of `ariane verify`.
- `src/ariane/ticket.py`: `TicketFolder` writes `work/<n>/` (`write`, `log`, `set_status`).
- `flow.py` is exactly 600 lines (updated 2026-10-14); `scripts/check_file_length.py` refuses files over 600 lines, so any line added to it fails the check.

## Decided spec

- New module `src/ariane/metrics.py` owns `work/<n>/metrics.json` (UTF-8, indented JSON, sorted keys):
  `{"ticket": n, "mode": "delivered" | "shadow", "started": ISO-8601 UTC, "steps": [{"name", "at"}], "sessions": [{"role", "round", "runtime", "model", "stop_reason", "cost_usd" (null when not reported), "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "duration_s"}], "rounds": number of fix rounds, "first_pass_verdict": "go" | "no-go" | "not reviewed", "outcome": "running" | "delivered" | "stopped" | "needs a human"}`. Token fields are null when not reported.
- Ariane rewrites the file after each step (folder opened, each session, checks replayed, delivery or stop) and it is committed with the records, so it travels with the pull request like the other records (ADR 0019). A crash leaves `outcome` `running`.
- `ariane verify` writes `work/verify/<branch>/metrics.json` in the same format with `mode` `verify`.
- **First, make room in `flow.py`**: move a coherent group of its code (for example the review round: `_review`, the replay helpers and their constants) into a new module, behaviour unchanged, with its `docs/architecture/modules/<module>.md`, so that `flow.py` ends this ticket at 560 lines or fewer. Then `flow.py` only calls `metrics`.

## Release note

New: each ticket records its measurements in `work/<n>/metrics.json` (cost, tokens, durations, rounds, first-pass verdict, outcome).

## Acceptance criteria

- Tests named `test_c19_metrics_*` show: the file after a delivered ticket (one implementer and one reviewer session, cache tokens, durations, `first_pass_verdict` `go`, `outcome` `delivered`); after a fix round (`rounds` 1, first-pass `no-go`); after a stop (`outcome` `stopped`); a session with no reported cost writes null; the file is in the committed records.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c19_metrics` runs at least 4 tests and they pass.
- [ ] All checks in CLAUDE.md pass.
- [ ] `src/ariane/flow.py` has 560 lines or fewer.
- [ ] Definition of done, documentation (C25): `docs/architecture/modules/metrics.md` and the moved module's doc added, `flow.md` and `verify.md` updated, the log catalogue regenerated if events are added, README mentions `work/<n>/metrics.json`.

## Out of scope

`ariane report`, shadow mode, `ariane judge`, attempts counting (later tickets of slice 4).

## Related

ADR 0030 (item 1), ADR 0012, ADR 0019, spec C19.
