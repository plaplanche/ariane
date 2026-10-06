# Learnings (temporary)

Interim notes until C18 (slice 2) gives learnings a file store and a fixed format. When it lands,
each entry below is turned into a proposal in that format and this file is removed.

Each entry: what happened, then the rule, test, check or probe it calls for (C18).

## 1. The Windows tests check is slow

- **What happened:** on Windows CI, `uv run pytest` takes about 420 s, against well under a
  minute on Linux.
- **Proposal (check):** record each check's duration per OS (C19) and flag a check whose
  duration grows past a threshold, so the slowdown is seen before it blocks tickets.

## 2. The push guard stops a ticket when anyone touches git during it

- **What happened:** ticket #5's first run stopped because a person ran
  `git branch --set-upstream-to` in the main checkout while the agent session ran. The edit to
  `.git/config` changed the guard's snapshot (ADR 0007, layer 3). Background `git gc` rewriting
  `.git/info/refs` had the same effect (#10, fixed in #11).
- **Proposal (rule):** while a ticket runs, nobody runs git commands in the repository or its
  working trees. This holds until claims (C13) let the guard tell a person's change from an
  agent's.
