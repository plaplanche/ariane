# Product brief: Record Ariane's last action in status.md and show "merged" in ariane status (C1, C23)

- Source: issue #28 (https://github.com/plaplanche/ariane/issues/28)

## Issue

Prefilled from the issue title and body (never its comments).

## Context

`status.md` keeps Ariane's last word, which goes stale: "delivered, review and merge the pull request" stays after the merge, and no state says "merged". Ariane cannot know the merge when it writes the file. Decision: ADR 0019; spec C1 and C23.

## Current state

- `src/ariane/ticket.py:75` `set_status` writes `State`, `Updated`, `Detail` and `Next`.
- `src/ariane/cli.py:89` `_status` prints the file's state.
- `src/ariane/ticket.py:129` `read_status` parses it.

## Decided spec

- `status.md` is worded as Ariane's last action: `Last action: <state>`, `At: <time>`, `Detail`, `Next`. `read_status` reads both the new and the old wording, so earlier tickets still read.
- `ariane status <n>` fetches the base branch from the remote and adds what git shows now: `merged` when the ticket's folder `work/<n>/` exists on the remote base branch (records travel with the pull request, so this holds even after the ticket branch is deleted); otherwise the last action as today. Its one-line output says which (for example `Ticket #19: merged into main (last action: delivered, 2026-10-08 06:48Z). Next: nothing.`).
- When the remote cannot be read, it says so and prints the last action.

## Release note

Changed: `ariane status` shows whether a ticket was merged.

## Acceptance criteria

- Tests named `test_c23_status_merged_*` show: a ticket whose branch was merged into the base reads `merged`, also after the ticket branch was deleted; one not merged reads its last action; an unreadable remote gives the last action and says the remote could not be read; an old-format status file still reads.
- All checks in CLAUDE.md pass.

## Acceptance checklist

- [ ] `uv run pytest -k c23_status_merged` runs at least 3 tests and they pass.
- [ ] All checks in CLAUDE.md pass.

## Out of scope

Writing anything after the merge (Ariane never commits to the base branch), labels (C14, frozen).

## Related

ADR 0019, spec C1, C23.
