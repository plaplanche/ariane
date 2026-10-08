# Architecture decision records

One file per decision, numbered in order: `0001-short-title.md`, `0002-...`. A decision that is
replaced is not edited: a new ADR supersedes it and the old one gets `Status: superseded by NNNN`.
When only part of it is replaced, the old one keeps `accepted` and names the part and the new
ADR (for example `accepted; push guard part superseded by 0017`).

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
