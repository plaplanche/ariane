# 0019. Shorter ticket records; a status that does not go stale

- Status: accepted
- Date: 2026-10-08
- Capabilities: C1, C5, C9, C23

## Context
Each ticket adds 248 to 309 lines under `work/` on `main` (tickets #5, #7, #10, #16, #19).
The issue body is stored twice: in `brief.md` (64 lines for #19) and inside the prompt recorded
in `journal.md` (lines 37 to 94 for #19). `status.md` keeps Ariane's last word, which goes stale:
"delivered, review and merge the pull request" stays after the merge, and no state says
"merged". Every brief says "draft, not yet approved" because stages and approvals (C2) are not
built yet.

## Decision
Records stay in `work/<n>/` on the ticket branch and reach `main` with the merge, shortened:
- **The issue body is stored once**, in `brief.md`. The prompt recorded in the journal replaces
  the issue part with a pointer ("issue title and body: see brief.md, read at <time>"); the
  rest of the prompt is recorded in full, so the context stays reconstructible (C5).
- **`brief.md` drops its approval lines** until C2 exists; it keeps the source issue link.
- **`checks.md`** keeps each check's command, result and duration; the output of a passing
  check is cut to its last 20 lines, a failing check's output stays whole.
- **`status.md` records Ariane's last action and its date**, worded as such ("Last action:
  delivered, pull request opened from ariane/<n>"). `ariane status <n>` adds what git knows
  now: `merged` when the ticket branch's head is contained in the base branch on the remote.

This decision amends ADR 0006 (records) and ADR 0011's expectations of the journal.

## Consequences
Records on `main` shrink by about the issue body and the passing checks' output. The status
file never claims what Ariane cannot know; `ariane status` gives the live answer.

## Alternatives considered
- Raw journals on a separate branch or as tracker attachments: keeps `main` smallest, but
  splits a ticket's truth across places, and the GitHub REST API has no endpoint to attach a
  file to an issue or pull request.
- Ariane rewriting the status after the merge: needs a commit on `main`, which Ariane never
  makes (C11).
