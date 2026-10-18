# Learnings (temporary)

Interim notes until C18 (slice 2) gives learnings a file store and a fixed format. When it lands,
each entry below is turned into a proposal in that format and this file is removed.

Each entry: what happened, then the rule, test, check or probe it calls for (C18).

## 1. The tests check is several times slower on Windows

- **What happened:** `uv run pytest` takes about 35 s on Linux CI, 100 s on macOS CI, 195 s on
  Windows CI and about 420 s on the owner's Windows machine. It is the longest step of a
  ticket's checks, and it grows with every flow test.
- **Proposal (check):** record each check's duration per OS (C19) and flag a check whose
  duration grows past a threshold, so the slowdown is seen before it blocks tickets.
- **Update (2026-10-18):** by October the suite took about 4 minutes on Linux CI and 23 to 26
  minutes on Windows CI. The tests now run in parallel (`pytest-xdist`, `-n auto`) and CI runs
  Python 3.11 on Linux only (ADR 0048).

## 2. The push guard stops a ticket when anyone touches git during it

- **What happened:** ticket #5's first run stopped because a person ran
  `git branch --set-upstream-to` in the main checkout while the agent session ran. The edit to
  `.git/config` changed the guard's snapshot (ADR 0007, layer 3). Background `git gc` rewriting
  `.git/info/refs` had the same effect (#10, fixed in #11).
- **Proposal (rule):** while a ticket runs, nobody runs git commands in the repository or its
  working trees. This holds until claims (C13) let the guard tell a person's change from an
  agent's.
- **Update (2026-10-11):** the remote part of the guard now watches only the ticket's branch,
  the base branch and tags (ADR 0017, amendment): other people's branches no longer stop a
  ticket. The rule above still holds for git commands in the repository and its working trees.
