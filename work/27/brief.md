# Product brief: Store the issue body once and shorten passing checks' output in ticket records (C1)

- Status: draft
- Approved: not yet
- Source: issue #27 (https://github.com/plaplanche/ariane/issues/27)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

Each ticket adds 248 to 309 lines under `work/`, and the issue body is stored twice: in `brief.md` and in the prompt recorded in `journal.md`. Every brief also says "draft, not yet approved" although stages and approvals (C2) do not exist yet. Decision: ADR 0019; spec C1.

## Current state

- `src/ariane/ticket.py:117` `brief` writes the issue with `Status: draft` and `Approved: not yet`.
- `src/ariane/flow.py:203` journals the whole prompt, which contains the issue title and body (`src/ariane/context.py:23` `implementer_prompt`).
- `src/ariane/checks.py:66` `report` writes every check's whole output.

## Decided spec

- `brief.md` keeps its title, the source issue link and the issue text, and drops the `Status` and `Approved` lines.
- The journal records the prompt with the untrusted ticket block replaced by one line: `(issue #<n> title and body: see brief.md)`. The rest of the prompt is recorded unchanged.
- In `checks.md`, a passing check's output is cut to its last 20 lines, preceded by `(<k> earlier lines omitted)` when cut; a failing check's output stays whole.

## Release note

Changed: shorter ticket records; the issue body is stored once.

## Acceptance criteria

- Tests named `test_c1_records_*` show: the brief has no approval lines; the journal's recorded prompt does not contain the issue body but points to `brief.md`; a passing check with 50 lines of output keeps its last 20 and says 30 were omitted; a failing check keeps all its lines.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c1_records` runs at least 3 tests and they pass.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

The status file (separate issue), records on a separate branch.

## Related

ADR 0019, spec C1.
