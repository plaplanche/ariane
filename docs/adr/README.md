# Architecture decision records

One file per decision, numbered in order: `0001-short-title.md`, `0002-...`. A decision that is
replaced is not edited: a new ADR supersedes it and the old one gets `Status: superseded by NNNN`.
When only part of it is replaced, the old one keeps `accepted` and names the part and the new
ADR (for example `accepted; push guard part superseded by 0017`).

Tickets running in parallel can each take the same next free number; `tests/test_c25_adr_numbers.py`
fails when two files share a number or a file does not start with four digits and a dash, so the
collision shows on the second pull request's merge with the base (CI, `ariane update`). It is
resolved this way: the ADR of the later pull request takes the next free number, and every
reference that pull request added to its old number is renumbered; the earlier ADR keeps its
number.

Template:

```markdown
# NNNN. Title

- Status: accepted | superseded by NNNN
- Date: YYYY-MM-DD
- Capabilities: C…

## Context
What forced a choice, with the requirement of `docs/spec.md` it serves.

## Decision
What was chosen.

## Consequences
What becomes easier, what becomes harder, what is now ruled out.

## Alternatives considered
Each option rejected and why.
```
